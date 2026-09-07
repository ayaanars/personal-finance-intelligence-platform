from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ledgerx.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_timeout=5,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000 -c timezone=UTC"},
        hide_parameters=True,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Services will explicitly own transactions; creating a session never commits."""
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
