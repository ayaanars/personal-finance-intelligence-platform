"""Authentication behavior against migrated, isolated PostgreSQL schemas."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from ledgerx.api.auth_security import Authenticated
from ledgerx.core.config import Settings
from ledgerx.db.session import build_engine, build_session_factory
from ledgerx.main import create_app
from ledgerx.modules.identity import service
from ledgerx.modules.identity.errors import AuthError
from ledgerx.modules.identity.models import Credential, UserSession
from ledgerx.modules.identity.passwords import secret_hash

pytestmark = pytest.mark.integration
PASSWORD = "synthetic long passphrase 123"
EMAIL = "Synthetic@example.com"
PREFIX = "/api/v1"


@dataclass
class Harness:
    app: FastAPI
    client: TestClient
    engine: Engine

    def register(self, email: str = EMAIL) -> dict[str, object]:
        response = self.client.post(
            PREFIX + "/auth/register", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 201, response.text
        return dict(response.json())

    def login(self, email: str = EMAIL) -> str:
        response = self.client.post(
            PREFIX + "/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 204, response.text
        return str(self.client.cookies["ledgerx_session"])

    def csrf(self) -> str:
        response = self.client.get(PREFIX + "/auth/csrf")
        assert response.status_code == 200, response.text
        return str(response.json()["csrf_token"])

    def use(self, token: str) -> None:
        self.client.cookies.clear()
        self.client.cookies.set("ledgerx_session", token, domain="testserver.local", path="/")


@pytest.fixture
def auth() -> Iterator[Harness]:
    url = os.environ.get("LEDGERX_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LEDGERX_TEST_DATABASE_URL to a dedicated PostgreSQL database")
    settings = Settings(environment="test", database_url=SecretStr(url))
    admin = build_engine(settings)
    schema = "test_auth_" + uuid4().hex
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={
            "options": f"-c search_path={schema} -c timezone=UTC -c statement_timeout=5000"
        },
    )
    try:
        with engine.begin() as db:
            config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
            config.attributes["connection"] = db
            command.upgrade(config, "head")
        with patch("ledgerx.main.build_engine", return_value=engine):
            app = create_app(settings)

            @app.post("/protected-probe")
            def protected(context: Authenticated) -> dict[str, str]:
                return {"user_id": str(context.principal.user.id)}

            with TestClient(app) as client:
                yield Harness(app, client, engine)
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_registration_workspace_hash_and_duplicate(auth: Harness) -> None:
    profile = auth.register(" Synthetic@EXAMPLE.com ")
    assert profile["email"] == "Synthetic@EXAMPLE.com"
    assert "password" not in str(profile)
    assert not auth.client.cookies
    with auth.engine.connect() as db:
        row = db.execute(text("SELECT * FROM users")).one()
        assert row.email_normalized == "synthetic@example.com"
        assert row.status == "active"
        assert db.scalar(text("SELECT owner_user_id FROM workspaces")) == row.id
        encoded = db.scalar(text("SELECT password_hash FROM user_credentials"))
        assert isinstance(encoded, str) and encoded.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
        assert PASSWORD not in encoded
        assert auth.app.state.passwords.verify(encoded, PASSWORD)
        assert db.scalar(text("SELECT event_code FROM auth_audit_events")) == "registered"
    response = auth.client.post(
        PREFIX + "/auth/register",
        json={
            "email": "synthetic@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_FAILED"
    with auth.engine.connect() as db:
        for table in ("users", "workspaces", "user_credentials", "auth_audit_events"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 1


@pytest.mark.parametrize("target", ["workspaces", "user_credentials", "auth_audit_events"])
def test_registration_rolls_back_every_record(auth: Harness, target: str) -> None:
    with auth.engine.begin() as db:
        db.execute(text(f"ALTER TABLE {target} ADD CONSTRAINT forced_failure CHECK (false)"))
    response = auth.client.post(
        PREFIX + "/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 500
    assert "forced_failure" not in response.text
    with auth.engine.connect() as db:
        for table in ("users", "workspaces", "user_credentials", "auth_audit_events"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_login_current_user_cookie_and_hash_only_storage(auth: Harness) -> None:
    profile = auth.register()
    token = auth.login()
    assert len(token) == 43 and token != str(profile["id"])
    response = auth.client.get(PREFIX + "/me")
    assert response.status_code == 200 and response.json() == profile
    assert response.headers["cache-control"] == "no-store"
    with auth.engine.connect() as db:
        row = db.execute(text("SELECT * FROM user_sessions")).one()
        assert bytes(row.token_hash) == secret_hash(token)
        assert token.encode() != bytes(row.token_hash)
        assert row.idle_expires_at - row.created_at == timedelta(minutes=30)
        assert row.absolute_expires_at - row.created_at == timedelta(days=7)
    response = auth.client.post(PREFIX + "/auth/login", json={"email": EMAIL, "password": PASSWORD})
    header = response.headers["set-cookie"]
    assert "HttpOnly" in header and "SameSite=lax" in header and "Path=/" in header
    assert "Domain=" not in header and "Secure" not in header
    assert response.content == b""


@pytest.mark.parametrize(
    "email,password",
    [
        (EMAIL, "incorrect synthetic password"),
        ("absent@example.com", PASSWORD),
    ],
)
def test_invalid_credentials_are_generic(auth: Harness, email: str, password: str) -> None:
    auth.register()
    response = auth.client.post(PREFIX + "/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert email not in response.text and password not in response.text
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM user_sessions")) == 0
        assert (
            db.scalar(
                text("SELECT count(*) FROM auth_audit_events WHERE event_code='login_failed'")
            )
            == 1
        )


@pytest.mark.parametrize("token", [None, "bad", "a" * 43, "x" * 1000, "user-id:admin"])
def test_missing_invalid_sessions(auth: Harness, token: str | None) -> None:
    if token:
        auth.use(token)
    assert auth.client.get(PREFIX + "/me").status_code == 401
    assert auth.client.get(PREFIX + "/auth/csrf").status_code == 401
    assert auth.client.post("/protected-probe", json={}).status_code == 401


@pytest.mark.parametrize("mode", ["idle", "absolute", "revoked"])
def test_expired_or_revoked_session(auth: Harness, mode: str) -> None:
    auth.register()
    auth.login()
    now = datetime.now(UTC)
    with auth.engine.begin() as db:
        if mode == "revoked":
            db.execute(
                text("UPDATE user_sessions SET revoked_at=:now, revoke_reason='logout'"),
                {"now": now},
            )
        else:
            age = timedelta(days=8) if mode == "absolute" else timedelta(hours=1)
            db.execute(
                text(
                    "UPDATE user_sessions SET created_at=:start, last_seen_at=:start, "
                    "idle_expires_at=:expiry, absolute_expires_at=:absolute"
                ),
                {
                    "start": now - age,
                    "expiry": now,
                    "absolute": now if mode == "absolute" else now + timedelta(days=1),
                },
            )
    with patch.object(service, "utcnow", return_value=now):
        assert auth.client.get(PREFIX + "/me").status_code == 401


def test_sliding_refresh_is_bounded_and_capped(auth: Harness) -> None:
    auth.register()
    auth.login()
    with auth.engine.connect() as db:
        row = db.execute(text("SELECT * FROM user_sessions")).one()
    with patch.object(service, "utcnow", return_value=row.created_at + timedelta(seconds=59)):
        assert auth.client.get(PREFIX + "/me").status_code == 200
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT last_seen_at FROM user_sessions")) == row.created_at
    with patch.object(service, "utcnow", return_value=row.created_at + timedelta(seconds=60)):
        assert auth.client.get(PREFIX + "/me").status_code == 200
    with auth.engine.connect() as db:
        assert db.scalar(
            text("SELECT idle_expires_at FROM user_sessions")
        ) == row.idle_expires_at + timedelta(seconds=60)
    near_end = row.absolute_expires_at - timedelta(minutes=2)
    with auth.engine.begin() as db:
        db.execute(
            text(
                "UPDATE user_sessions SET last_seen_at=:seen, idle_expires_at=absolute_expires_at"
            ),
            {"seen": near_end - timedelta(minutes=2)},
        )
    with patch.object(service, "utcnow", return_value=near_end):
        assert auth.client.get(PREFIX + "/me").status_code == 200
    with auth.engine.connect() as db:
        assert (
            db.scalar(text("SELECT idle_expires_at FROM user_sessions")) == row.absolute_expires_at
        )


def test_csrf_rotation_and_protected_mutations(auth: Harness) -> None:
    auth.register()
    auth.login()
    old = auth.csrf()
    csrf = auth.csrf()
    assert csrf != old
    with auth.engine.connect() as db:
        assert bytes(db.scalar(text("SELECT csrf_secret_hash FROM user_sessions"))) == secret_hash(
            csrf
        )
    for value in (None, "invalid", old, "a" * 43):
        headers = {"X-CSRF-Token": value} if value else {}
        for path in ("/protected-probe", PREFIX + "/auth/logout", PREFIX + "/auth/logout-all"):
            response = auth.client.post(path, json={}, headers=headers)
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "CSRF_INVALID"
    assert (
        auth.client.post("/protected-probe", json={}, headers={"X-CSRF-Token": csrf}).status_code
        == 200
    )
    assert auth.client.get(PREFIX + "/me").status_code == 200


def test_current_logout_and_replay(auth: Harness) -> None:
    auth.register()
    first = auth.login()
    auth.client.cookies.clear()
    second = auth.login()
    csrf = auth.csrf()
    response = auth.client.post(PREFIX + "/auth/logout", json={}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 204 and "Max-Age=0" in response.headers["set-cookie"]
    auth.use(second)
    assert auth.client.get(PREFIX + "/me").status_code == 401
    auth.use(first)
    assert auth.client.get(PREFIX + "/me").status_code == 200


def test_logout_all_is_owner_scoped(auth: Harness) -> None:
    first_profile = auth.register()
    first = auth.login()
    auth.client.cookies.clear()
    second = auth.login()
    other_profile = auth.register("other@example.com")
    other = auth.login("other@example.com")
    assert auth.client.get(PREFIX + "/me").json() == other_profile
    auth.use(second)
    assert auth.client.get(PREFIX + "/me").json() == first_profile
    csrf = auth.csrf()
    response = auth.client.post(
        PREFIX + "/auth/logout-all", json={}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 204
    for token in (first, second):
        auth.use(token)
        assert auth.client.get(PREFIX + "/me").status_code == 401
    auth.use(other)
    assert auth.client.get(PREFIX + "/me").json() == other_profile
    auth.login()
    assert auth.client.get(PREFIX + "/me").json() == first_profile


def test_session_fixation_and_cross_user_csrf(auth: Harness) -> None:
    auth.register()
    auth.use("a" * 43)
    first = auth.login()
    assert first != "a" * 43
    csrf = auth.csrf()
    second = auth.login()
    assert second != first
    assert (
        auth.client.post("/protected-probe", json={}, headers={"X-CSRF-Token": csrf}).status_code
        == 403
    )
    auth.use(first)
    assert auth.client.get(PREFIX + "/me").status_code == 401
    auth.use(second)
    first_csrf = auth.csrf()
    auth.register("other@example.com")
    auth.login("other@example.com")
    assert (
        auth.client.post(
            "/protected-probe", json={}, headers={"X-CSRF-Token": first_csrf}
        ).status_code
        == 403
    )
    # Login with someone else's prior cookie must not revoke that user's session.
    auth.use(second)
    assert auth.client.get(PREFIX + "/me").status_code == 200


@pytest.mark.parametrize("status", ["locked", "deletion_pending", "deleted"])
def test_inactive_users_cannot_login_or_use_session(auth: Harness, status: str) -> None:
    auth.register()
    auth.login()
    with auth.engine.begin() as db:
        db.execute(text("UPDATE users SET status=:status"), {"status": status})
    assert auth.client.get(PREFIX + "/me").status_code == 401
    response = auth.client.post(PREFIX + "/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "header,value",
    [
        ("Origin", "https://evil.example"),
        ("Origin", "null"),
        ("Referer", "http://localhost:3000.evil.example/page"),
        ("Sec-Fetch-Site", "cross-site"),
    ],
)
def test_untrusted_origins(auth: Harness, header: str, value: str) -> None:
    auth.register()
    auth.login()
    csrf = auth.csrf()
    headers = {header: value, "X-CSRF-Token": csrf}
    for path in ("/auth/register", "/auth/login", "/auth/logout", "/auth/logout-all"):
        assert (
            auth.client.post(
                PREFIX + path, json={"email": EMAIL, "password": PASSWORD}, headers=headers
            ).status_code
            == 403
        )
    assert auth.client.get(PREFIX + "/auth/csrf", headers=headers).status_code == 403


def test_json_origin_cors_and_redaction(auth: Harness, caplog: pytest.LogCaptureFixture) -> None:
    response = auth.client.post(
        PREFIX + "/auth/register", json={"email": "bad", "password": "secret"}
    )
    assert response.status_code == 422 and "secret" not in response.text
    response = auth.client.post(
        PREFIX + "/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "user_id": "credential-looking-unknown-field"},
    )
    assert response.status_code == 422 and "credential-looking" not in response.text
    for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
        response = auth.client.post(
            PREFIX + "/auth/login", content="{}", headers={"Content-Type": content_type}
        )
        assert response.status_code == 415
    auth.register()
    token = auth.login()
    csrf = auth.csrf()
    response = auth.client.post(
        "/protected-probe",
        json={},
        headers={
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": csrf,
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    response = auth.client.options(
        PREFIX + "/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers
    for secret in (PASSWORD, token, csrf, "$argon2id$", EMAIL):
        assert secret not in caplog.text


@pytest.mark.parametrize(
    "assignment",
    [
        "token_hash = decode('00','hex')",
        "csrf_secret_hash = decode('00','hex')",
        "idle_expires_at = created_at",
        "absolute_expires_at = last_seen_at",
        "revoked_at = created_at, revoke_reason = NULL",
        "revoke_reason = 'logout'",
        "revoked_at = created_at, revoke_reason = 'unknown'",
        "user_id = gen_random_uuid()",
    ],
)
def test_session_constraints(auth: Harness, assignment: str) -> None:
    auth.register()
    auth.login()
    with auth.engine.begin() as db, pytest.raises(IntegrityError):
        db.execute(text(f"UPDATE user_sessions SET {assignment}"))


def test_unique_session_hash_and_credential_constraints(auth: Harness) -> None:
    auth.register()
    first = auth.login()
    auth.client.cookies.clear()
    auth.login()
    with auth.engine.begin() as db, pytest.raises(IntegrityError):
        db.execute(text("UPDATE user_sessions SET token_hash=:hash"), {"hash": secret_hash(first)})
    with auth.engine.begin() as db, pytest.raises(IntegrityError):
        db.execute(text("UPDATE user_credentials SET password_hash='plaintext'"))


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE auth_audit_events SET event_code='logout'",
        "DELETE FROM auth_audit_events",
        "TRUNCATE auth_audit_events",
    ],
)
def test_auth_audit_is_append_only(auth: Harness, query: str) -> None:
    auth.register()
    with auth.engine.begin() as db, pytest.raises(DBAPIError):
        db.execute(text(query))


def test_logout_audit_failure_rolls_back_revocation(auth: Harness) -> None:
    auth.register()
    token = auth.login()
    csrf = auth.csrf()
    with auth.engine.begin() as db:
        db.execute(
            text(
                "ALTER TABLE auth_audit_events ADD CONSTRAINT no_logout "
                "CHECK (event_code <> 'logout')"
            )
        )
    response = auth.client.post(PREFIX + "/auth/logout", json={}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 500
    assert "set-cookie" not in response.headers
    auth.use(token)
    assert auth.client.get(PREFIX + "/me").status_code == 200


def test_concurrent_registration(auth: Harness) -> None:
    factory = build_session_factory(auth.engine)

    def attempt() -> int:
        with factory() as db:
            try:
                service.register(db, auth.app.state.passwords, EMAIL.lower(), PASSWORD, uuid4())
                return 201
            except AuthError as exc:
                return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [201, 409]
    with auth.engine.connect() as db:
        for table in ("users", "workspaces", "user_credentials", "auth_audit_events"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 1


def test_concurrent_refresh_cannot_resurrect_logout_all(auth: Harness) -> None:
    auth.register()
    token = auth.login()
    factory = build_session_factory(auth.engine)
    started = Event()

    def refresh() -> int:
        with factory() as db, db.begin():
            started.set()
            try:
                service.authenticate(db, token, None, False)
                return 200
            except AuthError as exc:
                return exc.status

    with ThreadPoolExecutor(max_workers=1) as pool:
        with factory() as db, db.begin():
            principal = service.authenticate(db, token, None, False)
            future = pool.submit(refresh)
            assert started.wait(2)
            service.logout(db, principal, True, uuid4())
        assert future.result(timeout=5) == 401
    assert auth.client.get(PREFIX + "/me").status_code == 401


def test_rehash_on_login(auth: Harness) -> None:
    from argon2 import PasswordHasher

    auth.register()
    old = PasswordHasher(time_cost=2).hash(PASSWORD)
    with build_session_factory(auth.engine)() as db, db.begin():
        credential = db.scalar(select(Credential))
        assert credential is not None
        credential.password_hash = old
    auth.login()
    with build_session_factory(auth.engine)() as db:
        credential = db.scalar(select(Credential))
        assert credential is not None and credential.password_hash != old
        assert not auth.app.state.passwords.hasher.check_needs_rehash(credential.password_hash)
        assert db.scalar(select(UserSession)) is not None
