"""Built-in job handlers: index and storage maintenance (no network)."""

from typing import Any

from sqlalchemy import select

from app.jobs.context import JobContext
from app.jobs.service import JobKind, register_kind
from app.models import Track
from app.search.index import reindex_track


def handle_reindex_all(ctx: JobContext) -> dict[str, Any]:
    ctx.check_cancelled()
    track_ids = [row[0] for row in ctx.db.execute(select(Track.id)).all()]
    total = len(track_ids)
    for position, track_id in enumerate(track_ids):
        ctx.check_cancelled()
        ctx.set_progress(position / total if total else 1.0)
        reindex_track(ctx.db, ctx.store, track_id)
        ctx.db.commit()
    ctx.set_progress(1.0)
    return {"reindexed": total}


def handle_reconcile_storage(ctx: JobContext) -> dict[str, Any]:
    ctx.check_cancelled()
    report = ctx.store.reconcile()
    ctx.set_progress(1.0)
    return report


def register_builtin_kinds() -> None:
    register_kind(
        JobKind(name="maintenance.reindex", handler=handle_reindex_all, admin_only=True)
    )
    register_kind(
        JobKind(
            name="maintenance.reconcile_storage",
            handler=handle_reconcile_storage,
            admin_only=True,
        )
    )
