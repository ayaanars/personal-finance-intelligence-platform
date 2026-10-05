"""Small global budgets, shared across workers. Never trusts client-supplied IPs."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from ledgerx.modules.identity.errors import AuthError

LIMITS = {"login": 60, "register": 10, "reset_request": 10, "reset_complete": 30}


def consume(db: Session, scope: str) -> None:
    limit = LIMITS[scope]
    with db.begin():
        attempts = db.scalar(
            text("""
            INSERT INTO auth_rate_limits (scope, window_start, attempts)
            VALUES (:scope, date_trunc('minute', statement_timestamp()), 1)
            ON CONFLICT (scope) DO UPDATE SET
                attempts = CASE WHEN auth_rate_limits.window_start =
                    date_trunc('minute', statement_timestamp())
                    THEN LEAST(auth_rate_limits.attempts + 1, :ceiling) ELSE 1 END,
                window_start = date_trunc('minute', statement_timestamp())
            RETURNING attempts
        """),
            {"scope": scope, "ceiling": limit + 1},
        )
    if attempts is not None and attempts > limit:
        raise AuthError(429, "RATE_LIMITED", "Too many attempts. Try again in one minute")
