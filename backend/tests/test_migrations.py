"""Alembic migrations apply cleanly to an empty database and round-trip."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {
    "access_requests",
    "artifact_derivations",
    "artifacts",
    "audit_events",
    "crew_memberships",
    "crew_tracks",
    "crews",
    "genres",
    "jobs",
    "processing_profiles",
    "source_records",
    "track_genres",
    "track_versions",
    "track_votes",
    "tracks",
    "users",
}


def run_alembic(db_path: Path, *args: str) -> None:
    env = dict(os.environ)
    env["MUSIC_GATHERINGS_DATABASE_URL"] = f"sqlite:///{db_path}"
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def table_names(db_path: Path) -> set[str]:
    con = sqlite3.connect(str(db_path))
    try:
        return {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'alembic%'"
            )
        }
    finally:
        con.close()


def test_migration_upgrade_downgrade_cycle(tmp_path):  # type: ignore[no-untyped-def]
    db_path = tmp_path / "migrated.db"
    run_alembic(db_path, "upgrade", "head")
    assert table_names(db_path) >= EXPECTED_TABLES
    run_alembic(db_path, "downgrade", "base")
    assert table_names(db_path) == set()
    run_alembic(db_path, "upgrade", "head")
    assert table_names(db_path) >= EXPECTED_TABLES
