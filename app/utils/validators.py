from fastapi import HTTPException, UploadFile, status
from app.core.config import settings
from app.utils.file_utils import ALLOWED_MIME_TYPES, validate_image_bytes


def validate_uploaded_file(file: UploadFile, file_bytes: bytes) -> tuple[str, int, int]:
    """
    Validates file size, MIME type, and decodability.
    Returns (content_type, width, height).
    """
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed limit of {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.content_type}'. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    is_valid, detected_mime, (width, height) = validate_image_bytes(file_bytes)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content is corrupted or not a valid image format"
        )
        
    return detected_mime, width, height
