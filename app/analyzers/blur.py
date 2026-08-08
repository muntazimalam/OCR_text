import cv2
import numpy as np
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer


class BlurAnalyzer(BaseAnalyzer):
    """
    Measures Laplacian variance to detect image blur.
    Heuristics:
    < 50: blurry
    50-100: questionable
    > 100: sharp / acceptable
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"score": 0.0, "is_blurry": True, "error": "Image decode failed"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_blurry = score < 100.0

        return {
            "score": round(score, 2),
            "is_blurry": is_blurry
        }
