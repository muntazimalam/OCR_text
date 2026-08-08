import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, JSON, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id = Column(Uuid(as_uuid=True), ForeignKey("images.id"), unique=True, nullable=False, index=True)
    
    blur_score = Column(Float, nullable=True)
    is_blurry = Column(Boolean, nullable=True)
    
    brightness_score = Column(Float, nullable=True)
    brightness_status = Column(String(50), nullable=True)
    
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(Uuid(as_uuid=True), nullable=True)
    
    ocr_text = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    plate_detected = Column(Boolean, default=False)
    plate_valid = Column(Boolean, default=False)
    plate_confidence = Column(Float, nullable=True)
    
    tampering_info = Column(JSON, nullable=True)
    metadata_info = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)
    issues = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    image = relationship("Image", back_populates="analysis_result")
