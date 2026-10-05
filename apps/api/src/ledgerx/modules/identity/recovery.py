"""One-time password recovery. Transactions always lock user before token/session."""

import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ledgerx.core.config import Settings
from ledgerx.modules.identity.errors import AuthError
from ledgerx.modules.identity.models import Credential, User, UserSession
from ledgerx.modules.identity.passwords import Passwords, new_secret, secret_hash, valid_secret
from ledgerx.modules.identity.recovery_models import PasswordReset
from ledgerx.modules.identity.service import audit, utcnow


def issue(db: Session, email: str) -> str | None:
    token = new_secret()
    with db.begin():
        user = db.scalar(
            select(User).where(User.email_normalized == email.lower()).with_for_update()
        )
        if user is None or user.status != "active":
            return None
        # One outstanding token per account; no unbounded recovery history.
        db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
        db.add(
            PasswordReset(
                token_hash=secret_hash(token),
                user_id=user.id,
                expires_at=utcnow() + timedelta(minutes=20),
            )
        )
    return token


def complete(
    db: Session,
    passwords: Passwords,
    token: str,
    password: str,
    correlation_id: UUID | None = None,
) -> None:
    invalid = AuthError(400, "RESET_INVALID", "Reset link is invalid or expired")
    if not valid_secret(token):
        raise invalid
    digest = secret_hash(token)
    # Avoid holding locks during expensive password hashing.
    encoded = passwords.hash(password)
    with db.begin():
        owner = db.scalar(select(PasswordReset.user_id).where(PasswordReset.token_hash == digest))
        if owner is None:
            raise invalid
        user = db.scalar(select(User).where(User.id == owner).with_for_update())
        reset = db.scalar(
            select(PasswordReset).where(PasswordReset.token_hash == digest).with_for_update()
        )
        now = utcnow()
        if (
            user is None
            or user.status != "active"
            or reset is None
            or reset.used_at is not None
            or reset.expires_at <= now
        ):
            raise invalid
        credential = db.scalar(select(Credential).where(Credential.user_id == owner))
        if credential is None:
            raise invalid
        credential.password_hash = encoded
        credential.password_changed_at = now
        db.execute(update(PasswordReset).where(PasswordReset.user_id == owner).values(used_at=now))
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == owner, UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason="logout_all")
        )
        audit(db, owner, "password_reset", correlation_id or uuid4())
    logging.getLogger("ledgerx.security").info('{"event":"password_reset_completed"}')


def deliver(settings: Settings, email: str, token: str) -> None:
    """Integration point: authenticated SMTP, mandatory TLS, no message logging."""
    message = EmailMessage()
    message["Subject"] = "Reset your LedgerX password"
    message["From"] = str(settings.reset_from_email)
    message["To"] = email
    message.set_content(
        "This one-time link expires in 20 minutes. Ignore it if you did not request it.\n\n"
        + settings.first_party_origin
        + "/reset-password#token="
        + token
    )
    with smtplib.SMTP(str(settings.smtp_host), settings.smtp_port, timeout=10) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(
            str(settings.smtp_username),
            settings.smtp_password.get_secret_value() if settings.smtp_password else "",
        )
        smtp.send_message(message)
