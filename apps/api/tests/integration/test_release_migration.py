"""Release migrations reject concurrent operators and retain a drift-free head."""

from unittest.mock import patch

import pytest
from sqlalchemy import text
from test_auth import Harness
from test_auth import auth as shared_auth

from ledgerx.db import migrate
from ledgerx.db.revision import EXPECTED_SCHEMA_REVISION

pytestmark = pytest.mark.integration
auth_fixture = shared_auth


def test_release_lock_and_retry(auth_fixture: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERX_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "LEDGERX_DATABASE_URL",
        auth_fixture.app.state.settings.database_url.get_secret_value(),
    )
    monkeypatch.delenv("LEDGERX_MIGRATION_DATABASE_URL", raising=False)
    with patch("ledgerx.db.migrate.create_engine", return_value=auth_fixture.engine):
        with auth_fixture.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(60212021)"))
            with pytest.raises(SystemExit, match="release must stop"):
                migrate.main()
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == EXPECTED_SCHEMA_REVISION
            )
        # The previous transaction releases the lock. A retry checks the schema
        # and succeeds without creating another revision or touching user data.
        migrate.main()
        with auth_fixture.engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == EXPECTED_SCHEMA_REVISION
            )
