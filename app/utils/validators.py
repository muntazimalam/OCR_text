from fastapi import HTTPException, UploadFile, status
from app.core.config import settings
from app.utils.file_utils import ALLOWED_MIME_TYPES, validate_image_bytes

_CHUNK_SIZE = 1024 * 1024


async def read_upload_with_size_limit(file: UploadFile) -> bytes:
    """
    Reads an upload in bounded chunks so an oversized file is rejected
    before its full contents are buffered in memory.
    """
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed limit of {settings.MAX_FILE_SIZE_MB}MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


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

    # Never trust the client-declared MIME type — verify against the actual
    # bytes. The detected type is what gets persisted and served.
    is_valid, detected_mime, (width, height) = validate_image_bytes(file_bytes)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type or corrupted content. Allowed types: " + ", ".join(ALLOWED_MIME_TYPES)
        )
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{detected_mime}'. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    return detected_mime, width, height
