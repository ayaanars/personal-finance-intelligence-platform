from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from ledgerx.api.auth_schemas import (
    CredentialsInput,
    CsrfView,
    EmptyMutation,
    UserView,
    WorkspaceView,
)
from ledgerx.api.auth_security import Authenticated, cookie, mutation_boundary
from ledgerx.modules.identity import service
from ledgerx.modules.identity.models import User, Workspace

router = APIRouter(prefix="/api/v1", tags=["authentication"])


def profile(user: User, workspace: Workspace) -> UserView:
    return UserView(
        id=user.id,
        email=user.email_display,
        workspace=WorkspaceView(id=workspace.id, display_name=workspace.display_name),
    )


@router.post("/auth/register", status_code=201, dependencies=[Depends(mutation_boundary)])
def register(body: CredentialsInput, request: Request) -> UserView:
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
