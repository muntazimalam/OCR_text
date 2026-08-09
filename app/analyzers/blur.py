import cv2
import numpy as np
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer


class BlurAnalyzer(BaseAnalyzer):
    """
    Measures image sharpness using a dual-metric approach:
    1. Laplacian variance (frequency energy in the whole image)
    2. Tenengrad variance (Sobel edge strength — more robust to uniform regions)
    Final score is the mean of both. Heuristics:
      < 50  : blurry
      50-100: questionable
      > 100 : sharp / acceptable
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"score": 0.0, "laplacian_score": 0.0, "tenengrad_score": 0.0, "is_blurry": True, "error": "Image decode failed"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Metric 1: Laplacian Variance
        laplacian_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Metric 2: Tenengrad Variance (Sobel-based sharpness)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        tenengrad_score = float(np.mean(sobel_x ** 2 + sobel_y ** 2))

        # Normalize tenengrad to comparable scale as laplacian (empirically /100)
        tenengrad_normalized = tenengrad_score / 100.0

        # Composite score: weighted average
        composite_score = (laplacian_score * 0.6) + (tenengrad_normalized * 0.4)
        is_blurry = composite_score < 100.0

        return {
            "score": round(composite_score, 2),
            "laplacian_score": round(laplacian_score, 2),
            "tenengrad_score": round(tenengrad_normalized, 2),
            "is_blurry": is_blurry
        }
