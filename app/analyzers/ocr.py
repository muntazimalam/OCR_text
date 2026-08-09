import gc
import os
import re
import cv2
import numpy as np
from typing import Any, Dict, List
from PIL import Image, ImageDraw, ImageFont
from app.analyzers.base import BaseAnalyzer
from app.core.logging import logger

_CHAR_TEMPLATES = None
_easyocr_reader = None


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader
    try:
        import easyocr
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        return _easyocr_reader
    except Exception as e:
        logger.warning("easyocr_init_failed", error=str(e))
        return None


def _tesseract_extract(img_bgr: np.ndarray, plate_rois: List[tuple] = None) -> Dict[str, Any]:
    """
    Runs Tesseract OCR on detected license plate cropped ROIs for accuracy.
    """
    try:
        import pytesseract
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h_img, w_img = gray.shape[:2]

        if not plate_rois:
            edges = cv2.Canny(gray, 30, 150)
            cnts, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            plate_rois = [(x, y, w, h) for (x, y, w, h) in [cv2.boundingRect(c) for c in cnts]
                          if 1.2 <= (w / float(h) if h > 0 else 0) <= 7.0 and 35 <= w <= (w_img * 0.85) and 12 <= h <= (h_img * 0.45)]

        for (px, py, pw, ph) in plate_rois[:5]:
            roi = gray[py:py+ph, px:px+pw]
            if roi.size == 0:
                continue

            roi_scaled = cv2.resize(roi, (pw * 2, ph * 2), interpolation=cv2.INTER_CUBIC)
            thresh = cv2.adaptiveThreshold(roi_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 31, 10)
            config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            text = pytesseract.image_to_string(thresh, config=config).strip()
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())

            if len(cleaned) >= 4:
                return {
                    "text": cleaned,
                    "confidence": 0.95,
                    "detections": [{"text": cleaned, "confidence": 0.95}]
                }

        return None
    except Exception:
        return None


class OCRAnalyzer(BaseAnalyzer):
    """
    Robust OCR engine utilizing EasyOCR with PyTorch as primary recognition engine,
    falling back to Tesseract OCR if available. Memory efficient and accurate.
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"text": None, "confidence": None, "error": "Image decode failed"}

            h, w = img.shape[:2]
            if max(h, w) > 1024:
                scale = 1024.0 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            # 1. Primary: EasyOCR
            reader = _get_easyocr_reader()
            if reader is not None:
                try:
                    results = reader.readtext(img)
                    detections = []
                    for res in results:
                        if len(res) >= 3:
                            _, text, conf = res[:3]
                            text_str = str(text).strip().upper()
                            cleaned_str = re.sub(r'[^A-Z0-9]', '', text_str)
                            if len(cleaned_str) >= 2:
                                detections.append({
                                    "text": cleaned_str,
                                    "confidence": float(conf)
                                })
                    if detections:
                        texts = [d["text"] for d in detections]
                        confs = [d["confidence"] for d in detections]
                        gc.collect()
                        return {
                            "text": " ".join(texts),
                            "confidence": round(sum(confs) / len(confs), 2),
                            "detections": detections
                        }
                except Exception as e:
                    logger.warning("easyocr_execution_failed", error=str(e))

            # 2. Fallback: Tesseract
            tess_result = _tesseract_extract(img)
            if tess_result:
                gc.collect()
                return tess_result

            gc.collect()
            return {"text": "", "confidence": 0.0, "detections": []}

        except Exception as e:
            gc.collect()
            return {"text": None, "confidence": None, "error": str(e)}

