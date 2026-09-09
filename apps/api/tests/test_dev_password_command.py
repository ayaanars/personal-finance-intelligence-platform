import getpass
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from ledgerx.core.config import Settings
from ledgerx.modules.identity import dev_reset_password as command


@pytest.mark.parametrize(
    "environment,host,query",
    [
        ("test", "localhost", ""),
        ("development", "remote.example.com", ""),
        ("development", "localhost", "?host=remote.example.com"),
    ],
)
def test_refuses_nonlocal_configuration_before_prompt(
    environment: str,
    host: str,
    query: str,
) -> None:
    settings = Settings.model_validate(
        {
            "environment": environment,
            "database_url": f"postgresql+psycopg://synthetic:synthetic@{host}/test{query}",
        }
    )
    with (
        patch.object(command, "Settings", return_value=settings),
        patch.object(getpass, "getpass") as prompt,
        patch.object(command, "build_engine") as connect,
    ):
        assert command.main(["--email", "synthetic@example.com"]) == 1
        prompt.assert_not_called()
        connect.assert_not_called()


@pytest.mark.parametrize(
    "values",
    [
        ["synthetic first password", "synthetic second password"],
        ["short", "short"],
    ],
)
def test_invalid_password_does_not_connect_or_echo(
    values: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(database_url=SecretStr("postgresql+psycopg://a:b@localhost/test"))
    with (
        patch.object(command, "Settings", return_value=settings),
        patch.object(getpass, "getpass", side_effect=values),
        patch.object(command, "build_engine") as connect,
    ):
        assert command.main(["--email", "synthetic@example.com"]) == 1
        connect.assert_not_called()
    output = capsys.readouterr()
    assert all(value not in output.out + output.err for value in values)


def test_non_echoing_terminal_required() -> None:
    settings = Settings(database_url=SecretStr("postgresql+psycopg://a:b@localhost/test"))
    with (
        patch.object(command, "Settings", return_value=settings),
        patch.object(getpass, "getpass", side_effect=getpass.GetPassWarning),
        patch.object(command, "build_engine") as connect,
    ):
        assert command.main(["--email", "synthetic@example.com"]) == 1
        connect.assert_not_called()
