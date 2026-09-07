from alembic import context
from sqlalchemy import create_engine, pool

from ledgerx.core.config import Settings
from ledgerx.db.base import Base

target_metadata = Base.metadata
url = Settings().database_url.get_secret_value()

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
