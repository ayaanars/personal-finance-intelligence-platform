import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ledgerx.api.analytics import router as analytics_router
from ledgerx.api.auth import router as auth_router
from ledgerx.api.goals import router as goals_router
from ledgerx.api.health import router
from ledgerx.api.imports import router as imports_router
from ledgerx.api.transactions import router as transactions_router
from ledgerx.core.config import Settings
from ledgerx.core.http import install_http_handlers
from ledgerx.db.session import build_engine, build_session_factory
from ledgerx.modules.identity.passwords import Passwords


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()
    logging.basicConfig(level=configuration.log_level, format="%(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(configuration)
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        app.state.passwords = Passwords()
        logging.getLogger("ledgerx.lifecycle").info('{"event":"startup"}')
        try:
            yield
        finally:
            engine.dispose()

    production = configuration.environment == "production"
    app = FastAPI(
        title="LedgerX API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.state.settings = configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[configuration.first_party_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-ID",
            "X-Filename",
            "Idempotency-Key",
            "If-Match",
            "X-Column-Mapping",
        ],
    )
    install_http_handlers(app)
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(imports_router)
    app.include_router(transactions_router)
    app.include_router(analytics_router)
    app.include_router(goals_router)
    return app
