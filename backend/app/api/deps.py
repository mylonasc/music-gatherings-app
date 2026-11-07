"""Shared FastAPI dependencies: DB sessions, auth, CSRF, rate limits."""

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuthSession, User
from app.storage.local import LocalObjectStore


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_store(request: Request) -> LocalObjectStore:
    store: LocalObjectStore = request.app.state.object_store
    return store


def get_db(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _session_cookie(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def get_current_session(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> tuple[AuthSession, User]:
    from app.core.auth import get_session_user

    token = _session_cookie(request, settings)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
    result = get_session_user(db, token)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
    request.state.auth_session = result[0]
    return result


def get_current_user(
    session_user: tuple[AuthSession, User] = Depends(get_current_session),
) -> User:
    return session_user[1]


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin required")
    return user


def verify_csrf(
    request: Request,
    session_user: tuple[AuthSession, User] = Depends(get_current_session),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """Double-submit CSRF check for cookie-authenticated mutations.

    The token is issued at login and kept in client memory (not a cookie),
    so a forged cross-site request cannot present it.
    """
    expected = session_user[0].csrf_token
    if not x_csrf_token or x_csrf_token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid CSRF token")


def check_rate_limit(
    request: Request,
    *,
    scope: str,
    key: str,
    max_attempts: int,
    window_seconds: int,
) -> None:
    limiter = request.app.state.rate_limiter
    client = request.client.host if request.client else "unknown"
    allowed = limiter.allow(
        f"{scope}:{client}:{key}", max_attempts=max_attempts, window_seconds=window_seconds
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many attempts, try again later",
        )
