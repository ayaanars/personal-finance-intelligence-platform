"""Conservative monthly payment-pattern evidence, not contractual obligations."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from pydantic import BaseModel

from ledgerx.modules.analytics.calculations import ZERO, money, month_name, percent, shift_month
from ledgerx.modules.analytics.intelligence import Observation


class RecurringEvidence(BaseModel):
    identifier: str
    day: str
    amount: str


class RecurringPayment(BaseModel):
    merchant: str
    typical_amount: str
    annual_estimate: str
    frequency: Literal["monthly"] = "monthly"
    newly_qualified: bool | None
    evidence: list[RecurringEvidence]
    reason: str = (
        "One charge in each of three consecutive months; 21-40-day gaps; "
        "amounts within 5% of median."
    )
    share_percent: str | None = None


CandidateReason = Literal[
    "fewer_than_three_months", "multiple_charges", "timing_not_regular", "amounts_vary"
]


class Candidate(BaseModel):
    merchant: str
    reason: CandidateReason


class RecurringReport(BaseModel):
    state: Literal[
        "likely_recurring", "insufficient_history", "insufficient_evidence", "no_activity"
    ]
    payments: list[RecurringPayment]
    candidates: list[Candidate]
    monthly_estimate: str
    annual_estimate: str
    matched_spending: str
    other_spending: str
    matched_share_percent: str | None
    method: str = (
        "Likely monthly patterns, not confirmed subscriptions or fixed obligations. Known "
        "merchants only; transfers, cash and return signals excluded. Annual estimates assume "
        "12 unchanged payments. Multiple charges at a merchant are left unresolved."
    )


def recurring(rows: list[Observation], selected: date) -> RecurringReport:
    """Evaluate a rolling three-month window ending in the selected activity month."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        selected_month = month_name(selected)
        observed = {month_name(row.day) for row in rows}
        grouped: dict[str, dict[str, list[Observation]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            if row.spending and row.merchant and not row.return_signal:
                grouped[row.merchant][month_name(row.day)].append(row)

        def evaluate(merchant: str, end: date) -> tuple[list[Observation], CandidateReason | None]:
            months = [month_name(shift_month(end, offset)) for offset in (-2, -1, 0)]
            entries = [grouped[merchant].get(month, []) for month in months]
            if len(set(months)) < 3 or any(not entry for entry in entries):
                return [], "fewer_than_three_months"
            if any(len(entry) != 1 for entry in entries):
                return [], "multiple_charges"
            evidence = [entry[0] for entry in entries]
            if any(
                not 21 <= (b.day - a.day).days <= 40
                for a, b in zip(evidence, evidence[1:], strict=False)
            ):
                return [], "timing_not_regular"
            amounts = sorted(-row.amount for row in evidence)
            median = amounts[1]
            if any(abs(value - median) > median * Decimal("0.05") for value in amounts):
                return [], "amounts_vary"
            return evidence, None

        payments: list[RecurringPayment] = []
        candidates: list[Candidate] = []
        matched = ZERO
        for merchant in sorted(grouped):
            if selected_month not in grouped[merchant]:
                continue
            evidence, reason = evaluate(merchant, selected)
            if reason is not None:
                candidates.append(Candidate(merchant=merchant, reason=reason))
                continue
            median = sorted(-row.amount for row in evidence)[1]
            previous_start = month_name(shift_month(selected, -3))
            previous_evidence, _ = evaluate(merchant, shift_month(selected, -1))
            payments.append(
                RecurringPayment(
                    merchant=merchant,
                    typical_amount=money(median),
                    annual_estimate=money(median * 12),
                    newly_qualified=(not bool(previous_evidence))
                    if previous_start in observed
                    and previous_start < month_name(shift_month(selected, -2))
                    else None,
                    evidence=[
                        RecurringEvidence(
                            identifier=row.identifier,
                            day=row.day.isoformat(),
                            amount=money(-row.amount),
                        )
                        for row in evidence
                    ],
                )
            )
            matched -= evidence[-1].amount
        payments.sort(key=lambda item: (-Decimal(item.typical_amount), item.merchant))
        monthly = sum((Decimal(item.typical_amount) for item in payments), ZERO)
        for payment in payments:
            payment.share_percent = percent(Decimal(payment.typical_amount), monthly)
        spending = sum(
            (-r.amount for r in rows if month_name(r.day) == selected_month and r.spending), ZERO
        )
        months = {month_name(shift_month(selected, offset)) for offset in (-2, -1, 0)}
        return RecurringReport(
            state="no_activity"
            if selected_month not in observed
            else "likely_recurring"
            if payments
            else "insufficient_history"
            if len(months) < 3 or not months <= observed
            else "insufficient_evidence",
            payments=payments,
            candidates=candidates[:5],
            monthly_estimate=money(monthly),
            annual_estimate=money(monthly * 12),
            matched_spending=money(matched),
            other_spending=money(spending - matched),
            matched_share_percent=percent(matched, spending),
        )
