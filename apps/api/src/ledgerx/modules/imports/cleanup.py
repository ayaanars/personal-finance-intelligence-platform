"""Run with python -m ledgerx.modules.imports.cleanup using operator DB configuration."""

from uuid import uuid4

from ledgerx.core.config import Settings
from ledgerx.db.session import build_engine, build_session_factory
from ledgerx.modules.imports.service import purge_expired


def main() -> None:
    engine = build_engine(Settings())
    try:
        with build_session_factory(engine)() as db, db.begin():
            count = purge_expired(db, limit=100, correlation_id=uuid4())
        print(f"Expired import batches cleaned: {count}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
