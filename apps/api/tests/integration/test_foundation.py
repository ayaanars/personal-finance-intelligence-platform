"""Real PostgreSQL tests; each test owns a unique, disposable schema."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy import Connection, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledgerx.core.config import Settings
from ledgerx.db.session import build_engine
from ledgerx.modules.identity.models import User, Workspace

pytestmark = pytest.mark.integration


def migration_config(connection: Connection) -> Config:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def db() -> Iterator[Connection]:
    url = os.environ.get("LEDGERX_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LEDGERX_TEST_DATABASE_URL to a dedicated PostgreSQL database")
    engine = build_engine(Settings(environment="test", database_url=SecretStr(url)))
    schema = "test_foundation_" + uuid4().hex
    try:
        with engine.connect() as connection:
            # Schema names are generated internally, never supplied by a caller.
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.commit()
            try:
                command.upgrade(migration_config(connection), "head")
                connection.commit()
                yield connection
            finally:
                connection.rollback()
                connection.execute(text("SET search_path TO public"))
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                connection.commit()
    finally:
        engine.dispose()


def insert_user(db: Connection, email: str = "synthetic@example.invalid") -> UUID:
    value = db.scalar(
        text("""
        INSERT INTO users (email_normalized, email_display, status)
        VALUES (:email, :email, 'active') RETURNING id
    """),
        {"email": email},
    )
    assert isinstance(value, UUID)
    return value


def test_orm_uuid_and_timestamps(db: Connection) -> None:
    before = datetime.now(UTC)
    with Session(db) as session:
        user = User(
            email_normalized="orm@example.invalid",
            email_display="ORM@example.invalid",
            status="active",
        )
        session.add(user)
        session.flush()
        workspace = Workspace(owner_user_id=user.id, display_name="Synthetic workspace")
        session.add(workspace)
        session.flush()
        assert isinstance(user.id, UUID) and user.id.version == 4
        assert isinstance(workspace.id, UUID) and workspace.id.version == 4
        assert workspace.id != user.id
        for instant in (user.created_at, user.updated_at, workspace.created_at):
            assert instant.utcoffset() == timedelta(0)
            assert before <= instant <= datetime.now(UTC)
        original = user.created_at
        user.status = "locked"
        session.flush()
        session.refresh(user)
        assert user.created_at == original
        assert user.updated_at > original


def test_explicit_uuid_and_offset_round_trip(db: Connection) -> None:
    identifier = uuid4()
    instant = datetime(2026, 1, 2, 12, 30, tzinfo=timezone(timedelta(hours=4)))
    with Session(db) as session:
        user = User(
            id=identifier,
            email_normalized="offset@example.invalid",
            email_display="offset@example.invalid",
            status="active",
            created_at=instant,
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        assert user.id == identifier
        assert user.created_at == instant.astimezone(UTC)
        assert user.created_at.utcoffset() == timedelta(0)


def test_unique_email(db: Connection) -> None:
    insert_user(db)
    with pytest.raises(IntegrityError) as error:
        insert_user(db)
    assert isinstance(error.value.orig, psycopg.Error)
    assert error.value.orig.diag.constraint_name == "uq_users_email_normalized"


@pytest.mark.parametrize(
    "column,value,constraint",
    [
        ("email_normalized", "Mixed@example.invalid", "ck_users_email_normalized_canonical"),
        ("email_normalized", " trailing@example.invalid ", "ck_users_email_normalized_canonical"),
        ("email_normalized", "", "ck_users_email_normalized_canonical"),
        ("email_display", "   ", "ck_users_email_display_nonblank"),
        ("status", "unknown", "ck_users_status"),
    ],
)
def test_user_checks(db: Connection, column: str, value: str, constraint: str) -> None:
    user_id = insert_user(db)
    with pytest.raises(IntegrityError) as error:
        db.execute(
            text(f"UPDATE users SET {column} = :value WHERE id = :id"),
            {"value": value, "id": user_id},
        )
    assert isinstance(error.value.orig, psycopg.Error)
    assert error.value.orig.diag.constraint_name == constraint


@pytest.mark.parametrize("status", ["active", "locked", "deletion_pending", "deleted"])
def test_allowed_statuses(db: Connection, status: str) -> None:
    user_id = insert_user(db)
    db.execute(
        text("UPDATE users SET status = :status WHERE id = :id"), {"status": status, "id": user_id}
    )
    assert db.scalar(text("SELECT status FROM users WHERE id = :id"), {"id": user_id}) == status


def test_workspace_foreign_key(db: Connection) -> None:
    with pytest.raises(IntegrityError) as error:
        db.execute(
            text("INSERT INTO workspaces (owner_user_id, display_name) VALUES (:id, 'Synthetic')"),
            {"id": uuid4()},
        )
    assert isinstance(error.value.orig, psycopg.Error)
    assert error.value.orig.diag.constraint_name == "fk_workspaces_owner_user_id_users"


def test_one_workspace_per_owner(db: Connection) -> None:
    user_id = insert_user(db)
    query = text("INSERT INTO workspaces (owner_user_id, display_name) VALUES (:id, 'Synthetic')")
    db.execute(query, {"id": user_id})
    with pytest.raises(IntegrityError) as error:
        db.execute(query, {"id": user_id})
    assert isinstance(error.value.orig, psycopg.Error)
    assert error.value.orig.diag.constraint_name == "uq_workspaces_owner_user_id"


def test_owner_delete_restricted(db: Connection) -> None:
    user_id = insert_user(db)
    db.execute(
        text("INSERT INTO workspaces (owner_user_id, display_name) VALUES (:id, 'Synthetic')"),
        {"id": user_id},
    )
    with pytest.raises(IntegrityError) as error:
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    assert isinstance(error.value.orig, psycopg.Error)
    assert error.value.orig.diag.constraint_name == "fk_workspaces_owner_user_id_users"


def test_workspace_name_nonblank(db: Connection) -> None:
    user_id = insert_user(db)
    with pytest.raises(IntegrityError) as error:
        db.execute(
            text("INSERT INTO workspaces (owner_user_id, display_name) VALUES (:id, '   ')"),
            {"id": user_id},
        )
    assert isinstance(error.value.orig, psycopg.Error)
    assert error.value.orig.diag.constraint_name == "ck_workspaces_display_name_nonblank"


def test_composite_key_rejects_cross_owner_child(db: Connection) -> None:
    owner = insert_user(db)
    other = insert_user(db, "other@example.invalid")
    workspace = db.scalar(
        text(
            "INSERT INTO workspaces (owner_user_id, display_name) "
            "VALUES (:id, 'Synthetic') RETURNING id"
        ),
        {"id": owner},
    )
    # Disposable-schema probe verifies the future child FK contract without adding a product table.
    db.execute(
        text("""
        CREATE TABLE ownership_probe (
            user_id uuid NOT NULL, workspace_id uuid NOT NULL,
            CONSTRAINT fk_probe_workspace FOREIGN KEY (user_id, workspace_id)
            REFERENCES workspaces (owner_user_id, id)
        )
    """)
    )
    query = text("INSERT INTO ownership_probe VALUES (:owner, :workspace)")
    db.execute(query, {"owner": owner, "workspace": workspace})
    with pytest.raises(IntegrityError) as error:
        db.execute(query, {"owner": other, "workspace": workspace})
    assert isinstance(error.value.orig, psycopg.Error)
    assert error.value.orig.diag.constraint_name == "fk_probe_workspace"


def test_migration_cycle_and_schema(db: Connection) -> None:
    config = migration_config(db)
    assert ScriptDirectory.from_config(config).get_heads() == ["0008_import_mapping"]
    assert set(inspect(db).get_table_names()) == {
        "alembic_version",
        "users",
        "workspaces",
        "user_credentials",
        "user_sessions",
        "auth_audit_events",
        "statement_imports",
        "import_rows",
        "imported_transactions",
        "import_audit_events",
        "transaction_enrichments",
        "transaction_audit_events",
        "merchant_preferences",
        "monthly_goals",
        "import_mapping_profiles",
    }
    command.check(config)
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0008_import_mapping"
    for table in ("users", "workspaces"):
        assert all(not column["nullable"] for column in inspect(db).get_columns(table))
    command.downgrade(config, "0001_foundation")
    assert inspect(db).get_table_names() == ["alembic_version"]
    assert db.scalar(text("SELECT to_regprocedure('ledgerx_touch_user_updated_at()')")) is None
    assert db.scalar(text("SELECT to_regprocedure('ledgerx_auth_audit_append_only()')")) is None
    for name in (
        "ledgerx_import_append_only",
        "ledgerx_import_transition",
        "ledgerx_import_complete_count",
        "ledgerx_import_fact_ready",
        "ledgerx_import_fact_completed",
    ):
        assert db.scalar(text("SELECT to_regprocedure(:name)"), {"name": name + "()"}) is None
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    assert inspect(db).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    command.check(config)
    insert_user(db)
