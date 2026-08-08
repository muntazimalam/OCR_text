from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.image import Image, ImageStatus
from app.models.analysis import AnalysisResult


class ImageService:
    @staticmethod
    def create_image(
        db: Session,
        image_id: UUID,
        original_filename: str,
        stored_filename: str,
        file_path: str,
        content_type: str,
        file_size: int,
        width: Optional[int],
        height: Optional[int],
        sha256_hash: str,
    ) -> Image:
        image = Image(
            id=image_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=file_path,
            content_type=content_type,
            file_size=file_size,
            width=width,
            height=height,
            sha256_hash=sha256_hash,
            status=ImageStatus.PENDING,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image

    @staticmethod
    def get_image_by_id(db: Session, image_id: UUID) -> Optional[Image]:
        return db.query(Image).filter(Image.id == image_id).first()

    @staticmethod
    def update_image_status(db: Session, image_id: UUID, status: ImageStatus, error_message: Optional[str] = None) -> Optional[Image]:
        image = db.query(Image).filter(Image.id == image_id).first()
        if image:
            image.status = status
            if error_message:
                image.error_message = error_message
            db.commit()
            db.refresh(image)
        return image

    @staticmethod
    def save_analysis_result(db: Session, analysis_data: dict) -> AnalysisResult:
        image_id = analysis_data["image_id"]
        existing = db.query(AnalysisResult).filter(AnalysisResult.image_id == image_id).first()
        if existing:
            for key, value in analysis_data.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            return existing

        analysis = AnalysisResult(**analysis_data)
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis

    @staticmethod
    def get_analysis_result_by_image_id(db: Session, image_id: UUID) -> Optional[AnalysisResult]:
        return db.query(AnalysisResult).filter(AnalysisResult.image_id == image_id).first()

    @staticmethod
    def find_duplicate_by_hash(db: Session, sha256_hash: str, current_image_id: UUID) -> Optional[Image]:
        return db.query(Image).filter(
            Image.sha256_hash == sha256_hash,
            Image.id != current_image_id,
            Image.status == ImageStatus.COMPLETED
        ).first()

    @staticmethod
    def get_all_images(db: Session, skip: int = 0, limit: int = 20, status_filter: Optional[ImageStatus] = None):
        query = db.query(Image)
        if status_filter:
            query = query.filter(Image.status == status_filter)
        total = query.count()
        items = query.order_by(Image.created_at.desc()).offset(skip).limit(limit).all()
        return items, total

    @staticmethod
    def delete_image(db: Session, image_id: UUID) -> bool:
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            return False
        db.delete(image)
        db.commit()
        return True
