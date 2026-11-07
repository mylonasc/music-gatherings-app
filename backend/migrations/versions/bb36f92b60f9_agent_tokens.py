"""agent tokens

Revision ID: bb36f92b60f9
Revises: 58a338ce3b5c
Create Date: 2026-11-07

Scoped read-only agent credentials (see S15).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bb36f92b60f9"
down_revision: str | Sequence[str] | None = "58a338ce3b5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tokens",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("crew_id", sa.String(length=32), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["crew_id"], ["crews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_agent_tokens_user_id"), "agent_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_tokens_user_id"), table_name="agent_tokens")
    op.drop_table("agent_tokens")
