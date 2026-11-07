"""Login, logout, and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    check_rate_limit,
    get_current_session,
    get_db,
    get_settings,
    verify_csrf,
)
from app.api.v1.schemas import LoginRequest, LoginResponse, UserOut
from app.core.auth import create_session, revoke_session
from app.core.config import Settings
from app.core.security import verify_password
from app.models import AuditEvent, AuthSession, User

router = APIRouter()


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_admin=user.is_admin,
    )


def _audit(db: Session, action: str, user_id: str | None) -> None:
    db.add(AuditEvent(actor_user_id=user_id, action=action))
    db.flush()


@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    check_rate_limit(
        request,
        scope="login",
        key=body.username.strip().lower(),
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
    )
    username = body.username.strip()
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    bad_password = user is None or not verify_password(user.password_hash, body.password)
    if user is None or user.status != "active" or bad_password:
        _audit(db, "auth.login_failed", user.id if user else None)
        db.commit()  # failure audits must survive the error response rollback
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    row, token = create_session(db, user, settings)
    _audit(db, "auth.login", user.id)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    return LoginResponse(csrf_token=row.csrf_token, user=_user_out(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session_user: tuple[AuthSession, User] = Depends(get_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(verify_csrf),
) -> None:
    row, user = session_user
    revoke_session(db, row)
    _audit(db, "auth.logout", user.id)
    response.delete_cookie(key=settings.session_cookie_name, path="/")


@router.get("/auth/me", response_model=LoginResponse)
def me(
    session_user: tuple[AuthSession, User] = Depends(get_current_session),
) -> LoginResponse:
    row, user = session_user
    return LoginResponse(csrf_token=row.csrf_token, user=_user_out(user))
