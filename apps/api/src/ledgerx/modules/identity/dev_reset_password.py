"""Local development operator command only. Never import this from an API route."""

import argparse
import getpass
import sys
import warnings
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import make_url

from ledgerx.api.auth_schemas import CredentialsInput
from ledgerx.core.config import Settings
from ledgerx.db.session import build_engine, build_session_factory
from ledgerx.modules.identity.models import Credential, User
from ledgerx.modules.identity.passwords import Passwords


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LOCAL DEVELOPMENT ONLY: reset one password.")
    parser.add_argument("--email", required=True, help="Existing local account email")
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        url = make_url(settings.database_url.get_secret_value())
        # 'db' is the repository's local Compose service. Reject libpq query overrides.
        if (
            settings.environment != "development"
            or url.host not in {"localhost", "127.0.0.1", "::1", "db"}
            or url.query
        ):
            print(
                "Refused: requires development settings and a local database URL.", file=sys.stderr
            )
            return 1
        with warnings.catch_warnings():
            # Never fall back to echoed stdin when a secure terminal is unavailable.
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New password (15-128 characters): ")
            confirmation = getpass.getpass("Confirm new password: ")
        if password != confirmation:
            print("Passwords do not match; nothing changed.", file=sys.stderr)
            return 1
        credentials = CredentialsInput(email=args.email, password=password)
        encoded = Passwords().hash(credentials.password.get_secret_value())
        engine = build_engine(settings)
        try:
            with build_session_factory(engine)() as db, db.begin():
                # Match login's normalization and user-first lock order.
                user = db.scalar(
                    select(User)
                    .where(User.email_normalized == credentials.email.lower())
                    .with_for_update()
                )
                credential = (
                    db.scalar(select(Credential).where(Credential.user_id == user.id))
                    if user
                    else None
                )
                if credential is None:
                    print("No matching credential; nothing changed.", file=sys.stderr)
                    return 1
                credential.password_hash = encoded
                credential.password_changed_at = datetime.now(UTC)
        finally:
            engine.dispose()
    except ValidationError:
        print("Invalid settings, email or password (15-128 characters required).", file=sys.stderr)
        return 1
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print("Cancelled or secure terminal unavailable; nothing changed.", file=sys.stderr)
        return 1
    except Exception:
        # Do not expose credentials, driver exceptions, SQL or password/hash values.
        print(
            "Reset failed. Check the local database configuration and availability.",
            file=sys.stderr,
        )
        return 1
    print("Local development password updated. Existing sessions and other data are unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
