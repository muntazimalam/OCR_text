import cv2
import numpy as np
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer


class BrightnessAnalyzer(BaseAnalyzer):
    """
    Calculates mean grayscale intensity (brightness) and standard deviation (contrast).
    Brightness heuristics:
      0-40  : very_dark
      40-80 : low_light
      80-180: acceptable
      180-220: bright
      220+  : overexposed
    Contrast heuristics (std dev of pixel values):
      < 20  : very_low (flat / no detail)
      20-50 : low
      50-80 : acceptable
      > 80  : high
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"score": 0.0, "status": "unknown", "contrast_score": 0.0, "contrast_status": "unknown", "error": "Image decode failed"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        contrast = float(gray.std())

        if brightness < 40:
            status_str = "very_dark"
        elif brightness < 80:
            status_str = "low_light"
        elif brightness <= 180:
            status_str = "acceptable"
        elif brightness <= 220:
            status_str = "bright"
        else:
            status_str = "overexposed"

        if contrast < 20:
            contrast_status = "very_low"
        elif contrast < 50:
            contrast_status = "low"
        elif contrast <= 80:
            contrast_status = "acceptable"
        else:
            contrast_status = "high"

        return {
            "score": round(brightness, 2),
            "status": status_str,
            "contrast_score": round(contrast, 2),
            "contrast_status": contrast_status
        }
