from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Validated runtime settings; production fails closed on unsafe configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGERX_", env_file=".env", extra="forbid", hide_input_in_errors=True
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    first_party_origin: str = "http://localhost:3000"
    log_level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=5, ge=0, le=20)
    reset_delivery: Literal["disabled", "smtp"] = "disabled"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    reset_from_email: str | None = None

    @model_validator(mode="after")
    def production_guards(self) -> "Settings":
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("Production requires an HTTPS first-party origin")
            url = make_url(self.database_url.get_secret_value())
            if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Production PostgreSQL requires explicit TLS sslmode")
        if self.reset_delivery == "smtp" and not all(
            [self.smtp_host, self.smtp_username, self.smtp_password, self.reset_from_email]
        ):
            raise ValueError("SMTP recovery requires host, credentials and sender")
        return self

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
