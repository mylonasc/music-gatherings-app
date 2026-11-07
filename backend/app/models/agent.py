"""Agent credentials: revocable, scoped, read-only bearer tokens."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedOnly, Identified

AGENT_CAPABILITIES = (
    "search.read",
    "library.read",
    "jobs.read",
)


class AgentToken(Base, Identified, CreatedOnly):
    """One row per credential. Only a SHA-256 of the token is stored.

    Scope: exactly one user (owner), one crew, and an explicit capability
    list. There are no agent mutation tools in S15; capabilities gate
    future read-only additions.
    """

    __tablename__ = "agent_tokens"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    crew_id: Mapped[str] = mapped_column(
        ForeignKey("crews.id", ondelete="CASCADE"), nullable=False
    )
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
