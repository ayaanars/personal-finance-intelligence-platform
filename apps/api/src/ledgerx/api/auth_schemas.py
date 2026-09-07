from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class CredentialsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=15, max_length=128)

    @field_validator("password")
    @classmethod
    def password_encoding(cls, value: SecretStr) -> SecretStr:
        try:
            value.get_secret_value().encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Use valid Unicode text") from None
        return value

    @field_validator("email")
    @classmethod
    def email_syntax(cls, value: str) -> str:
        display = value.strip(" ")
        # ADR 0002 forbids silently adding Unicode/IDNA canonicalization.
        if not display.isascii():
            raise ValueError("Use an ASCII email address")
        try:
            validate_email(display, check_deliverability=False, allow_smtputf8=False)
        except EmailNotValidError:
            raise ValueError("Use a valid email address") from None
        return display


class WorkspaceView(BaseModel):
    id: UUID
    display_name: str


class UserView(BaseModel):
    id: UUID
    email: str
    workspace: WorkspaceView


class CsrfView(BaseModel):
    csrf_token: str


class EmptyMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
