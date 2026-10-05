"""Issue a recovery link only to a trusted local operator, never an HTTP response."""

import argparse

from sqlalchemy.engine import make_url

from ledgerx.api.auth_schemas import ResetRequest
from ledgerx.core.config import Settings
from ledgerx.db.session import build_engine, build_session_factory
from ledgerx.modules.identity.recovery import issue


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a LOCAL development recovery link")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment != "development"
        or url.host not in {"localhost", "127.0.0.1", "::1", "db"}
        or url.query
    ):
        raise SystemExit("Requires development settings and a local database")
    email = ResetRequest(email=args.email).email
    engine = build_engine(settings)
    try:
        with build_session_factory(engine)() as db:
            token = issue(db, email)
        print(
            settings.first_party_origin + "/reset-password#token=" + token
            if token
            else "No matching active account"
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
