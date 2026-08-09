import cv2
import numpy as np
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer


class PhotoOfPhotoAnalyzer(BaseAnalyzer):
    """
    Detects heuristics of a photo taken of a digital screen or printed photograph.
    Combines 2D FFT (Fast Fourier Transform) frequency domain Moiré pattern detection
    with EXIF camera indicators.
    """
    def analyze(self, image_path: str, file_bytes: bytes, metadata_result: Dict[str, Any] = None) -> Dict[str, Any]:
        is_photo_of_photo = False
        confidence = 0.0
        moire_ratio = 0.0

        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # Compute 2D Fast Fourier Transform
                f = np.fft.fft2(gray)
                fshift = np.fft.fftshift(f)
                magnitude = 20 * np.log(np.abs(fshift) + 1e-8)

                # Analyze high-frequency energy ratio outside central low-frequency area
                h, w = gray.shape
                cy, cx = h // 2, w // 2
                r = min(h, w) // 10
                
                # Zero out low frequencies around center
                magnitude_high_freq = np.copy(magnitude)
                cv2.circle(magnitude_high_freq, (cx, cy), r, 0, -1)

                # Ratio of high-frequency periodic peak energy to total magnitude
                high_energy_peaks = float(np.sum(magnitude_high_freq > (magnitude.mean() * 2.5)))
                total_pixels = h * w
                moire_ratio = round(high_energy_peaks / total_pixels, 4)

                # Moiré grid frequency threshold
                if moire_ratio > 0.015:
                    is_photo_of_photo = True
                    confidence = min(0.70 + (moire_ratio * 10), 0.95)

            # Combine with metadata indicators (e.g. camera photo of high screenshot resolution)
            if metadata_result:
                has_exif_camera = bool(metadata_result.get("camera_make") or metadata_result.get("camera_model"))
                screenshot_prob = metadata_result.get("screenshot_probability", 0.0)

                # If camera EXIF exists but image matches standard screen aspect ratios with moiré noise
                if has_exif_camera and screenshot_prob >= 0.4:
                    is_photo_of_photo = True
                    confidence = max(confidence, 0.80)

            return {
                "is_photo_of_photo": is_photo_of_photo,
                "confidence": round(confidence, 2),
                "moire_index": moire_ratio
            }
        except Exception:
            return {
                "is_photo_of_photo": False,
                "confidence": 0.0,
                "moire_index": 0.0
            }
