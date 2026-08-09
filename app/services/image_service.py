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
            image.error_message = error_message
            db.commit()
            db.refresh(image)
        return image

    @staticmethod
    def save_analysis_result(db: Session, analysis_data: dict) -> AnalysisResult:
        image_id = analysis_data["image_id"]
        valid_keys = {c.name for c in AnalysisResult.__table__.columns}
        filtered_data = {k: v for k, v in analysis_data.items() if k in valid_keys}

        existing = db.query(AnalysisResult).filter(AnalysisResult.image_id == image_id).first()
        if existing:
            for key, value in filtered_data.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            return existing

        analysis = AnalysisResult(**filtered_data)
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
        from sqlalchemy.orm import joinedload
        query = db.query(Image).options(joinedload(Image.analysis_result))
        if status_filter:
            if status_filter == ImageStatus.PENDING:
                query = query.filter(Image.status.in_([ImageStatus.PENDING, ImageStatus.PROCESSING]))
            else:
                query = query.filter(Image.status == status_filter)
        total = query.count()
        items = query.order_by(Image.created_at.desc()).offset(skip).limit(limit).all()

        response_items = []
        for img in items:
            item_dict = {
                "id": img.id,
                "original_filename": img.original_filename,
                "stored_filename": img.stored_filename,
                "file_path": img.file_path,
                "content_type": img.content_type,
                "file_size": img.file_size,
                "width": img.width,
                "height": img.height,
                "sha256_hash": img.sha256_hash,
                "status": img.status,
                "error_message": img.error_message,
                "overall_score": img.analysis_result.overall_score if img.analysis_result else None,
                "plate_text": img.analysis_result.plate_text if img.analysis_result else None,
                "plate_valid": img.analysis_result.plate_valid if img.analysis_result else None,
                "created_at": img.created_at,
                "updated_at": img.updated_at
            }
            response_items.append(item_dict)

        return response_items, total

    @staticmethod
    def delete_image(db: Session, image_id: UUID) -> bool:
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            return False
        db.delete(image)
        db.commit()
        return True
