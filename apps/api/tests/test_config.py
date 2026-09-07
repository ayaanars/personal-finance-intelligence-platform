import pytest
from pydantic import SecretStr, ValidationError

from ledgerx.core.config import Settings


@pytest.mark.parametrize(
    "url", ["sqlite:///test.db", "invalid", "postgresql+psycopg://localhost/db"]
)
def test_invalid_database_configuration_is_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr(url))


def test_database_secret_is_hidden() -> None:
    settings = Settings(
        database_url=SecretStr("postgresql+psycopg://test:synthetic@localhost/test")
    )
    assert "synthetic" not in repr(settings)
