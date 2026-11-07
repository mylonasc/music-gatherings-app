"""Handler execution context: cooperative cancellation, deadlines, progress."""

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.storage.local import LocalObjectStore


class JobCancelled(Exception):
    pass


class JobTimedOut(Exception):
    pass


@dataclass
class JobContext:
    job_id: str
    kind: str
    payload: dict[str, Any]
    db: Session
    store: LocalObjectStore
    settings: Settings
    deadline_monotonic: float
    _cancelled: bool = field(default=False, repr=False)

    def check_cancelled(self) -> None:
        """Raise if the job was cancelled or its deadline passed.

        Handlers must call this at safe interruption points and, for network
        work in later slices, before each external call.
        """
        if self._cancelled:
            raise JobCancelled(f"job {self.job_id} cancelled")
        if time.monotonic() >= self.deadline_monotonic:
            raise JobTimedOut(f"job {self.job_id} exceeded its deadline")

    def set_progress(self, fraction: float, wait_reason: str | None = None) -> None:
        from app.models import Job

        row = self.db.get(Job, self.job_id)
        if row is None:
            raise JobCancelled(f"job {self.job_id} disappeared")
        if row.cancel_requested:
            self._cancelled = True
            self.check_cancelled()
        row.progress = max(0.0, min(1.0, fraction))
        row.wait_reason = wait_reason
        # Commit immediately: handlers must never hold a write transaction
        # across network or CPU-heavy work (see S06 acceptance).
        self.db.commit()
