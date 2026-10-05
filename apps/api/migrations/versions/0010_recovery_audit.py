"""Preserve password recovery in the append-only authentication audit."""

import sqlalchemy as sa
from alembic import op

revision = "0010_recovery_audit"
down_revision = "0009_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_auth_audit_events_event_code"), "auth_audit_events", type_="check")
    op.create_check_constraint(
        op.f("ck_auth_audit_events_event_code"),
        "auth_audit_events",
        "event_code IN ('registered', 'login', 'login_failed', 'logout', 'logout_all', "
        "'password_reset')",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM auth_audit_events WHERE event_code = 'password_reset')"
        )
    ):
        raise RuntimeError(
            "Recorded password resets require a forward migration; preserve the audit"
        )
    op.drop_constraint(op.f("ck_auth_audit_events_event_code"), "auth_audit_events", type_="check")
    op.create_check_constraint(
        op.f("ck_auth_audit_events_event_code"),
        "auth_audit_events",
        "event_code IN ('registered', 'login', 'login_failed', 'logout', 'logout_all')",
    )
