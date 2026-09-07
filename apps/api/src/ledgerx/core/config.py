from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Explicit development/test configuration; production is a later deployment phase."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGERX_", env_file=".env", extra="forbid", hide_input_in_errors=True
    )

    environment: Literal["development", "test"] = "development"
    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("A valid PostgreSQL connection URL is required") from None
        if (
            url.drivername != "postgresql+psycopg"
            or not url.host
            or not url.database
            or not url.username
            or not url.password
        ):
            raise ValueError("Use postgresql+psycopg with host, database and credentials")
        return value
