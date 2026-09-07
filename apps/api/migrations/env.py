from alembic import context
from sqlalchemy import Connection, create_engine, pool

from ledgerx.core.config import Settings
from ledgerx.db import models  # noqa: F401
from ledgerx.db.base import Base

target_metadata = Base.metadata


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_server_default=True
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        run_migrations(supplied_connection)
    else:
        engine = create_engine(
            Settings().database_url.get_secret_value(),
            poolclass=pool.NullPool,
            hide_parameters=True,
            connect_args={"options": "-c timezone=UTC"},
        )
        try:
            with engine.connect() as connection:
                run_migrations(connection)
        finally:
            engine.dispose()
