from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.image import ImageStatus


class ImageBase(BaseModel):
    original_filename: str
    content_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    sha256_hash: str


class ImageCreate(ImageBase):
    stored_filename: str
    file_path: str


class ImageStatusResponse(BaseModel):
    id: UUID
    status: ImageStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageResponse(ImageBase):
    id: UUID
    stored_filename: str
    file_path: str
    status: ImageStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageListResponse(BaseModel):
    total: int
    items: list[ImageResponse]

