from uuid import UUID
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.image import ImageStatus
from app.services.image_service import ImageService
from app.services.analysis_service import AnalysisService
from app.core.logging import logger


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_image(self, image_id_str: str):
    image_id = UUID(image_id_str)
    db = SessionLocal()

    try:
        image = ImageService.get_image_by_id(db, image_id)
        if not image:
            logger.error("image_not_found_for_processing", image_id=image_id_str)
            return {"status": "failed", "error": "Image not found"}

        if image.status == ImageStatus.COMPLETED:
            logger.info("image_already_processed", image_id=image_id_str)
            return {"status": "completed", "image_id": image_id_str}

        ImageService.update_image_status(db, image_id, ImageStatus.PROCESSING)
        logger.info("processing_started", image_id=image_id_str)

        analysis_service = AnalysisService()
        analysis_data = analysis_service.run_pipeline(
            db, image_id, image.file_path, image.sha256_hash
        )

        ImageService.save_analysis_result(db, analysis_data)
        
        if analysis_data.get("is_failed"):
            err_msg = analysis_data.get("error_message") or "Validation checks failed"
            ImageService.update_image_status(db, image_id, ImageStatus.FAILED, error_message=err_msg)
            logger.info("processing_completed_with_validation_failure", image_id=image_id_str, error=err_msg)
            return {"status": "failed", "image_id": image_id_str, "error": err_msg}
        else:
            ImageService.update_image_status(db, image_id, ImageStatus.COMPLETED)
            logger.info("processing_completed", image_id=image_id_str)
            return {"status": "completed", "image_id": image_id_str}

    except Exception as exc:
        logger.error("processing_failed", image_id=image_id_str, error=str(exc))
        db.rollback()

        if self.request.retries < self.max_retries:
            ImageService.update_image_status(
                db, image_id, ImageStatus.PENDING, error_message=f"Retrying... ({str(exc)})"
            )
            db.close()
            raise self.retry(exc=exc)
        else:
            ImageService.update_image_status(
                db, image_id, ImageStatus.FAILED, error_message=f"Processing failed after max retries: {str(exc)}"
            )
            return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
