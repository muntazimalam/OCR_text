from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import SessionLocal, engine
from app.core.config import settings

router = APIRouter()


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

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "database": {
            "status": db_status,
            "dialect": db_dialect
        },
        "task_queue": {
            "redis_status": redis_status,
            "mode": "async" if redis_status == "connected" else "sync_fallback"
        }
    }
