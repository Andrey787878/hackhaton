"""Verify a migrated PostgreSQL database; optionally exercise persistence.

Run from the repository root: python -m scripts.verify_database [--exercise].
The default is read-only. --exercise briefly commits a uniquely named test
user and removes it in finally; use a dedicated development/test database.
No credentials, password hashes or tokens are printed.
"""
from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

import bcrypt
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import delete, inspect, select, text

from app.db import Base, SessionLocal, engine
from app import models  # registers all ORM tables


ROOT = Path(__file__).resolve().parents[1]


def verify_schema() -> dict:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("This verification requires a real PostgreSQL server.")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        actual_heads = set(context.get_current_heads())
        if actual_heads != expected_heads:
            raise RuntimeError("Database is not at Alembic head; run alembic upgrade head.")
        differences = compare_metadata(context, Base.metadata)
        if differences:
            raise RuntimeError(f"ORM/migration schema drift: {differences!r}")
        inspector = inspect(connection)
        actual_tables = set(inspector.get_table_names(schema="public"))
        if not set(Base.metadata.tables).issubset(actual_tables):
            raise RuntimeError("Missing application tables.")
        roles = set(connection.scalars(text("SELECT slug FROM roles WHERE deleted_at IS NULL")))
        if not {"admin", "organizer", "participant", "expert"}.issubset(roles):
            raise RuntimeError("Platform roles were not seeded by migrations.")
        return {
            "server_version": connection.scalar(text("SHOW server_version")),
            "database": connection.scalar(text("SELECT current_database()")),
            "revision": sorted(actual_heads),
            "application_tables": len(Base.metadata.tables),
            "foreign_keys": sum(len(inspector.get_foreign_keys(t)) for t in Base.metadata.tables),
            "check_constraints": sum(len(inspector.get_check_constraints(t)) for t in Base.metadata.tables),
            "roles": sorted(roles),
            "schema_matches_models": True,
        }


def exercise_persistence() -> dict:
    """Commit, read through a new connection, roll back and remove own row."""
    username = "dbcheck_" + secrets.token_hex(12)
    password_hash = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode("ascii")
    try:
        with SessionLocal.begin() as db:
            user = models.User(username=username, email=f"{username}@example.invalid",
                               password_hash=password_hash, display_name="Database smoke test")
            db.add(user)
            db.flush()
            user_id = user.id
        # Independent engine connection proves the row is committed, not just
        # visible in the identity map or in the inserting transaction.
        with engine.connect() as connection:
            found = connection.scalar(select(models.User.username).where(models.User.id == user_id))
            if found != username:
                raise RuntimeError("Committed row cannot be read from another connection.")
        with SessionLocal() as db:
            user = db.get(models.User, user_id)
            user.display_name = "This change must be rolled back"
            db.flush()
            db.rollback()
        with engine.connect() as connection:
            value = connection.scalar(select(models.User.display_name).where(models.User.id == user_id))
            if value != "Database smoke test":
                raise RuntimeError("Rollback did not restore the committed value.")
    finally:
        # Username is random and owned by this invocation. Never delete a
        # pre-existing account or depend on a guessed primary key.
        with SessionLocal.begin() as db:
            db.execute(delete(models.User).where(models.User.username == username))
    with engine.connect() as connection:
        if connection.scalar(select(models.User.id).where(models.User.username == username)) is not None:
            raise RuntimeError("Smoke-test cleanup failed.")
    return {"commit_and_read": "passed", "rollback": "passed", "cleanup": "passed"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exercise", action="store_true", help="Commit/read/rollback/cleanup in a test database")
    args = parser.parse_args()
    result = verify_schema()
    if args.exercise:
        result["persistence"] = exercise_persistence()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
