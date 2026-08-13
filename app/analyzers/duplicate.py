import io
import imagehash
from PIL import Image as PILImage
from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer


class DuplicateAnalyzer(BaseAnalyzer):
    """
    Perceptual hash computation (phash) for near-duplicate detection.
    """
    def compute_phash(self, file_bytes: bytes) -> str:
        try:
            pil_img = PILImage.open(io.BytesIO(file_bytes))
            phash = imagehash.phash(pil_img)
            return str(phash)
        except Exception:
            return ""

    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        phash_str = self.compute_phash(file_bytes)
        return {
            "phash": phash_str,
            "is_duplicate": False,
            "duplicate_of": None,
            "similarity": None
        }
