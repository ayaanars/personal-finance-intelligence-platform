"""Explicit release command, using a separate migration credential when provided."""

import logging
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, pool, text

from ledgerx.core.config import Settings


def main() -> None:
    migration_url = os.environ.pop("LEDGERX_MIGRATION_DATABASE_URL", None)
    if migration_url:
        os.environ["LEDGERX_DATABASE_URL"] = migration_url
    settings = Settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    logger = logging.getLogger("ledgerx.migrations")
    engine = create_engine(
        settings.database_url.get_secret_value(),
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 10,
            "options": "-c timezone=UTC -c lock_timeout=15000 -c statement_timeout=120000",
        },
    )
    try:
        logger.info('{"event":"migration_started"}')
        with engine.begin() as connection:
            # Fixed application lock; concurrent releases fail without racing DDL.
            if not connection.scalar(text("SELECT pg_try_advisory_xact_lock(60212021)")):
                raise RuntimeError("Another LedgerX migration is running")
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
        logger.info('{"event":"migration_completed"}')
    except Exception:
        logger.error('{"event":"migration_failed"}')
        raise SystemExit("Migration failed; application release must stop") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
