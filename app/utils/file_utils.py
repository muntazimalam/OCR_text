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
    Validates image header/size using PIL (lazy, no full pixel decode).
    Returns (is_valid, content_type, (width, height)).
    Memory-optimized: avoids a full-res cv2 decode in the request thread.
    """
    try:
        pil_img = PILImage.open(io.BytesIO(file_bytes))
        width, height = pil_img.size
        format_name = pil_img.format.lower() if pil_img.format else ""

        pil_img.verify()

        mime_type = f"image/{format_name}" if format_name in {"jpeg", "png", "webp"} else "image/jpeg"
        if format_name == "jpg":
            mime_type = "image/jpeg"

        return True, mime_type, (width, height)
    except Exception:
        return False, "", (0, 0)


def downscale_image_bytes(file_bytes: bytes, max_dim: int = 1600, quality: int = 90) -> bytes:
    """
    Downscales (only when larger than max_dim) and re-encodes image bytes so
    every analyzer works on a bounded-size image instead of decoding the full
    original (e.g. a 12MP photo = ~36MB per decode) on each pipeline stage.
    Returns the original bytes untouched when already small enough.
    """
    try:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return file_bytes
        h, w = img.shape[:2]
        if max(h, w) <= max_dim:
            return file_bytes
        scale = max_dim / float(max(h, w))
        small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else file_bytes
    except Exception:
        return file_bytes


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
