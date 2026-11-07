from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.access_requests import router as access_requests_router
from app.api.v1.artifacts import router as artifacts_router
from app.api.v1.auth import router as auth_router
from app.api.v1.crews import router as crews_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.library import router as library_router
from app.api.v1.online import router as online_router
from app.api.v1.search import router as search_router
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.quotas import UserQuotaTracker
from app.core.rate_limit import RateLimiter
from app.jobs.handlers import register_builtin_kinds
from app.jobs.online import register_online_kinds
from app.storage.local import LocalObjectStore


def create_app() -> FastAPI:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    app = FastAPI(title="Music Gatherings API", version=settings.app_version)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.rate_limiter = RateLimiter()
    app.state.quota_tracker = UserQuotaTracker()
    app.state.object_store = LocalObjectStore(
        settings.data_dir, max_bytes=settings.max_object_bytes
    )
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(health_router, tags=["health"])
    app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
    app.include_router(access_requests_router, prefix="/api/v1", tags=["access"])
    app.include_router(crews_router, prefix="/api/v1", tags=["crews"])
    app.include_router(jobs_router, prefix="/api/v1", tags=["jobs"])
    app.include_router(online_router, prefix="/api/v1", tags=["online"])
    app.include_router(library_router, prefix="/api/v1", tags=["library"])
    app.include_router(search_router, prefix="/api/v1", tags=["search"])
    app.include_router(artifacts_router, prefix="/api/v1", tags=["artifacts"])
    register_builtin_kinds()
    register_online_kinds()
    return app


app = create_app()
