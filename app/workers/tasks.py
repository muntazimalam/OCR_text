import gc
from uuid import UUID
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.image import ImageStatus
from app.services.image_service import ImageService
from app.services.analysis_service import AnalysisService
from app.core.logging import logger


def run_image_processing_standalone(image_id_str: str) -> dict:
    """
    Runs the full analysis pipeline for a single image.
    Fails immediately on any error — no retries, no second chances.
    """
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

        if image.status == ImageStatus.FAILED:
            logger.info("image_already_failed", image_id=image_id_str)
            return {"status": "failed", "image_id": image_id_str, "error": image.error_message}

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
            logger.info("processing_failed_validation", image_id=image_id_str, error=err_msg)
            return {"status": "failed", "image_id": image_id_str, "error": err_msg}
        else:
            ImageService.update_image_status(db, image_id, ImageStatus.COMPLETED)
            logger.info("processing_completed", image_id=image_id_str)
            return {"status": "completed", "image_id": image_id_str}

    except Exception as exc:
        # Fail immediately — mark as FAILED, no retry
        logger.error("processing_crashed", image_id=image_id_str, error=str(exc))
        try:
            db.rollback()
            ImageService.update_image_status(
                db, image_id, ImageStatus.FAILED, error_message=f"Processing error: {str(exc)}"
            )
        except Exception:
            pass
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
        gc.collect()


@celery_app.task(bind=True, max_retries=0)
def process_image(self, image_id_str: str):
    """
    Celery task wrapper. max_retries=0 means fail immediately on first error.
    """
    return run_image_processing_standalone(image_id_str)
