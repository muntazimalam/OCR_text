import gc
from typing import Any, Dict, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.analyzers.blur import BlurAnalyzer
from app.analyzers.brightness import BrightnessAnalyzer
from app.analyzers.duplicate import DuplicateAnalyzer
from app.analyzers.ocr import OCRAnalyzer
from app.analyzers.number_plate import NumberPlateAnalyzer
from app.analyzers.metadata import MetadataAnalyzer
from app.analyzers.tampering import TamperingAnalyzer
from app.analyzers.photo_of_photo import PhotoOfPhotoAnalyzer
from app.services.image_service import ImageService
from app.utils.file_utils import load_image_auto_orient
from app.core.logging import logger


class AnalysisService:
    def __init__(self):
        self.blur_analyzer = BlurAnalyzer()
        self.brightness_analyzer = BrightnessAnalyzer()
        self.duplicate_analyzer = DuplicateAnalyzer()
        self.ocr_analyzer = OCRAnalyzer()
        self.number_plate_analyzer = NumberPlateAnalyzer()
        self.metadata_analyzer = MetadataAnalyzer()
        self.tampering_analyzer = TamperingAnalyzer()
        self.photo_of_photo_analyzer = PhotoOfPhotoAnalyzer()

    def run_pipeline(
        self, db: Session, image_id: UUID, file_path: str, sha256_hash: str
    ) -> Dict[str, Any]:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        # Apply EXIF auto-orientation for mobile phone uploads
        file_bytes, _, _, _ = load_image_auto_orient(raw_bytes)
        # Free raw_bytes immediately
        del raw_bytes
        gc.collect()

        issues: List[Dict[str, Any]] = []
        failure_reasons: List[str] = []

        # 1. Blur
        try:
            blur_res = self.blur_analyzer.analyze(file_path, file_bytes)
            if blur_res.get("is_blurry"):
                issues.append({
                    "type": "blurry_image",
                    "severity": "medium",
                    "confidence": 0.85,
                    "description": f"Image is blurry with variance score {blur_res.get('score')}"
                })
        except Exception as e:
            logger.error("blur_analyzer_error", error=str(e))
            blur_res = {"score": 0.0, "is_blurry": None, "error": str(e)}
        gc.collect()

        # 2. Brightness
        try:
            brightness_res = self.brightness_analyzer.analyze(file_path, file_bytes)
            b_status = brightness_res.get("status")
            if b_status in {"very_dark", "low_light", "overexposed"}:
                issues.append({
                    "type": f"lighting_{b_status}",
                    "severity": "medium" if b_status == "low_light" else "high",
                    "confidence": 0.90,
                    "description": f"Suboptimal image brightness ({b_status})"
                })
        except Exception as e:
            logger.error("brightness_analyzer_error", error=str(e))
            brightness_res = {"score": 0.0, "status": "error", "error": str(e)}
        gc.collect()

        # 3. Duplicate
        try:
            duplicate_res = self.duplicate_analyzer.analyze(file_path, file_bytes)
            existing_dup = ImageService.find_duplicate_by_hash(db, sha256_hash, image_id)
            if existing_dup:
                duplicate_res["is_duplicate"] = True
                duplicate_res["duplicate_of"] = existing_dup.id
                issues.append({
                    "type": "exact_duplicate",
                    "severity": "high",
                    "confidence": 1.0,
                    "description": f"Exact SHA-256 duplicate of image {existing_dup.id}"
                })
        except Exception as e:
            logger.error("duplicate_analyzer_error", error=str(e))
            duplicate_res = {"is_duplicate": False, "error": str(e)}

        # 4. OCR
        try:
            ocr_res = self.ocr_analyzer.analyze(file_path, file_bytes)
        except Exception as e:
            logger.error("ocr_analyzer_error", error=str(e))
            ocr_res = {"text": None, "confidence": None, "error": str(e)}
        gc.collect()

        # 5. Number Plate
        try:
            plate_res = self.number_plate_analyzer.analyze(file_path, file_bytes, ocr_result=ocr_res)
            if not plate_res.get("valid"):
                issues.append({
                    "type": "invalid_number_plate",
                    "severity": "high",
                    "confidence": 0.80,
                    "description": "No valid license plate format detected"
                })
        except Exception as e:
            logger.error("number_plate_analyzer_error", error=str(e))
            plate_res = {"detected": False, "valid": False, "confidence": 0.0, "error": str(e)}

        # 6. Metadata
        try:
            metadata_res = self.metadata_analyzer.analyze(file_path, file_bytes)
            if metadata_res.get("screenshot_probability", 0.0) >= 0.7:
                issues.append({
                    "type": "probable_screenshot",
                    "severity": "low",
                    "confidence": metadata_res.get("screenshot_probability"),
                    "description": "High probability of being a screenshot rather than camera photo"
                })
        except Exception as e:
            logger.error("metadata_analyzer_error", error=str(e))
            metadata_res = {"has_exif": False, "screenshot_probability": 0.0, "error": str(e)}

        # 7. Tampering
        try:
            tampering_res = self.tampering_analyzer.analyze(file_path, file_bytes, metadata_result=metadata_res)
            if tampering_res.get("suspicious_editing"):
                issues.append({
                    "type": "suspicious_editing",
                    "severity": "high",
                    "confidence": tampering_res.get("confidence", 0.85),
                    "description": "Image metadata indicates editing software usage"
                })
        except Exception as e:
            logger.error("tampering_analyzer_error", error=str(e))
            tampering_res = {"suspicious_editing": False, "confidence": 0.0, "error": str(e)}

        # 8. Photo-of-Photo / Moiré Detection
        try:
            pop_res = self.photo_of_photo_analyzer.analyze(file_path, file_bytes, metadata_result=metadata_res)
            if pop_res.get("is_photo_of_photo"):
                issues.append({
                    "type": "photo_of_photo",
                    "severity": "medium",
                    "confidence": pop_res.get("confidence", 0.80),
                    "description": "Moiré pattern/heuristics indicate image was taken of a digital screen or printed photo"
                })
        except Exception as e:
            logger.error("photo_of_photo_analyzer_error", error=str(e))
            pop_res = {"is_photo_of_photo": False, "confidence": 0.0, "error": str(e)}

        # Free file_bytes before score calculation
        del file_bytes
        gc.collect()

        # Overall Score Calculation
        overall_score = self._calculate_overall_score(
            blur_res, brightness_res, duplicate_res, plate_res, tampering_res, pop_res
        )

        # Failure Condition Checks
        if not plate_res.get("valid"):
            failure_reasons.append("No valid license plate detected")
        if blur_res.get("is_blurry"):
            failure_reasons.append("Image is blurry")
        if brightness_res.get("status") in {"very_dark", "overexposed"}:
            failure_reasons.append("Suboptimal lighting")

        is_failed = len(failure_reasons) > 0
        error_msg = f"Validation Failed: {', '.join(failure_reasons)}" if is_failed else None

        return {
            "image_id": image_id,
            "blur_score": blur_res.get("score"),
            "is_blurry": blur_res.get("is_blurry"),
            "brightness_score": brightness_res.get("score"),
            "brightness_status": brightness_res.get("status"),
            "contrast_score": brightness_res.get("contrast_score"),
            "is_duplicate": duplicate_res.get("is_duplicate", False),
            "duplicate_of": duplicate_res.get("duplicate_of"),
            "ocr_text": ocr_res.get("text"),
            "ocr_confidence": ocr_res.get("confidence"),
            "plate_detected": plate_res.get("detected", False),
            "plate_valid": plate_res.get("valid", False),
            "plate_confidence": plate_res.get("confidence"),
            "tampering_info": tampering_res,
            "metadata_info": metadata_res,
            "overall_score": overall_score,
            "issues": issues,
            "is_failed": is_failed,
            "error_message": error_msg,
        }

    def _calculate_overall_score(
        self,
        blur_res: dict,
        brightness_res: dict,
        dup_res: dict,
        plate_res: dict,
        tampering_res: dict,
        pop_res: dict = None
    ) -> float:
        score = 1.0

        if blur_res.get("is_blurry"):
            score -= 0.20
        if brightness_res.get("status") in {"very_dark", "overexposed"}:
            score -= 0.15
        elif brightness_res.get("status") == "low_light":
            score -= 0.10
        if dup_res.get("is_duplicate"):
            score -= 0.25
        if not plate_res.get("valid"):
            score -= 0.20
        if tampering_res.get("suspicious_editing"):
            score -= 0.20
        if pop_res and pop_res.get("is_photo_of_photo"):
            score -= 0.15

        return round(max(score, 0.0), 2)
