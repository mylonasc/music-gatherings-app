from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Music Gatherings API", version=settings.app_version)
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(health_router, tags=["health"])
    return app


app = create_app()
