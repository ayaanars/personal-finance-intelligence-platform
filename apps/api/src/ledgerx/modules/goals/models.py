from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ledgerx.db.base import Base


class MonthlyGoal(Base):
    __tablename__ = "monthly_goals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "workspace_id"],
            ["workspaces.owner_user_id", "workspaces.id"],
            name="fk_monthly_goals_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint("kind IN ('spending','net_cash_flow')", name="kind"),
        CheckConstraint("currency IN ('AED','USD','EUR','GBP')", name="currency"),
        CheckConstraint("target > 0", name="target"),
        CheckConstraint("EXTRACT(DAY FROM month) = 1", name="month"),
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(primary_key=True)
    month: Mapped[date] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    target: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    active: Mapped[bool]
