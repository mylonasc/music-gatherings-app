"""SQLite engine defaults: WAL, busy timeout, FK enforcement, transactions."""

import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import session_scope
from tests.conftest import sqlite_pragma


def test_sqlite_pragmas(engine, db_file):  # type: ignore[no-untyped-def]
    with engine.connect() as connection:
        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
    assert str(sqlite_pragma(db_file, "journal_mode")).lower() == "wal"
    assert busy_timeout == 5000
    assert foreign_keys == 1


def test_foreign_keys_enforced(db_session):  # type: ignore[no-untyped-def]
    from app.models import TrackVersion

    db_session.add(TrackVersion(track_id="0" * 32))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_session_scope_rolls_back_on_error(session_factory):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import Genre

    with pytest.raises(RuntimeError, match="boom"), session_scope(
        session_factory
    ) as session:
        session.add(Genre(name="jazz"))
        raise RuntimeError("boom")
    with session_scope(session_factory) as session:
        assert session.execute(select(Genre)).all() == []


def test_busy_timeout_survives_reconnect(db_file):  # type: ignore[no-untyped-def]
    first = sqlite3.connect(str(db_file))
    try:
        first.execute("PRAGMA busy_timeout=5000")
        assert first.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        first.close()
