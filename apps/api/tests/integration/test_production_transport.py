"""Production transport policy with a migrated, isolated local PostgreSQL engine."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from test_auth import EMAIL, PASSWORD, Harness
from test_auth import auth as shared_auth

from ledgerx.core.config import Settings
from ledgerx.main import create_app

pytestmark = pytest.mark.integration
auth_fixture = shared_auth


@pytest.fixture
def production(auth_fixture: Harness) -> Harness:
    url = make_url(auth_fixture.app.state.settings.database_url.get_secret_value())
    settings = Settings(
        environment="production",
        database_url=SecretStr(
            url.update_query_dict({"sslmode": "require"}).render_as_string(hide_password=False)
        ),
        first_party_origin="https://ledgerx.example",
    )
    # This tests production policy against real PostgreSQL; provider TLS still
    # requires hosted verification. The fixture owns the isolated local engine.
    with patch("ledgerx.main.build_engine", return_value=auth_fixture.engine):
        app = create_app(settings)
    return Harness(app=app, client=auth_fixture.client, engine=auth_fixture.engine)


def test_production_cookies_origins_csrf_and_logout(production: Harness) -> None:
    with (
        patch("ledgerx.main.build_engine", return_value=production.engine),
        TestClient(
            production.app,
            base_url="https://ledgerx.example",
            headers={"Origin": "https://ledgerx.example"},
        ) as client,
    ):
        payload = {"email": EMAIL, "password": PASSWORD}
        assert client.post("/api/v1/auth/register", json=payload).status_code == 201
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 204
        cookie = response.headers["set-cookie"]
        assert cookie.startswith("__Host-ledgerx_session=")
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Domain=" not in cookie
        prior = client.cookies["__Host-ledgerx_session"]
        assert client.get("/api/v1/me").status_code == 200
        assert client.post("/api/v1/auth/logout", json={}).status_code == 403
        assert (
            client.post(
                "/api/v1/auth/login", json=payload, headers={"Origin": "https://attacker.example"}
            ).status_code
            == 403
        )
        assert client.post("/api/v1/auth/login", json=payload).status_code == 204
        assert client.cookies["__Host-ledgerx_session"] != prior
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        assert (
            client.post(
                "/api/v1/auth/logout-all", json={}, headers={"X-CSRF-Token": csrf}
            ).status_code
            == 204
        )
        assert client.get("/api/v1/me").status_code == 401


def test_production_readiness_requires_current_migration(production: Harness) -> None:
    with (
        patch("ledgerx.main.build_engine", return_value=production.engine),
        TestClient(production.app) as client,
    ):
        assert client.get("/health/ready").status_code == 200
        with production.engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = '0008_import_mapping'")
            )
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "0008" not in response.text and "alembic" not in response.text
        assert client.get("/health/live").status_code == 200
