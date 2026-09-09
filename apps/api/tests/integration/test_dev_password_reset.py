import getpass
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from test_auth import EMAIL, PASSWORD, Harness
from test_auth import auth as shared_auth
from test_transactions import finalized

from ledgerx.core.config import Settings
from ledgerx.db.base import Base
from ledgerx.modules.identity import dev_reset_password as command

pytestmark = pytest.mark.integration
auth_fixture = shared_auth


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


def snapshot(auth: Harness) -> dict[str, list[str]]:
    with auth.engine.connect() as db:
        return {
            name: sorted(db.scalars(text(f'SELECT row_to_json(t)::text FROM "{name}" t')))
            for name in Base.metadata.tables
            if name != "user_credentials"
        }


def test_only_matching_credential_changes_and_login_works(
    auth: Harness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    finalized(auth)
    auth.register("untouched@example.com")
    before = snapshot(auth)
    with auth.engine.connect() as db:
        credentials = dict(
            db.execute(text("SELECT user_id, password_hash FROM user_credentials")).tuples().all()
        )
        other = db.scalar(
            text("SELECT id FROM users WHERE email_normalized='untouched@example.com'")
        )
    new_password = "Synthetic replacement passphrase 2026"
    settings = Settings(
        database_url=SecretStr(auth.engine.url.render_as_string(hide_password=False))
    )
    with (
        patch.object(command, "Settings", return_value=settings),
        patch.object(command, "build_engine", return_value=auth.engine),
        patch.object(getpass, "getpass", side_effect=[new_password, new_password]),
    ):
        assert command.main(["--email", " " + EMAIL.upper() + " "]) == 0
    assert snapshot(auth) == before
    with auth.engine.connect() as db:
        after = dict(
            db.execute(text("SELECT user_id, password_hash FROM user_credentials")).tuples().all()
        )
    assert after[other] == credentials[other]
    assert sum(after[key] != value for key, value in credentials.items()) == 1
    captured = capsys.readouterr()
    assert new_password not in captured.out + captured.err
    assert "$argon2" not in captured.out + captured.err
    assert (
        auth.client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        auth.client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": new_password}
        ).status_code
        == 204
    )


def test_missing_user_is_not_created(auth: Harness) -> None:
    auth.register()
    before = snapshot(auth)
    settings = Settings(
        database_url=SecretStr(auth.engine.url.render_as_string(hide_password=False))
    )
    with (
        patch.object(command, "Settings", return_value=settings),
        patch.object(command, "build_engine", return_value=auth.engine),
        patch.object(getpass, "getpass", return_value="Synthetic replacement password"),
    ):
        assert command.main(["--email", "missing@example.com"]) == 1
    assert snapshot(auth) == before
