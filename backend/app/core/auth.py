"""Session issuance, validation, and revocation (DB-backed)."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_token, new_token
from app.models import AuthSession, User
from app.models.base import utcnow_naive


def create_session(
    db: Session, user: User, settings: Settings
) -> tuple[AuthSession, str]:
    token = new_token()
    row = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=new_token(),
        expires_at=utcnow_naive()
        + timedelta(seconds=settings.session_ttl_seconds),
    )
    db.add(row)
    db.flush()
    return row, token


def get_session_user(db: Session, token: str) -> tuple[AuthSession, User] | None:
    row = db.execute(
        select(AuthSession).where(AuthSession.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at <= utcnow_naive():
        return None
    user = db.execute(select(User).where(User.id == row.user_id)).scalar_one_or_none()
    if user is None or user.status != "active":
        return None
    return row, user


def revoke_session(db: Session, row: AuthSession) -> None:
    row.revoked_at = utcnow_naive()
    db.flush()


def revoke_user_sessions(db: Session, user_id: str) -> int:
    rows = (
        db.execute(
            select(AuthSession).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.revoked_at = utcnow_naive()
    db.flush()
    return len(rows)
