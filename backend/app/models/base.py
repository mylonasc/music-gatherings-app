"""Declarative base and shared column helpers."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Identified:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive
    )


class CreatedOnly:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_naive
    )
