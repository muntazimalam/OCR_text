from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer

_easyocr_reader = None


def get_ocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        except Exception:
            _easyocr_reader = False
    return _easyocr_reader


class OCRAnalyzer(BaseAnalyzer):
    """
    Extracts text using EasyOCR with lazy singleton model initialization.
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        reader = get_ocr_reader()
        if not reader:
            return {"text": None, "confidence": None, "error": "OCR engine unavailable"}

        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            input_target = img if img is not None else image_path

            results = reader.readtext(input_target)
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
            return {"text": None, "confidence": None, "error": str(e)}
