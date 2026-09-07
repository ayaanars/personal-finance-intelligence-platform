import os

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from ledgerx.core.config import Settings
from ledgerx.db.session import build_engine, build_session_factory
from ledgerx.main import create_app

pytestmark = pytest.mark.integration


def test_postgres_readiness_and_session() -> None:
    url = os.environ.get("LEDGERX_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LEDGERX_TEST_DATABASE_URL to a dedicated PostgreSQL database")
    settings = Settings(environment="test", database_url=SecretStr(url))
    engine = build_engine(settings)
    try:
        with build_session_factory(engine)() as session:
            assert session.scalar(text("SELECT 1")) == 1
        with TestClient(create_app(settings)) as client:
            assert client.get("/health/ready").json() == {"status": "ok"}
    finally:
        engine.dispose()
