from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "media_pipeline_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_timeout=0.5,
    broker_connection_max_retries=1,
    result_backend_transport_options={
        "max_retries": 1,
        "interval_start": 0,
        "interval_step": 0,
        "interval_max": 0,
    },
    broker_transport_options={
        "max_retries": 1,
        "interval_start": 0,
        "interval_step": 0,
        "interval_max": 0,
        "socket_timeout": 0.5,
        "socket_connect_timeout": 0.5,
    }
)
