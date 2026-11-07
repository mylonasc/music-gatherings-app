from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.access_requests import router as access_requests_router
from app.api.v1.auth import router as auth_router
from app.api.v1.crews import router as crews_router
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.rate_limit import RateLimiter


def create_app() -> FastAPI:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    app = FastAPI(title="Music Gatherings API", version=settings.app_version)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.rate_limiter = RateLimiter()
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(health_router, tags=["health"])
    app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
    app.include_router(access_requests_router, prefix="/api/v1", tags=["access"])
    app.include_router(crews_router, prefix="/api/v1", tags=["crews"])
    return app


app = create_app()
