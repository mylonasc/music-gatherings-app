from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import create_engine, create_session_factory, session_scope
from app.models import Base


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def engine(db_file: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture()
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_scope(session_factory) as session:
        yield session


def sqlite_pragma(db_file: Path, name: str) -> object:
    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        row = con.execute(f"PRAGMA {name}").fetchone()
        assert row is not None
        return row[0]
    finally:
        con.close()
