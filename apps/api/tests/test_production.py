import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from ledgerx.core.config import Settings
from ledgerx.main import create_app


def test_production_requires_https_and_database_tls() -> None:
    url = "postgresql+psycopg://synthetic:synthetic@localhost/test"
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(environment="production", database_url=SecretStr(url))
    with pytest.raises(ValidationError, match="TLS"):
        Settings(
            environment="production",
            database_url=SecretStr(url),
            first_party_origin="https://ledgerx.example",
        )
    settings = Settings(
        environment="production",
        database_url=SecretStr(url + "?sslmode=require"),
        first_party_origin="https://ledgerx.example",
    )
    assert settings.cookie_secure and settings.session_cookie_name == "__Host-ledgerx_session"
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "synthetic password long"},
            ).status_code
            == 403
        )
        allowed = client.options(
            "/api/v1/goals",
            headers={
                "Origin": "https://ledgerx.example",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://ledgerx.example"
        assert (
            client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "https://attacker.example",
                    "Access-Control-Request-Method": "POST",
                },
            ).status_code
            == 400
        )


def test_smtp_requires_complete_configuration() -> None:
    with pytest.raises(ValidationError, match="SMTP"):
        Settings(
            database_url=SecretStr("postgresql+psycopg://synthetic:synthetic@localhost/test"),
            reset_delivery="smtp",
        )
