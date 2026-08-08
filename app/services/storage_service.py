import os
import uuid
from datetime import datetime, timezone
from app.core.config import settings


class StorageService:
    @staticmethod
    def save_image(file_bytes: bytes, original_filename: str, image_id: uuid.UUID) -> tuple[str, str]:
        """
        Saves file under uploads/YYYY/MM/UUID.ext.
        Returns (stored_filename, file_path).
        """
        ext = os.path.splitext(original_filename)[1].lower()
        if not ext or ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"

        now = datetime.now(timezone.utc)
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")

        relative_dir = os.path.join(settings.UPLOAD_DIR, year_str, month_str)
        os.makedirs(relative_dir, exist_ok=True)

        stored_filename = f"{image_id}{ext}"
        file_path = os.path.join(relative_dir, stored_filename)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        return stored_filename, file_path

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """
        Deletes image file from disk if it exists.
        """
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception:
            pass
        return False
