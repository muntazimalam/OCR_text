import time
from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import SessionLocal, engine
from app.core.config import settings

router = APIRouter()
_START_TIME = time.time()


@router.get("/health", summary="Check system health")
def check_health():
    db_status = "ok"
    db_dialect = engine.dialect.name
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    redis_status = "unavailable"
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
        if r.ping():
            redis_status = "connected"
    except Exception:
        redis_status = "fallback_sync_mode"

    uptime_seconds = round(time.time() - _START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "database": {
            "status": db_status,
            "dialect": db_dialect,
            "persistence": (
                "durable (managed PostgreSQL — data survives restarts)"
                if engine.dialect.name == "postgresql"
                else "ephemeral local file (erased on instance restart — configure DATABASE_URL to PostgreSQL to persist data)"
            )
        },
        "task_queue": {
            "redis_status": redis_status,
            "mode": "async" if redis_status == "connected" else "sync_fallback"
        },
        "analyzers": [
            "blur (Laplacian + Tenengrad)",
            "brightness + contrast",
            "duplicate (SHA-256)",
            "ocr (RapidOCR PP-OCRv4 + Tesseract fallback)",
            "number_plate (regex + heuristic)",
            "metadata (EXIF)",
            "tampering",
            "photo_of_photo (Moire)"
        ]
    }
