import os
import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.image import ImageStatus
from app.schemas.image import ImageStatusResponse, ImageResponse, ImageListResponse
from app.schemas.analysis import AnalysisResultResponse, DetailedAnalysisSchema
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
from app.utils.file_utils import calculate_sha256
from app.utils.validators import validate_uploaded_file
from app.workers.tasks import process_image, run_image_processing_standalone
from app.core.logging import logger

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ImageStatusResponse, summary="Upload image for processing")
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_bytes = await file.read()
    
    content_type, width, height = validate_uploaded_file(file, file_bytes)
    
    sha256_hash = calculate_sha256(file_bytes)
    image_id = uuid.uuid4()
    
    stored_filename, file_path = StorageService.save_image(file_bytes, file.filename, image_id)
    
    image_record = ImageService.create_image(
        db=db,
        image_id=image_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=file_path,
        content_type=content_type,
        file_size=len(file_bytes),
        width=width,
        height=height,
        sha256_hash=sha256_hash,
    )
    
    celery_dispatched = False
    try:
        from app.workers.celery_app import celery_app
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=0.5)
        if r.ping():
            inspector = celery_app.control.inspect(timeout=0.5)
            workers = inspector.ping() if inspector else None
            if workers:
                process_image.delay(str(image_id))
                celery_dispatched = True
    except Exception as e:
        logger.warning("celery_worker_check_failed", image_id=str(image_id), error=str(e))

    if not celery_dispatched:
        logger.info("dispatching_via_background_tasks", image_id=str(image_id))
        background_tasks.add_task(run_image_processing_standalone, str(image_id))

    return image_record


@router.get("", response_model=ImageListResponse, summary="List all processed images")
def list_images(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[ImageStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    items, total = ImageService.get_all_images(db, skip=skip, limit=limit, status_filter=status_filter)
    return ImageListResponse(total=total, items=items)


@router.get("/{image_id}/status", response_model=ImageStatusResponse, summary="Get image processing status")
def get_image_status(image_id: uuid.UUID, db: Session = Depends(get_db)):
    image = ImageService.get_image_by_id(db, image_id)
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID '{image_id}' not found"
        )
    return image


@router.get("/{image_id}/results", response_model=AnalysisResultResponse, summary="Get image processing results")
def get_image_results(image_id: uuid.UUID, db: Session = Depends(get_db)):
    image = ImageService.get_image_by_id(db, image_id)
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID '{image_id}' not found"
        )
        
    analysis = ImageService.get_analysis_result_by_image_id(db, image_id)
    
    detailed_analysis = None
    if analysis:
        tampering_data = analysis.tampering_info or {"suspicious_editing": False, "confidence": 0.0}
        ocr_conf = getattr(analysis, "ocr_confidence", None)
        
        detailed_analysis = DetailedAnalysisSchema(
            blur={"score": analysis.blur_score, "is_blurry": analysis.is_blurry} if analysis.blur_score is not None else None,
            brightness={"score": analysis.brightness_score, "status": analysis.brightness_status} if analysis.brightness_score is not None else None,
            duplicate={"is_duplicate": analysis.is_duplicate, "duplicate_of": analysis.duplicate_of},
            ocr={"text": analysis.ocr_text, "confidence": ocr_conf},
            number_plate={"detected": analysis.plate_detected, "valid": analysis.plate_valid, "confidence": analysis.plate_confidence, "plate_text": analysis.plate_text},
            metadata=analysis.metadata_info,
            tampering={"suspicious_editing": tampering_data.get("suspicious_editing", False), "confidence": tampering_data.get("confidence", 0.0)}
        )

    return AnalysisResultResponse(
        image_id=image.id,
        status=image.status,
        analysis=detailed_analysis,
        issues=analysis.issues if analysis and analysis.issues else [],
        overall_score=analysis.overall_score if analysis else None,
        error_message=image.error_message,
        created_at=analysis.created_at if analysis else image.created_at
    )


@router.post("/{image_id}/reanalyze", summary="Re-trigger image analysis pipeline")
def reanalyze_image(
    image_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    image = ImageService.get_image_by_id(db, image_id)
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID '{image_id}' not found"
        )
    ImageService.update_image_status(db, image_id, ImageStatus.PENDING, error_message=None)
    background_tasks.add_task(run_image_processing_standalone, str(image_id))
    return {"status": "reanalyzing", "image_id": str(image_id)}


@router.get("/stats", summary="Get pipeline statistics")
def get_pipeline_stats(db: Session = Depends(get_db)):
    from app.models.image import Image, ImageStatus
    from app.models.analysis import AnalysisResult
    from sqlalchemy import func

    total = db.query(Image).count()
    completed = db.query(Image).filter(Image.status == ImageStatus.COMPLETED).count()
    failed = db.query(Image).filter(Image.status == ImageStatus.FAILED).count()
    pending = db.query(Image).filter(Image.status.in_([ImageStatus.PENDING, ImageStatus.PROCESSING])).count()
    avg_score = db.query(func.avg(AnalysisResult.overall_score)).scalar()

    pass_rate = round(completed / total, 3) if total > 0 else 0.0
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "pass_rate": pass_rate,
        "average_score": round(float(avg_score), 3) if avg_score is not None else None
    }


@router.get("/{image_id}/file", summary="Serve uploaded image file")
def get_image_file(image_id: uuid.UUID, db: Session = Depends(get_db)):
    image = ImageService.get_image_by_id(db, image_id)
    if not image or not os.path.exists(image.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image file with ID '{image_id}' not found"
        )
    return FileResponse(image.file_path, media_type=image.content_type, filename=image.original_filename)


@router.delete("/{image_id}", status_code=status.HTTP_200_OK, summary="Delete an image record and file")
def delete_image(image_id: uuid.UUID, db: Session = Depends(get_db)):
    image = ImageService.get_image_by_id(db, image_id)
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID '{image_id}' not found"
        )
    file_path = image.file_path
    ImageService.delete_image(db, image_id)
    StorageService.delete_file(file_path)
    return {"status": "deleted", "image_id": str(image_id)}
