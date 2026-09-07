import pytest
from pydantic import ValidationError

from ledgerx.core.config import Settings
from ledgerx.main import create_app


def test_settings_load_required_database_url_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "LEDGERX_DATABASE_URL", "postgresql+psycopg://synthetic:synthetic@localhost/test"
    )
    assert create_app().title == "LedgerX API"


def test_missing_database_url_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEDGERX_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)
