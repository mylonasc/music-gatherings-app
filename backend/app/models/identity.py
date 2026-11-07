"""Identity and crew membership schema (no auth logic here; see S03)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedOnly, Identified, Timestamped, utcnow_naive

USER_STATUS_PENDING = "pending"
USER_STATUS_ACTIVE = "active"
USER_STATUS_DISABLED = "disabled"
USER_STATUSES = (USER_STATUS_PENDING, USER_STATUS_ACTIVE, USER_STATUS_DISABLED)

CREW_ROLE_OWNER = "owner"
CREW_ROLE_ADMIN = "admin"
CREW_ROLE_MEMBER = "member"
CREW_ROLES = (CREW_ROLE_OWNER, CREW_ROLE_ADMIN, CREW_ROLE_MEMBER)

REQUEST_STATUS_PENDING = "pending"
REQUEST_STATUS_APPROVED = "approved"
REQUEST_STATUS_REJECTED = "rejected"
REQUEST_STATUSES = (REQUEST_STATUS_PENDING, REQUEST_STATUS_APPROVED, REQUEST_STATUS_REJECTED)


class User(Base, Identified, Timestamped):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=USER_STATUS_ACTIVE
    )
    is_admin: Mapped[bool] = mapped_column(nullable=False, default=False)


class Crew(Base, Identified, Timestamped):
    __tablename__ = "crews"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CrewMembership(Base, Identified, CreatedOnly):
    __tablename__ = "crew_memberships"
    __table_args__ = (UniqueConstraint("crew_id", "user_id", name="uq_membership_crew_user"),)

    crew_id: Mapped[str] = mapped_column(
        ForeignKey("crews.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=CREW_ROLE_MEMBER)


class AccessRequest(Base, Identified):
    """Join request carrying minimal personal data until a decision is made."""

    __tablename__ = "access_requests"

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    # Hash of the proposed password so an approved request can create the
    # account without ever storing a cleartext secret.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=REQUEST_STATUS_PENDING
    )
    decided_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive
    )
