import io
from PIL import Image as PILImage, ExifTags
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer

COMMON_SCREENSHOT_RESOLUTIONS = {
    (1080, 1920), (1080, 2340), (1080, 2400),
    (1170, 2532), (1284, 2778), (1440, 3040),
    (1440, 3200), (1920, 1080), (2560, 1440)
}


class MetadataAnalyzer(BaseAnalyzer):
    """
    Extracts EXIF metadata (camera, software, timestamp) and assesses screenshot probability.
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        has_exif = False
        camera_make = None
        camera_model = None
        software = None
        screenshot_prob = 0.0

        try:
            pil_img = PILImage.open(io.BytesIO(file_bytes))
            width, height = pil_img.size

            exif_raw = pil_img._getexif() if hasattr(pil_img, "_getexif") else None
            if exif_raw:
                exif_data = {
                    ExifTags.TAGS.get(k, k): v
                    for k, v in exif_raw.items()
                    if k in ExifTags.TAGS
                }
                has_exif = True
                camera_make = str(exif_data.get("Make", "")).strip() or None
                camera_model = str(exif_data.get("Model", "")).strip() or None
                software = str(exif_data.get("Software", "")).strip() or None

            if not has_exif:
                screenshot_prob += 0.4
            if (width, height) in COMMON_SCREENSHOT_RESOLUTIONS:
                screenshot_prob += 0.4
            if software and any(term in software.lower() for term in ["screenshot", "capture", "snagit", "snipping"]):
                screenshot_prob += 0.5

            screenshot_prob = min(screenshot_prob, 1.0)

            return {
                "has_exif": has_exif,
                "camera_make": camera_make,
                "camera_model": camera_model,
                "software": software,
                "screenshot_probability": round(screenshot_prob, 2)
            }
        except Exception:
            return {
                "has_exif": False,
                "camera_make": None,
                "camera_model": None,
                "software": None,
                "screenshot_probability": 0.5
            }
