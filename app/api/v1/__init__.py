from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.images import router as images_router
from app.api.v1.visits import router as visits_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(images_router)
api_router.include_router(visits_router)
