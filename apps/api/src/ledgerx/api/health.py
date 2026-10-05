import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from ledgerx.db.revision import EXPECTED_SCHEMA_REVISION

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/live", response_model=HealthResponse)
def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
def ready(request: Request) -> HealthResponse:
    engine: Engine = request.app.state.engine
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            if request.app.state.settings.environment == "production" and list(
                connection.scalars(text("SELECT version_num FROM alembic_version"))
            ) != [EXPECTED_SCHEMA_REVISION]:
                logging.getLogger("ledgerx.health").error('{"event":"schema_not_ready"}')
                raise HTTPException(status_code=503, detail="Service is not ready")
    except SQLAlchemyError:
        logging.getLogger("ledgerx.health").error('{"event":"database_not_ready"}')
        raise HTTPException(status_code=503, detail="Service is not ready") from None
    return HealthResponse(status="ok")
