from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.models.image import ImageStatus


class IssueSchema(BaseModel):
    type: str
    severity: str  # low, medium, high
    confidence: float
    description: str


class BlurAnalysis(BaseModel):
    score: float
    is_blurry: bool


class BrightnessAnalysis(BaseModel):
    score: float
    status: str


class DuplicateAnalysis(BaseModel):
    is_duplicate: bool
    duplicate_of: Optional[UUID] = None


class OCRAnalysis(BaseModel):
    text: Optional[str] = None
    confidence: Optional[float] = None


class NumberPlateAnalysis(BaseModel):
    detected: bool
    valid: bool
    confidence: Optional[float] = None
    plate_text: Optional[str] = None


class MetadataAnalysis(BaseModel):
    has_exif: bool
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None
    screenshot_probability: float


class TamperingAnalysis(BaseModel):
    suspicious_editing: bool
    confidence: float


class DetailedAnalysisSchema(BaseModel):
    blur: Optional[BlurAnalysis] = None
    brightness: Optional[BrightnessAnalysis] = None
    duplicate: Optional[DuplicateAnalysis] = None
    ocr: Optional[OCRAnalysis] = None
    number_plate: Optional[NumberPlateAnalysis] = None
    metadata: Optional[MetadataAnalysis] = None
    tampering: Optional[TamperingAnalysis] = None


class AnalysisResultResponse(BaseModel):
    image_id: UUID
    status: ImageStatus
    analysis: Optional[DetailedAnalysisSchema] = None
    issues: List[IssueSchema] = []
    overall_score: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
