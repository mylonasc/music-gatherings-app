"""track search fts

Revision ID: 22c0e68d4276
Revises: ab1de1a2d8e1
Create Date: 2026-11-07

Application-managed FTS5 index (one row per track). The DDL is frozen here;
app/search/index.py reuses the same statement with IF NOT EXISTS for tests
and runtime safety.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "22c0e68d4276"
down_revision: str | Sequence[str] | None = "ab1de1a2d8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS track_search_fts USING fts5(
            track_id UNINDEXED,
            title,
            artist,
            genres,
            lyrics,
            tokenize='unicode61'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS track_search_fts")
