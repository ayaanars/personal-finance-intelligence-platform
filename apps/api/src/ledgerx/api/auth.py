import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from ledgerx.api.auth_schemas import (
    CredentialsInput,
    CsrfView,
    EmptyMutation,
    ResetComplete,
    ResetRequest,
    UserView,
    WorkspaceView,
)
from ledgerx.api.auth_security import Authenticated, cookie, mutation_boundary
from ledgerx.modules.identity import rate_limit, recovery, service
from ledgerx.modules.identity.errors import AuthError
from ledgerx.modules.identity.models import User, Workspace

router = APIRouter(prefix="/api/v1", tags=["authentication"])


def auth_budget(request: Request, scope: str) -> None:
    if request.app.state.settings.environment == "production":
        with request.app.state.session_factory() as db:
            rate_limit.consume(db, scope)


def profile(user: User, workspace: Workspace) -> UserView:
    return UserView(
        id=user.id,
        email=user.email_display,
        workspace=WorkspaceView(id=workspace.id, display_name=workspace.display_name),
    )


@router.post("/auth/register", status_code=201, dependencies=[Depends(mutation_boundary)])
def register(body: CredentialsInput, request: Request) -> UserView:
    auth_budget(request, "register")
    with request.app.state.session_factory() as db:
        user, workspace = service.register(
            db,
            request.app.state.passwords,
            body.email,
            body.password.get_secret_value(),
            UUID(request.state.correlation_id),
        )
    return profile(user, workspace)


@router.post("/auth/login", status_code=204, dependencies=[Depends(mutation_boundary)])
def login(body: CredentialsInput, request: Request) -> Response:
    auth_budget(request, "login")
    settings = request.app.state.settings
    with request.app.state.session_factory() as db:
        token = service.login(
            db,
            request.app.state.passwords,
            body.email,
            body.password.get_secret_value(),
            request.cookies.get(settings.session_cookie_name),
            UUID(request.state.correlation_id),
        )
    response = Response(status_code=204)
    cookie(response, settings, token)
    return response


@router.post(
    "/auth/password-reset/request", status_code=202, dependencies=[Depends(mutation_boundary)]
)
def request_reset(body: ResetRequest, request: Request) -> dict[str, str]:
    auth_budget(request, "reset_request")
    settings = request.app.state.settings
    if settings.reset_delivery == "disabled":
        raise AuthError(503, "RECOVERY_UNAVAILABLE", "Password recovery is not configured yet")
    with request.app.state.session_factory() as db:
        token = recovery.issue(db, body.email)
    if token is not None:
        try:
            recovery.deliver(settings, body.email, token)
        except Exception:
            # Never log SMTP errors, message bodies, recipients or recovery tokens.
            logging.getLogger("ledgerx.security").error('{"event":"reset_delivery_failed"}')
    return {"message": "If the account exists, a reset link will be sent. Check your inbox."}


@router.post(
    "/auth/password-reset/complete", status_code=204, dependencies=[Depends(mutation_boundary)]
)
def complete_reset(body: ResetComplete, request: Request) -> Response:
    auth_budget(request, "reset_complete")
    with request.app.state.session_factory() as db:
        recovery.complete(
            db,
            request.app.state.passwords,
            body.token.get_secret_value(),
            body.password.get_secret_value(),
            UUID(request.state.correlation_id),
        )
    response = Response(status_code=204)
    cookie(response, request.app.state.settings, None)
    return response


@router.get("/me")
def me(context: Authenticated) -> UserView:
    return profile(context.principal.user, context.principal.workspace)


@router.get("/auth/csrf")
def csrf(context: Authenticated) -> CsrfView:
    return CsrfView(csrf_token=service.rotate_csrf(context.principal))


def revoke(context: Authenticated, request: Request, all_sessions: bool) -> Response:
    service.logout(context.db, context.principal, all_sessions, UUID(request.state.correlation_id))
    response = Response(status_code=204)
    cookie(response, request.app.state.settings, None)
    return response


@router.post("/auth/logout", status_code=204)
def logout(context: Authenticated, request: Request, body: EmptyMutation) -> Response:
    return revoke(context, request, False)


@router.post("/auth/logout-all", status_code=204)
def logout_all(context: Authenticated, request: Request, body: EmptyMutation) -> Response:
    return revoke(context, request, True)
