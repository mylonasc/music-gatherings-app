"""Agent credential issuance and validation.

Tokens are random, shown once at creation, and stored as SHA-256 hashes.
Every use re-validates: hash match, expiry, revocation, owner active, and
the owner still belonging to the scoped crew.
"""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.models import AgentToken, CrewMembership, User
from app.models.base import utcnow_naive

TOKEN_PREFIX = "mgat_"


def mint_token() -> tuple[str, str]:
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def validate_agent_token(db: Session, presented: str) -> tuple[AgentToken, User] | None:
    if not presented.startswith(TOKEN_PREFIX):
        return None
    row = db.execute(
        select(AgentToken).where(AgentToken.token_hash == hash_token(presented))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at is not None and row.expires_at <= utcnow_naive():
        return None
    owner = db.get(User, row.user_id)
    if owner is None or owner.status != "active":
        return None
    member = db.execute(
        select(CrewMembership).where(
            CrewMembership.crew_id == row.crew_id, CrewMembership.user_id == owner.id
        )
    ).scalar_one_or_none()
    if member is None:
        return None
    row.last_used_at = utcnow_naive()
    db.flush()
    return row, owner


def revoke_token(db: Session, row: AgentToken) -> None:
    row.revoked_at = utcnow_naive()
    db.flush()
