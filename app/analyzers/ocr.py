import gc
import os
import re
import cv2
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from app.analyzers.base import BaseAnalyzer
from app.core.logging import logger

_OCR_ENGINE = None

_MAX_CROP_OCR_CALLS = 8


def _get_ocr_engine():
    """Lazily loads the lightweight RapidOCR (ONNX PP-OCRv4) engine.

    OCR_ENGINE env: 'tesseract' (forced lightweight fallback), 'rapidocr' (forced),
    or 'auto' (default) — auto prefers RapidOCR when importable.

    RapidOCR uses ~15 MB of ONNX models and no PyTorch, so it loads a small
    fraction of EasyOCR's RAM/disk footprint and keeps 512 MB instances safe
    while staying significantly more accurate than Tesseract.
    """
    global _OCR_ENGINE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE or None

    choice = os.getenv("OCR_ENGINE", "auto").strip().lower()
    if choice == "tesseract":
        _OCR_ENGINE = False
        return None

    if choice == "auto":
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except Exception:
            logger.warning("rapidocr_unavailable", error="rapidocr_onnxruntime not installed")
            _OCR_ENGINE = False
            return None

    try:
        from rapidocr_onnxruntime import RapidOCR
        try:
            _OCR_ENGINE = RapidOCR(intra_op_num_threads=2)
        except TypeError:
            _OCR_ENGINE = RapidOCR()
        logger.info("rapidocr_loaded")
    except Exception as e:
        logger.warning("rapidocr_init_failed", error=str(e))
        _OCR_ENGINE = False
    return _OCR_ENGINE or None


def _locate_plate_rois(img_bgr: np.ndarray, top_n: int = 6) -> List[Tuple[int, int, int, int]]:
    """
    Extracts candidate license plate ROIs regardless of plate color (White, Yellow, Green, Silver, Black)
    using edge and contour shape analysis.
    """
    h_img, w_img = img_bgr.shape[:2]
    if h_img < 40 or w_img < 40:
        return []

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 180)
    cnts, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    img_area = float(h_img * w_img)
    rois = []

    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh) if bh > 0 else 0
        area_frac = (bw * bh) / img_area
        if 1.2 <= aspect <= 7.5 and 0.0002 <= area_frac <= 0.30 and bw >= 20 and bh >= 8:
            rois.append((x, y, bw, bh))

    # Deduplicate heavily overlapping bounding boxes
    picks = []
    for r in sorted(rois, key=lambda b: b[2] * b[3], reverse=True):
        x, y, bw, bh = r
        if not any(abs(x - px) < pw * 0.5 and abs(y - py) < ph * 0.5 for (px, py, pw, ph) in picks):
            picks.append(r)
            if len(picks) >= top_n:
                break
    return picks


def _crop_and_enhance_patch(img_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """Crops candidate plate patch with padding, upscales, and enhances contrast using CLAHE."""
    x, y, pw, ph = roi
    h_img, w_img = img_bgr.shape[:2]
    pad_x = int(pw * 0.15)
    pad_y = int(ph * 0.35)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(w_img, x + pw + pad_x), min(h_img, y + ph + pad_y)
    patch = img_bgr[y0:y1, x0:x1]

    if patch.size == 0 or patch.shape[0] < 6 or patch.shape[1] < 18:
        return None

    target_h = 160
    scale = max(target_h / float(patch.shape[0]), 2.0)
    # Cap upscaled patch size to bound RAM usage (large ROIs would otherwise balloon)
    max_dim = float(max(patch.shape[:2]))
    if max_dim * scale > 900:
        scale = 900.0 / max_dim
    patch_up = cv2.resize(patch, (int(patch.shape[1] * scale), int(patch.shape[0] * scale)), interpolation=cv2.INTER_CUBIC)

    lab = cv2.cvtColor(patch_up, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    patch_enhanced = cv2.cvtColor(cv2.merge((l_ch, a_ch, b_ch)), cv2.COLOR_LAB2BGR)
    return patch_enhanced


def _tesseract_extract(img_bgr: np.ndarray) -> Optional[Dict[str, Any]]:
    """Tesseract OCR fallback used when the RapidOCR engine is unavailable."""
    try:
        import pytesseract
        from PIL import Image as PILImage
    except Exception:
        return None
    try:
        pil_img = PILImage.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        detections = []
        seen_texts = set()
        for psm in ("7", "11", "6"):
            try:
                data = pytesseract.image_to_data(
                    pil_img,
                    config=f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                    output_type=pytesseract.Output.DICT,
                )
            except Exception:
                continue
            for i, raw in enumerate(data.get("text", [])):
                cleaned = re.sub(r"[^A-Z0-9]", "", str(raw).upper())
                if len(cleaned) < 2 or cleaned in seen_texts:
                    continue
                try:
                    conf = float(data.get("conf", [0])[i])
                except (TypeError, ValueError, IndexError):
                    conf = 0.0
                if conf < 30.0:
                    continue
                seen_texts.add(cleaned)
                detections.append({"text": cleaned, "confidence": round(conf / 100.0, 2)})
        if not detections:
            return None
        confs = [d["confidence"] for d in detections]
        return {
            "text": " ".join(d["text"] for d in detections),
            "confidence": round(sum(confs) / len(confs), 2),
            "detections": detections,
        }
    except Exception:
        return None


def _run_engine(
    engine,
    img_bgr: np.ndarray,
    min_chars: int = 2,
    with_boxes: bool = False,
) -> Optional[Dict[str, Any]]:
    """Runs RapidOCR on an image and returns normalized detections (or None)."""
    try:
        raw = engine(img_bgr)
        results = raw[0] if isinstance(raw, tuple) else raw
        detections: List[Dict[str, Any]] = []
        for item in results or []:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            box, text, score = item[:3]
            text_str = str(text).strip().upper()
            cleaned_str = re.sub(r'[^A-Z0-9]', '', text_str)
            if len(cleaned_str) < min_chars:
                continue
            det = {"text": cleaned_str, "confidence": float(score)}
            if with_boxes and box is not None:
                try:
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    x0, y0 = min(xs), min(ys)
                    x1, y1 = max(xs), max(ys)
                    det["box"] = (int(x0), int(y0), int(max(x1 - x0, 1)), int(max(y1 - y0, 1)))
                except Exception:
                    pass
            detections.append(det)
        if not detections:
            return None
        confs = [d["confidence"] for d in detections if d.get("confidence") is not None]
        return {
            "text": " ".join(d["text"] for d in detections),
            "confidence": round(sum(confs) / len(confs), 2) if confs else 0.0,
            "detections": detections,
        }
    except Exception as e:
        logger.warning("ocr_engine_execution_failed", error=str(e))
        return None


def _merge_ocr_results(*results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merges multiple OCR results, keeping distinct unique detections."""
    merged_dets: List[Dict[str, Any]] = []
    seen_texts = set()

    for res in results:
        if not res:
            continue
        for det in res.get("detections", []):
            txt = det.get("text")
            if txt and txt not in seen_texts:
                seen_texts.add(txt)
                merged_dets.append(det)

    if not merged_dets:
        return {"text": "", "confidence": 0.0, "detections": []}

    confs = [d["confidence"] for d in merged_dets if d.get("confidence") is not None]
    return {
        "text": " ".join(d["text"] for d in merged_dets),
        "confidence": round(sum(confs) / len(confs), 2) if confs else 0.0,
        "detections": merged_dets,
    }


class OCRAnalyzer(BaseAnalyzer):
    """
    Universal High-Accuracy License Plate OCR Engine:
    Processes full image at high resolution + crops candidate plate ROIs (white, yellow, green, silver)
    for maximum recognition accuracy across cars, motorcycles, scooters, and trucks.
    Uses RapidOCR (PP-OCRv4 ONNX) when available and falls back to Tesseract.
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"text": None, "confidence": None, "error": "Image decode failed"}

            h, w = img.shape[:2]
            # Moderate resolution for OCR — big enough for plates, small enough
            # to stay inside 512 MB RAM instances.
            if max(h, w) > 1600:
                scale = 1600.0 / max(h, w)
                img_work = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                img_work = img

            engine = _get_ocr_engine()
            if engine is not None:
                # 1. Full-image OCR
                full_result = _run_engine(engine, img_work, min_chars=2, with_boxes=True)

                # 2. Candidate plate ROIs (bounded to keep runtime + RAM low)
                crop_results: List[Dict[str, Any]] = []
                plate_rois = _locate_plate_rois(img_work, top_n=_MAX_CROP_OCR_CALLS)

                for roi in plate_rois:
                    patch = _crop_and_enhance_patch(img_work, roi)
                    if patch is not None:
                        c_res = _run_engine(engine, patch, min_chars=2, with_boxes=False)
                        if c_res:
                            crop_results.append(c_res)

                combined = _merge_ocr_results(full_result, *crop_results)
                if combined.get("text"):
                    gc.collect()
                    return combined

            # 3. Lightweight fallback when no heavy model can be loaded
            tess_result = _tesseract_extract(img_work)
            gc.collect()
            if tess_result:
                return tess_result
            return {"text": "", "confidence": 0.0, "detections": []}

        except Exception as e:
            gc.collect()
            return {"text": None, "confidence": None, "error": str(e)}
