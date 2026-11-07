"""Worker entrypoint: claim and run jobs until stopped.

Usage: ``python -m app.worker [--once]``. ``--once`` processes a single
available job (or exits 0 when idle); used by tests and one-shot ops runs.
"""

import argparse
import logging
import signal
import time

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory, session_scope
from app.jobs.handlers import register_builtin_kinds
from app.jobs.online import register_online_kinds
from app.jobs.service import claim_next_available, new_worker_id, run_claimed_job
from app.models import Job
from app.storage.local import LocalObjectStore

log = logging.getLogger("music_gatherings.worker")


def work_once(worker_id: str) -> bool:
    """Claim and run a single job. Returns True if a job was processed."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        factory = create_session_factory(engine)
        store = LocalObjectStore(settings.data_dir, max_bytes=settings.max_object_bytes)
        with session_scope(factory) as db:
            job = claim_next_available(db, worker_id=worker_id, settings=settings)
            if job is None:
                return False
            job_id, kind = job.id, job.kind
        log.info("worker=%s claimed job=%s kind=%s", worker_id, job_id, kind)
        with session_scope(factory) as db:
            claimed = db.get(Job, job_id)
            assert claimed is not None
            run_claimed_job(db, store, settings, claimed)
            log.info("worker=%s finished job=%s status=%s", worker_id, job_id, claimed.status)
            return True
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Music Gatherings job worker")
    parser.add_argument("--once", action="store_true", help="process one job then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    register_builtin_kinds()
    register_online_kinds()
    worker_id = new_worker_id()
    stop = False

    def _handle_signal(signum, _frame):  # type: ignore[no-untyped-def]
        nonlocal stop
        log.info("worker=%s received signal %s, stopping", worker_id, signum)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    log.info("worker=%s starting", worker_id)
    while not stop:
        try:
            processed = work_once(worker_id)
        except Exception:  # noqa: BLE001 - worker must survive handler crashes
            log.exception("worker=%s unexpected error", worker_id)
            processed = False
        if args.once:
            return 0
        if not processed:
            time.sleep(settings.worker_poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
