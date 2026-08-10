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


from PIL import ImageOps


def load_image_auto_orient(file_bytes: bytes) -> tuple[bytes, np.ndarray, int, int]:
    """
    Decodes image and applies EXIF auto-orientation (e.g. mobile portrait photos).
    Returns (oriented_bytes, cv_bgr_image, width, height).

    Memory-optimized: when the image has no EXIF orientation (the common case),
    the original bytes are returned untouched and no extra decode/re-encode happens.
    """
    try:
        pil_img = PILImage.open(io.BytesIO(file_bytes))
        orientation = pil_img.getexif().get(0x0112) if hasattr(pil_img, "getexif") else None

        if orientation in (2, 3, 4, 5, 6, 7, 8):
            pil_img = ImageOps.exif_transpose(pil_img)
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            out_buf = io.BytesIO()
            pil_img.save(out_buf, format="JPEG", quality=92)
            return out_buf.getvalue(), cv_img, pil_img.width, pil_img.height

        # No orientation fix needed — return original bytes, avoid re-encode
        return file_bytes, None, pil_img.width, pil_img.height
    except Exception:
        nparr = np.frombuffer(file_bytes, np.uint8)
        cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        h, w = (cv_img.shape[0], cv_img.shape[1]) if cv_img is not None else (0, 0)
        return file_bytes, cv_img, w, h
