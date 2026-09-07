"""Transactional identity use cases. Lock order is user, then session."""

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import psycopg
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledgerx.modules.identity.errors import AuthError, unauthenticated
from ledgerx.modules.identity.models import AuthAudit, Credential, User, UserSession, Workspace
from ledgerx.modules.identity.passwords import Passwords, new_secret, secret_hash, valid_secret

IDLE_LIFETIME = timedelta(minutes=30)
ABSOLUTE_LIFETIME = timedelta(days=7)
REFRESH_INTERVAL = timedelta(minutes=1)


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Principal:
    user: User
    workspace: Workspace
    session: UserSession


def audit(db: Session, user_id: UUID | None, event: str, correlation_id: UUID) -> None:
    db.add(AuthAudit(user_id=user_id, event_code=event, correlation_id=correlation_id))


def register(
    db: Session, passwords: Passwords, email: str, password: str, correlation_id: UUID
) -> tuple[User, Workspace]:
    encoded = passwords.hash(password)
    try:
        with db.begin():
            user = User(email_normalized=email.lower(), email_display=email, status="active")
            db.add(user)
            db.flush()
            workspace = Workspace(owner_user_id=user.id, display_name="Private workspace")
            db.add(workspace)
            db.add(Credential(user_id=user.id, password_hash=encoded))
            audit(db, user.id, "registered", correlation_id)
            db.flush()
        return user, workspace
    except IntegrityError as exc:
        if isinstance(exc.orig, psycopg.Error) and (
            exc.orig.diag.constraint_name == "uq_users_email_normalized"
        ):
            raise AuthError(
                409, "REGISTRATION_FAILED", "Registration could not be completed"
            ) from None
        raise


def login(
    db: Session,
    passwords: Passwords,
    email: str,
    password: str,
    prior_token: str | None,
    correlation_id: UUID,
) -> str:
    # Verify the expensive hash outside the row lock, then recheck the credential
    # under lock. A concurrent credential change must invalidate this attempt.
    with db.begin():
        row = db.execute(
            select(User.id, Credential.password_hash)
            .join(Credential, Credential.user_id == User.id)
            .where(User.email_normalized == email.lower())
        ).one_or_none()
    encoded = row.password_hash if row else None
    verified = passwords.verify(encoded, password)
    replacement = (
        passwords.hash(password)
        if verified and encoded is not None and passwords.hasher.check_needs_rehash(encoded)
        else None
    )
    token = new_secret()
    success = False
    with db.begin():
        user = db.scalar(select(User).where(User.id == row.id).with_for_update()) if row else None
        credential = (
            db.scalar(select(Credential).where(Credential.user_id == user.id)) if user else None
        )
        if (
            verified
            and user is not None
            and user.status == "active"
            and credential is not None
            and credential.password_hash == encoded
        ):
            now = utcnow()
            if replacement:
                credential.password_hash = replacement
            if valid_secret(prior_token):
                db.execute(
                    update(UserSession)
                    .where(
                        UserSession.user_id == user.id,
                        UserSession.token_hash == secret_hash(str(prior_token)),
                        UserSession.revoked_at.is_(None),
                    )
                    .values(revoked_at=now, revoke_reason="login_rotation")
                )
            db.add(
                UserSession(
                    user_id=user.id,
                    token_hash=secret_hash(token),
                    csrf_secret_hash=secret_hash(new_secret()),
                    created_at=now,
                    last_seen_at=now,
                    idle_expires_at=now + IDLE_LIFETIME,
                    absolute_expires_at=now + ABSOLUTE_LIFETIME,
                )
            )
            audit(db, user.id, "login", correlation_id)
            success = True
        else:
            # Do not store attempted emails or distinguish unknown from wrong password.
            audit(db, None, "login_failed", correlation_id)
    if not success:
        raise AuthError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
    return token


def authenticate(db: Session, token: str | None, csrf: str | None, unsafe: bool) -> Principal:
    """Caller owns transaction through the protected operation and commit."""
    if not valid_secret(token):
        raise unauthenticated()
    digest = secret_hash(str(token))
    owner = db.scalar(select(UserSession.user_id).where(UserSession.token_hash == digest))
    if owner is None:
        raise unauthenticated()
    user = db.scalar(select(User).where(User.id == owner).with_for_update())
    session = db.scalar(
        select(UserSession)
        .where(UserSession.user_id == owner, UserSession.token_hash == digest)
        .with_for_update()
    )
    now = utcnow()
    if (
        user is None
        or user.status != "active"
        or session is None
        or session.revoked_at is not None
        or now >= session.idle_expires_at
        or now >= session.absolute_expires_at
    ):
        raise unauthenticated()
    if unsafe and (
        not valid_secret(csrf)
        or not hmac.compare_digest(secret_hash(str(csrf)), session.csrf_secret_hash)
    ):
        raise AuthError(403, "CSRF_INVALID", "CSRF validation failed")
    workspace = db.scalar(select(Workspace).where(Workspace.owner_user_id == user.id))
    if workspace is None:
        raise unauthenticated()
    if now - session.last_seen_at >= REFRESH_INTERVAL:
        session.last_seen_at = now
        session.idle_expires_at = min(now + IDLE_LIFETIME, session.absolute_expires_at)
    return Principal(user, workspace, session)


def rotate_csrf(principal: Principal) -> str:
    token = new_secret()
    principal.session.csrf_secret_hash = secret_hash(token)
    return token


def logout(db: Session, principal: Principal, all_sessions: bool, correlation_id: UUID) -> None:
    reason = "logout_all" if all_sessions else "logout"
    query = update(UserSession).where(
        UserSession.user_id == principal.user.id, UserSession.revoked_at.is_(None)
    )
    if not all_sessions:
        query = query.where(UserSession.id == principal.session.id)
    # Flush a possible idle refresh before the bulk update; no stale ORM write can
    # subsequently restore revocation fields.
    db.flush()
    db.execute(query.values(revoked_at=utcnow(), revoke_reason=reason))
    audit(db, principal.user.id, reason, correlation_id)
