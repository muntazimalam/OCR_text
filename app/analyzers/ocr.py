import gc
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer

_easyocr_reader = None


def get_ocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import torch
            torch.set_grad_enabled(False)
            import easyocr
            # Initialize CPU reader with low-memory configuration
            _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception:
            _easyocr_reader = False
    return _easyocr_reader


class OCRAnalyzer(BaseAnalyzer):
    """
    Extracts text using EasyOCR with ultra-lightweight memory and speed optimizations for 512MB RAM environments.
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        reader = get_ocr_reader()
        if not reader:
            return {"text": None, "confidence": None, "error": "OCR engine unavailable"}

        try:
            import cv2
            import numpy as np
            import torch

            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is not None:
                h, w = img.shape[:2]
                # Downscale to 640px max for ultra-fast CPU inference and 10MB RAM limit
                if max(h, w) > 640:
                    scale = 640.0 / max(h, w)
                    img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                input_target = img
            else:
                input_target = image_path

            with torch.no_grad():
                # canvas_size=640, max_size=640 limits PyTorch intermediate tensors to ~10MB RAM
                results = reader.readtext(input_target, canvas_size=640, max_size=640)

            gc.collect()

            if not results:
                return {"text": "", "confidence": 0.0, "detections": []}

            extracted_texts = []
            confidences = []
            detections = []

            for bbox, text, prob in results:
                extracted_texts.append(text)
                confidences.append(float(prob))
                detections.append({
                    "text": text,
                    "confidence": round(float(prob), 2)
                })

            full_text = " ".join(extracted_texts)
            avg_confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0

            return {
                "text": full_text,
                "confidence": round(avg_confidence, 2),
                "detections": detections
            }
        except Exception as e:
            gc.collect()
            return {"text": None, "confidence": None, "error": str(e)}
