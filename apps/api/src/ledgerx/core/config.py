from typing import Literal
from urllib.parse import urlsplit

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
    first_party_origin: str = "http://localhost:3000"

    @field_validator("first_party_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        try:
            url = urlsplit(value)
            port = url.port
        except ValueError:
            raise ValueError("Use one exact first-party origin") from None
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.path
            or url.query
            or url.fragment
            or "*" in value
            or not value.isascii()
            or any(character.isspace() for character in value)
            or value != f"{url.scheme}://{url.netloc}"
            or (port is not None and port == 0)
        ):
            raise ValueError("Use one exact first-party origin")
        if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("HTTP is allowed only for loopback development")
        return value

    @property
    def cookie_secure(self) -> bool:
        return self.first_party_origin.startswith("https://")

    @property
    def session_cookie_name(self) -> str:
        return "__Host-ledgerx_session" if self.cookie_secure else "ledgerx_session"

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
