from http.cookies import SimpleCookie

import pytest
from fastapi import Response
from pydantic import SecretStr, ValidationError

from ledgerx.api.auth_schemas import CredentialsInput
from ledgerx.api.auth_security import cookie
from ledgerx.core.config import Settings
from ledgerx.modules.identity.passwords import Passwords, new_secret, valid_secret


@pytest.mark.parametrize(
    "origin,secure,name",
    [
        ("http://localhost:3000", False, "ledgerx_session"),
        ("https://ledgerx.example", True, "__Host-ledgerx_session"),
    ],
)
def test_cookie_scope_and_deletion(origin: str, secure: bool, name: str) -> None:
    settings = Settings(
        environment="test",
        first_party_origin=origin,
        database_url=SecretStr("postgresql+psycopg://test:synthetic@localhost/test"),
    )
    for token in (new_secret(), None):
        response = Response()
        cookie(response, settings, token)
        parsed = SimpleCookie()
        parsed.load(response.headers["set-cookie"])
        assert set(parsed) == {name}
        value = parsed[name]
        assert bool(value["secure"]) == secure
        assert value["httponly"] and value["samesite"] == "lax"
        assert value["path"] == "/" and value["domain"] == ""
        assert value["max-age"] == ("604800" if token else "0")


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://example.com/",
        "https://example.com/path",
        "http://example.com",
        "https://user:password@example.com",
        "https://example.com?query=1",
        "https://example.com#fragment",
        "https://*.example.com",
        "https://example.com:bad",
        "HTTPS://example.com",
        " https://example.com",
        "https://exam\nple.com",
    ],
)
def test_unsafe_origin_configuration_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            first_party_origin=origin,
            database_url=SecretStr("postgresql+psycopg://test:synthetic@localhost/test"),
        )


def test_production_still_requires_separate_deployment_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEDGERX_ENVIRONMENT", "production")
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr("postgresql+psycopg://test:synthetic@localhost/test"))


@pytest.mark.parametrize(
    "email", ["invalid", "a@", "a b@example.com", "ü@example.com", "a@éxample.com"]
)
def test_email_validation(email: str) -> None:
    with pytest.raises(ValidationError):
        CredentialsInput(email=email, password=SecretStr("synthetic passphrase"))


@pytest.mark.parametrize("password", ["x" * 14, "x" * 129, "x" * 15 + "\ud800"])
def test_password_bounds(password: str) -> None:
    with pytest.raises(ValidationError):
        CredentialsInput(email="synthetic@example.com", password=SecretStr(password))


def test_passwords_preserve_passphrases_and_use_unique_salts() -> None:
    passwords = Passwords()
    phrase = "  synthetic ünicode passphrase " + "x" * 65
    body = CredentialsInput(email="synthetic+alias@example.com", password=SecretStr(phrase))
    assert body.password.get_secret_value() == phrase
    first, second = passwords.hash(phrase), passwords.hash(phrase)
    assert first != second
    assert passwords.verify(first, phrase) and not passwords.verify(first, phrase.strip())
    assert not passwords.verify(None, phrase)
    assert not passwords.verify("invalid-encoded-hash", phrase)


def test_random_session_token_shape_and_collision_smoke() -> None:
    # This tests generator usage/shape, not a mathematical proof of unpredictability.
    tokens = {new_secret() for _ in range(1000)}
    assert len(tokens) == 1000 and all(valid_secret(token) for token in tokens)
