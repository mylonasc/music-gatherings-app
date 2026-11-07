"""job leases and cancellation

Revision ID: 58a338ce3b5c
Revises: 22c0e68d4276
Create Date: 2026-11-07

Lease-based claiming with restart recovery, cooperative cancellation, and
retry backoff scheduling.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "58a338ce3b5c"
down_revision: str | Sequence[str] | None = "22c0e68d4276"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("worker_id", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column("jobs", sa.Column("available_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "available_at")
    op.drop_column("jobs", "cancel_requested")
    op.drop_column("jobs", "lease_expires_at")
    op.drop_column("jobs", "worker_id")
