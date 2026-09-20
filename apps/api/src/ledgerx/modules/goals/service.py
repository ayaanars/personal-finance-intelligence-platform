from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ledgerx.modules.analytics.calculations import money, month_name
from ledgerx.modules.analytics.intelligence_service import load_history
from ledgerx.modules.goals.forecast import Forecast, forecast, goal_status
from ledgerx.modules.goals.models import MonthlyGoal
from ledgerx.modules.identity.service import Principal


class GoalKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    currency: Literal["AED", "USD", "EUR", "GBP"]
    kind: Literal["spending", "net_cash_flow"]

    @field_validator("month")
    @classmethod
    def valid_month(cls, value: str) -> str:
        date.fromisoformat(value + "-01")
        return value


class GoalInput(GoalKey):
    target: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    active: bool

    @field_validator("target", mode="before")
    @classmethod
    def decimal_string(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("Use a decimal string")
        return value


class GoalView(BaseModel):
    kind: str
    currency: str
    target: str
    active: bool
    actual: str
    projected: str | None
    status: str
    pace_target: str


class Plan(BaseModel):
    month: str
    available_months: list[str]
    currencies: list[Forecast]
    goals: list[GoalView]


def save(db: Session, principal: Principal, body: GoalInput) -> None:
    # Natural-key PUT is replay-safe. Authentication holds the owner lock through commit.
    key = (
        principal.user.id,
        principal.workspace.id,
        date.fromisoformat(body.month + "-01"),
        body.currency,
        body.kind,
    )
    goal = db.get(MonthlyGoal, key)
    if goal is None:
        goal = MonthlyGoal(
            user_id=key[0], workspace_id=key[1], month=key[2], currency=key[3], kind=key[4]
        )
        db.add(goal)
    goal.target, goal.active = body.target, body.active
    db.flush()


def remove(db: Session, principal: Principal, key: GoalKey) -> None:
    db.execute(
        delete(MonthlyGoal).where(
            MonthlyGoal.user_id == principal.user.id,
            MonthlyGoal.workspace_id == principal.workspace.id,
            MonthlyGoal.month == date.fromisoformat(key.month + "-01"),
            MonthlyGoal.currency == key.currency,
            MonthlyGoal.kind == key.kind,
        )
    )


def plan(db: Session, principal: Principal, month: str | None) -> Plan:
    today = datetime.now(UTC).date()
    selected = month or month_name(today)
    _, available, observations = load_history(db, principal, selected)
    all_goals = list(
        db.scalars(
            select(MonthlyGoal).where(
                MonthlyGoal.user_id == principal.user.id,
                MonthlyGoal.workspace_id == principal.workspace.id,
            )
        )
    )
    goals = [g for g in all_goals if month_name(g.month) == selected]
    currencies = sorted(set(observations) | {g.currency for g in goals})
    forecasts = [
        forecast(observations.get(c, []), date.fromisoformat(selected + "-01"), today, c)
        for c in currencies
    ]
    views = []
    for g in goals:
        f = next(f for f in forecasts if f.currency == g.currency)
        actual = f.actual_spending if g.kind == "spending" else f.actual_net_cash_flow
        projected = f.projected_spending if g.kind == "spending" else f.projected_net_cash_flow
        views.append(
            GoalView(
                kind=g.kind,
                currency=g.currency,
                target=money(g.target),
                active=g.active,
                actual=actual,
                projected=projected,
                status=goal_status(
                    g.kind,
                    g.target,
                    Decimal(actual),
                    Decimal(projected) if projected is not None else None,
                    f.elapsed_days,
                    f.days_in_month,
                )
                if g.active
                else "Inactive",
                pace_target=money(g.target * Decimal(f.elapsed_days) / Decimal(f.days_in_month)),
            )
        )
    return Plan(
        month=selected,
        available_months=sorted(
            set(available)
            | {month_name(g.month) for g in all_goals}
            | {selected, month_name(today)},
            reverse=True,
        ),
        currencies=forecasts,
        goals=sorted(views, key=lambda g: (g.currency, g.kind)),
    )
