import hashlib
import io
import cv2
import numpy as np
from PIL import Image as PILImage

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def calculate_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def validate_image_bytes(file_bytes: bytes) -> tuple[bool, str, tuple[int, int]]:
    """
    Decodes image using PIL & OpenCV to verify it's a valid image.
    Returns (is_valid, content_type, (width, height)).
    """
    try:
        pil_img = PILImage.open(io.BytesIO(file_bytes))
        pil_img.verify()
        
        pil_img = PILImage.open(io.BytesIO(file_bytes))
        width, height = pil_img.size
        format_name = pil_img.format.lower() if pil_img.format else ""
        
        mime_type = f"image/{format_name}" if format_name in {"jpeg", "png", "webp"} else "image/jpeg"
        if format_name == "jpg":
            mime_type = "image/jpeg"
            
        nparr = np.frombuffer(file_bytes, np.uint8)
        cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if cv_img is None:
            return False, "", (0, 0)

        return True, mime_type, (width, height)
    except Exception:
        return False, "", (0, 0)
