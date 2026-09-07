"""Cookie/CSRF transport and reusable transactional authentication dependency."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from ledgerx.core.config import Settings
from ledgerx.modules.identity.errors import AuthError
from ledgerx.modules.identity.service import ABSOLUTE_LIFETIME, Principal, authenticate

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def check_origin(request: Request) -> None:
    settings: Settings = request.app.state.settings
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin
    if candidate is None and referer is not None:
        try:
            parsed = urlsplit(referer)
            candidate = f"{parsed.scheme}://{parsed.netloc}"
        except ValueError:
            candidate = "invalid"
    if candidate is not None and candidate != settings.first_party_origin:
        raise AuthError(403, "ORIGIN_INVALID", "Request origin is not permitted")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise AuthError(403, "ORIGIN_INVALID", "Request origin is not permitted")


def mutation_boundary(request: Request) -> None:
    check_origin(request)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise AuthError(415, "JSON_REQUIRED", "Use application/json")


def cookie(response: Response, settings: Settings, token: str | None) -> None:
    if token is None:
        response.delete_cookie(
            settings.session_cookie_name,
            path="/",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )
    else:
        response.set_cookie(
            settings.session_cookie_name,
            token,
            max_age=int(ABSOLUTE_LIFETIME.total_seconds()),
            path="/",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )


@dataclass(frozen=True)
class AuthContext:
    db: Session
    principal: Principal


def authenticated_context(request: Request) -> Iterator[AuthContext]:
    unsafe = request.method not in SAFE_METHODS
    if unsafe:
        mutation_boundary(request)
    else:
        check_origin(request)
    settings: Settings = request.app.state.settings
    with request.app.state.session_factory() as db, db.begin():
        principal = authenticate(
            db,
            request.cookies.get(settings.session_cookie_name),
            request.headers.get("x-csrf-token"),
            unsafe,
        )
        yield AuthContext(db, principal)


# Commit (or rollback) before sending a response, retaining locks through the use case.
Authenticated = Annotated[AuthContext, Depends(authenticated_context, scope="function")]
