from fastapi import APIRouter

from app.routes.cameras import router as cameras_router
from app.routes.health import router as health_router
from app.routes.media import router as media_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(cameras_router)
api_router.include_router(media_router)
