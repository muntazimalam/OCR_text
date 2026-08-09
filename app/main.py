import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import engine, Base
from app.core.logging import setup_logging, logger
import app.models  # Ensure models are imported for create_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("app_startup", app_name=settings.APP_NAME)
    
    # Auto-create tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
        # Migration check: Add contrast_score column if missing in pre-existing database
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE analysis_results ADD COLUMN contrast_score FLOAT"))
                conn.commit()
                logger.info("database_migration_added_contrast_score")
            except Exception:
                pass  # Column already exists
        logger.info("database_tables_initialized")
    except Exception as e:
        logger.error("database_init_error", error=str(e))
        
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs("app/static", exist_ok=True)
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for asynchronous vehicle image processing and analysis pipeline",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount uploads directory for viewing processed images
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Mount static directory for UI assets
if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", summary="Dashboard UI & Root Information")
def root():
    index_path = os.path.join("app", "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs_url": "/docs"
    }


@app.get("/api/info", summary="API info endpoint")
def api_info():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs_url": "/docs"
    }