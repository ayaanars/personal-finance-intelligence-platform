from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError

from ledgerx.core.config import Settings
from ledgerx.main import create_app


def test_liveness_does_not_connect_to_database() -> None:
    app = create_app(
        Settings(
            database_url=SecretStr("postgresql+psycopg://synthetic:synthetic@127.0.0.1:1/test")
        )
    )
    with TestClient(app) as client, patch.object(app.state.engine, "connect") as connect:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        UUID(response.headers["X-Correlation-ID"])
        connect.assert_not_called()


def test_readiness_failure_is_safe() -> None:
    app = create_app(
        Settings(
            database_url=SecretStr("postgresql+psycopg://synthetic:synthetic@127.0.0.1:1/test")
        )
    )
    with (
        TestClient(app) as client,
        patch.object(
            app.state.engine,
            "connect",
            side_effect=OperationalError("secret SQL", {}, Exception("secret")),
        ),
    ):
        response = client.get("/health/ready", headers={"X-Request-ID": "not-a-uuid"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_NOT_READY"
        assert "secret" not in response.text
        assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]


def test_openapi_only_exposes_health_and_authentication_operations() -> None:
    app = create_app(
        Settings(
            database_url=SecretStr("postgresql+psycopg://synthetic:synthetic@127.0.0.1:1/test")
        )
    )
    assert set(app.openapi()["paths"]) == {
        "/health/live",
        "/health/ready",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
        "/api/v1/auth/csrf",
        "/api/v1/me",
    }


def test_unexpected_error_is_redacted_and_correlated() -> None:
    app = create_app(
        Settings(database_url=SecretStr("postgresql+psycopg://synthetic:synthetic@localhost/test"))
    )
    request_id = "84e3aa57-34c6-4f41-af45-fb56861d509f"
    with (
        TestClient(app) as client,
        patch.object(
            app.state.engine, "connect", side_effect=RuntimeError("private implementation detail")
        ),
    ):
        response = client.get("/health/ready", headers={"X-Request-ID": request_id})
        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "correlation_id": request_id,
            }
        }
        assert response.headers["X-Correlation-ID"] == request_id
        assert response.headers["Cache-Control"] == "no-store"
