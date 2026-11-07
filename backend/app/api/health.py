from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "backend",
        "version": settings.app_version,
        "env": settings.app_env,
    }
