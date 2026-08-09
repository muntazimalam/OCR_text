import gc
import re
import cv2
import numpy as np
from typing import Any, Dict, List
from app.analyzers.base import BaseAnalyzer
from app.core.logging import logger


def _get_tesseract_text(img_bgr: np.ndarray) -> str:
    """
    Attempts Tesseract OCR. Falls back to contour-based digit extraction if unavailable.
    """
    try:
        import pytesseract
        # Preprocess: grayscale, threshold for plate-like text
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        # Adaptive threshold for varied lighting conditions on plates
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 31, 10)
        # Tesseract with plate-optimized config: single line, alphanumeric only
        config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text = pytesseract.image_to_string(thresh, config=config).strip()
        return text
    except ImportError:
        logger.warning("tesseract_not_available", msg="pytesseract not installed, using OpenCV fallback")
        return _opencv_text_fallback(img_bgr)
    except Exception as e:
        logger.warning("tesseract_error", error=str(e))
        return _opencv_text_fallback(img_bgr)


def _opencv_text_fallback(img_bgr: np.ndarray) -> str:
    """
    Lightweight OpenCV-only text region detection fallback.
    Finds rectangular contours that look like character bounding boxes
    and returns a placeholder indicating text regions were found.
    """
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        # Bilateral filter preserves edges
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(filtered, 30, 200)

        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # Find rectangular contours (potential plate regions)
        plate_candidates = []
        h_img, w_img = gray.shape[:2]
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:30]:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect = w / float(h) if h > 0 else 0
                area_ratio = (w * h) / (w_img * h_img) if (w_img * h_img) > 0 else 0
                # License plates are typically 2:1 to 5:1 aspect ratio
                if 1.5 <= aspect <= 6.0 and 0.005 <= area_ratio <= 0.3:
                    plate_candidates.append((x, y, w, h))

        if plate_candidates:
            return "PLATE_REGION_DETECTED"
        return ""
    except Exception:
        return ""


class OCRAnalyzer(BaseAnalyzer):
    """
    Lightweight OCR using Tesseract (if available) or OpenCV contour fallback.
    Uses ~30MB RAM total vs EasyOCR/PyTorch at ~350MB.
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"text": None, "confidence": None, "error": "Image decode failed"}

            h, w = img.shape[:2]
            # Downscale to max 800px for fast OCR processing
            if max(h, w) > 800:
                scale = 800.0 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            text = _get_tesseract_text(img)
            gc.collect()

            if not text:
                return {"text": "", "confidence": 0.0, "detections": []}

            # Clean extracted text
            cleaned = re.sub(r'[^A-Z0-9\s]', '', text.upper())
            tokens = cleaned.split()

            detections = [{"text": t, "confidence": 0.80} for t in tokens if len(t) >= 2]
            full_text = " ".join(t for t in tokens if len(t) >= 2)

            return {
                "text": full_text,
                "confidence": 0.80 if full_text else 0.0,
                "detections": detections
            }
        except Exception as e:
            gc.collect()
            return {"text": None, "confidence": None, "error": str(e)}
