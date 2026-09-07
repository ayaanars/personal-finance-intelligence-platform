import json
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger("ledgerx.http")


def install_http_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = "SERVICE_NOT_READY" if exc.status_code == 503 else "HTTP_ERROR"
        message = (
            "Service is not ready" if exc.status_code == 503 else "Request could not be completed"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "correlation_id": request.state.correlation_id,
                }
            },
            headers=exc.headers,
        )

    @app.middleware("http")
    async def correlate(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            correlation_id = str(UUID(request.headers.get("X-Request-ID", "")))
        except ValueError:
            correlation_id = str(uuid4())
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An internal error occurred",
                        "correlation_id": correlation_id,
                    }
                },
            )
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "event": "request_completed",
                    "correlation_id": correlation_id,
                    "status": response.status_code,
                }
            )
        )
        return response
