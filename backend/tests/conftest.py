import sqlite3

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import create_engine, session_scope
from app.models import Base


@pytest.fixture()
def db_file(tmp_path):  # type: ignore[no-untyped-def]
    return tmp_path / "test.db"


@pytest.fixture()
def engine(db_file):  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session_factory(engine) -> sessionmaker[Session]:  # type: ignore[no-untyped-def]
    from app.core.database import create_session_factory

    return create_session_factory(engine)


@pytest.fixture()
def db_session(session_factory):  # type: ignore[no-untyped-def]
    with session_scope(session_factory) as session:
        yield session


def sqlite_pragma(db_file: object, name: str) -> object:
    con = sqlite3.connect(str(db_file))
    try:
        return con.execute(f"PRAGMA {name}").fetchone()[0]
    finally:
        con.close()
