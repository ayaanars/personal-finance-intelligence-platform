from typing import Literal

from pydantic import BaseModel


class Totals(BaseModel):
    inflows: str
    income: str
    other_inflows: str
    outflow: str
    net_cash_flow: str
    spending: str
    transfers_out: str
    cash_out: str
    transaction_count: int


class Breakdown(BaseModel):
    name: str | None
    amount: str
    transaction_count: int
    share_percent: str | None


class Change(BaseModel):
    name: str
    current: str
    previous: str
    delta: str
    percent: str | None
    scale_percent: str = "0.00"


class Comparison(BaseModel):
    state: Literal["available", "insufficient_history", "no_activity"]
    previous_month: str
    metrics: list[Change]
    categories: list[Change]


class Insight(BaseModel):
    code: str
    text: str
    metric: str
    subject: str | None
    current: str
    previous: str
    delta: str
    total_delta: str | None = None
    contribution_percent: str | None = None


class TrendPoint(BaseModel):
    month: str
    totals: Totals
    spending_scale_percent: str
    income_scale_percent: str = "0.00"
    outflow_scale_percent: str = "0.00"


class CurrencyOverview(BaseModel):
    currency: str
    totals: Totals
    categories: list[Breakdown]
    top_merchants: list[Breakdown]
    comparison: Comparison
    insights: list[Insight]
    trend: list[TrendPoint]
    observed_start: str | None
    observed_end: str | None


class Overview(BaseModel):
    month: str | None
    available_months: list[str]
    window_start: str | None
    currencies: list[CurrencyOverview]
    methodology_version: Literal["intelligence-v1"] = "intelligence-v1"
    coverage_note: str = (
        "Based on finalized imported activity, which may cover partial months or overlapping "
        "statements. Categories reflect your current corrections. This is not an account balance."
    )
