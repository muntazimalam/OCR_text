import cv2
import numpy as np
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer


class BrightnessAnalyzer(BaseAnalyzer):
    """
    Calculates mean grayscale intensity.
    Heuristics:
    0-40: very_dark
    40-80: low_light
    80-180: acceptable
    180-220: bright
    220+: overexposed
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"score": 0.0, "status": "unknown", "error": "Image decode failed"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())

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

        return {
            "score": round(brightness, 2),
            "status": status_str
        }
