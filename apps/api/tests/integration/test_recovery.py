"""Real PostgreSQL recovery concurrency, revocation and shared-budget regression tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session
from test_auth import EMAIL, PASSWORD, PREFIX, Harness
from test_auth import auth as shared_auth

from ledgerx.modules.identity import recovery
from ledgerx.modules.identity.errors import AuthError
from ledgerx.modules.identity.models import AuthAudit, Credential, UserSession
from ledgerx.modules.identity.passwords import secret_hash
from ledgerx.modules.identity.rate_limit import consume
from ledgerx.modules.identity.recovery_models import PasswordReset
from ledgerx.modules.identity.service import utcnow

pytestmark = pytest.mark.integration
auth_fixture = shared_auth


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


NEW_PASSWORD = "Replacement synthetic passphrase 2026"


def issue_token(harness: Harness) -> str:
    with Session(harness.engine) as db:
        token = recovery.issue(db, EMAIL)
    assert token is not None
    return token


def test_reset_consumes_hash_and_revokes_all_sessions(auth: Harness) -> None:
    auth.register()
    auth.login()
    auth.client.cookies.clear()
    auth.login()
    token = issue_token(auth)
    with Session(auth.engine) as db:
        stored = db.scalar(select(PasswordReset))
        assert stored is not None and stored.token_hash == secret_hash(token)
        assert token.encode() != stored.token_hash
    response = auth.client.post(
        PREFIX + "/auth/password-reset/complete", json={"token": token, "password": NEW_PASSWORD}
    )
    assert response.status_code == 204
    assert auth.client.get(PREFIX + "/me").status_code == 401
    with Session(auth.engine) as db:
        assert all(s.revoked_at is not None for s in db.scalars(select(UserSession)))
        assert (
            db.scalar(select(AuthAudit.id).where(AuthAudit.event_code == "password_reset"))
            is not None
        )
        credential = db.scalar(select(Credential))
        assert credential is not None and credential.password_hash.startswith("$argon2id$")
    assert (
        auth.client.post(
            PREFIX + "/auth/password-reset/complete",
            json={"token": token, "password": NEW_PASSWORD},
        ).status_code
        == 400
    )
    assert (
        auth.client.post(
            PREFIX + "/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        auth.client.post(
            PREFIX + "/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
        ).status_code
        == 204
    )


def test_expired_and_replaced_tokens_fail(auth: Harness) -> None:
    auth.register()
    old = issue_token(auth)
    current = issue_token(auth)
    with Session(auth.engine) as db:
        with pytest.raises(AuthError):
            recovery.complete(db, auth.app.state.passwords, old, NEW_PASSWORD)
        with db.begin():
            db.execute(update(PasswordReset).values(expires_at=utcnow() - timedelta(seconds=1)))
        with pytest.raises(AuthError):
            recovery.complete(db, auth.app.state.passwords, current, NEW_PASSWORD)


def test_concurrent_reset_has_one_winner(auth: Harness) -> None:
    auth.register()
    token = issue_token(auth)

    def attempt(_: int) -> bool:
        with Session(auth.engine) as db:
            try:
                recovery.complete(db, auth.app.state.passwords, token, NEW_PASSWORD)
                return True
            except AuthError:
                return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(attempt, range(2))) == [False, True]


def test_request_has_uniform_response_and_no_token(auth: Harness) -> None:
    auth.register()
    auth.app.state.settings.reset_delivery = "smtp"
    with patch("ledgerx.modules.identity.recovery.deliver") as deliver:
        known = auth.client.post(PREFIX + "/auth/password-reset/request", json={"email": EMAIL})
        unknown = auth.client.post(
            PREFIX + "/auth/password-reset/request", json={"email": "unknown@example.com"}
        )
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()
        deliver.assert_called_once()
        assert deliver.call_args.args[2] not in known.text
    auth.app.state.settings.reset_delivery = "disabled"
    assert (
        auth.client.post(PREFIX + "/auth/password-reset/request", json={"email": EMAIL}).status_code
        == 503
    )


def test_shared_budget_is_atomic(auth: Harness) -> None:
    def attempt(_: int) -> bool:
        with Session(auth.engine) as db:
            try:
                consume(db, "register")
                return True
            except AuthError as exc:
                assert exc.status == 429
                return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(attempt, range(16))) == 10


def test_recovery_rejects_cross_origin_and_malformed_input(auth: Harness) -> None:
    auth.register()
    token = issue_token(auth)
    payload = {"token": token, "password": NEW_PASSWORD}
    assert (
        auth.client.post(
            PREFIX + "/auth/password-reset/complete",
            json=payload,
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        auth.client.post(
            PREFIX + "/auth/password-reset/complete", json={**payload, "password": "short"}
        ).status_code
        == 422
    )
    assert (
        auth.client.post(PREFIX + "/auth/password-reset/complete", json=payload).status_code == 204
    )


def test_failed_reset_rolls_back_credential_token_and_revocation(auth: Harness) -> None:
    auth.register()
    auth.login()
    token = issue_token(auth)
    with Session(auth.engine) as db:
        original = db.scalar(select(Credential.password_hash))

    def fail_commit(db: Session) -> None:
        raise RuntimeError("synthetic commit failure")

    with Session(auth.engine) as db:
        event.listen(db, "before_commit", fail_commit)
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            recovery.complete(db, auth.app.state.passwords, token, NEW_PASSWORD)
    with Session(auth.engine) as db:
        assert db.scalar(select(Credential.password_hash)) == original
        assert (
            db.scalar(select(AuthAudit.id).where(AuthAudit.event_code == "password_reset")) is None
        )
        reset = db.scalar(select(PasswordReset))
        session = db.scalar(select(UserSession))
        assert reset is not None and reset.used_at is None
        assert session is not None and session.revoked_at is None
    assert auth.client.get(PREFIX + "/me").status_code == 200


def test_downgrade_preserves_recorded_recovery_audit(auth: Harness) -> None:
    auth.register()
    token = issue_token(auth)
    with Session(auth.engine) as db:
        recovery.complete(db, auth.app.state.passwords, token, NEW_PASSWORD)
    config = Config("alembic.ini")
    with auth.engine.begin() as connection:
        config.attributes["connection"] = connection
        with pytest.raises(RuntimeError, match="preserve the audit"):
            command.downgrade(config, "0009_recovery")
    with Session(auth.engine) as db:
        assert (
            db.scalar(select(AuthAudit.id).where(AuthAudit.event_code == "password_reset"))
            is not None
        )
