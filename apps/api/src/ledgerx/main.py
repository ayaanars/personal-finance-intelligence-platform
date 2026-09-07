import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ledgerx.api.auth import router as auth_router
from ledgerx.api.health import router
from ledgerx.core.config import Settings
from ledgerx.core.http import install_http_handlers
from ledgerx.db.session import build_engine, build_session_factory
from ledgerx.modules.identity.passwords import Passwords


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(configuration)
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        app.state.passwords = Passwords()
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="LedgerX API", version="0.1.0", lifespan=lifespan)
    app.state.settings = configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[configuration.first_party_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )
    install_http_handlers(app)
    app.include_router(router)
    app.include_router(auth_router)
    return app
