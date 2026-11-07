"""SQLite engine/session wiring with safe defaults.

WAL mode, busy timeouts, and foreign-key enforcement are applied on every
connection. Write transactions must stay short; never hold one across network
or CPU-heavy work (see S06 worker design).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine(database_url: str) -> Engine:
    engine = _create_engine(database_url, future=True)
    if engine.dialect.name == "sqlite":
        _register_sqlite_pragmas(engine)
    return engine


def _register_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
