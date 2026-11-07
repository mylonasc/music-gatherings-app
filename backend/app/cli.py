"""Operator commands. No default credentials: the admin password is supplied
interactively or via an operator-provided environment variable (never committed)."""

import argparse
import getpass
import os

from sqlalchemy import select

from app.api.v1.access_requests import get_or_create_default_crew
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory, session_scope
from app.core.security import hash_password
from app.models import AuditEvent, CrewMembership, User


def bootstrap(username: str, password: str | None) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    password = password or os.environ.get("MUSIC_GATHERINGS_BOOTSTRAP_PASSWORD")
    if not password:
        password = getpass.getpass(f"Password for initial admin '{username}': ")
    if not password:
        raise SystemExit("a non-empty password is required")
    with session_scope(factory) as db:
        existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing is not None:
            raise SystemExit(f"user '{username}' already exists")
        user = User(
            username=username,
            password_hash=hash_password(password),
            status="active",
            is_admin=True,
        )
        db.add(user)
        db.flush()
        crew = get_or_create_default_crew(db)
        db.add(CrewMembership(crew_id=crew.id, user_id=user.id, role="owner"))
        db.add(
            AuditEvent(
                actor_user_id=user.id,
                action="admin.bootstrapped",
                entity_type="user",
                entity_id=user.id,
            )
        )
    print(f"admin '{username}' created and owns crew '{crew.name}'")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Music Gatherings operator commands")
    sub = parser.add_subparsers(dest="command", required=True)
    create_admin = sub.add_parser("create-admin", help="Create the first admin user")
    create_admin.add_argument("--username", required=True)
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        bootstrap(args.username, None)


if __name__ == "__main__":
    main()
