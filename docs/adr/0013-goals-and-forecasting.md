# ADR 0013: Monthly goals and deterministic forecasts

Status: Implemented for the explicitly requested Phase 17, 16 September 2026.

## Context

Users need a practical month-end outlook and editable targets. Existing finalized
import history, money definitions, owner locks, and recurring detection provide
the foundation. Forecasts are advisory imported-activity estimates, never ledger
entries, balances, guaranteed income, or instructions to move money.

## Decision

Store one spending ceiling and one net cash flow floor per user, workspace, ISO
currency and calendar month. Positive targets use NUMERIC(20,4), decimal-string
transport, and the existing AED/USD/EUR/GBP allowlist. Goals can be edited,
deactivated or removed. They do not automatically recur into another month.
Net cash flow retains existing semantics: all imported inflows minus all outflows,
including transfers and cash withdrawals. It is not an account savings balance.

GET /api/v1/goals?month=YYYY-MM returns goals and currency-separated forecasts.
The omitted month defaults to the current UTC month, even without activity.
PUT /api/v1/goals atomically creates/replaces a goal by its natural key; DELETE
removes that owned key and is repeatable. Every write uses existing authentication,
origin, JSON and CSRF boundaries and the authenticated owner's transaction lock.
Owner/workspace composite foreign keys and primary keys enforce isolation and
uniqueness. Serialized replacements deliberately use last-write-wins semantics;
these are user preferences, not financial postings. Same-payload retries have the
same result. No accounting or imported records are changed by goal operations.
The additive migration refuses downgrade while saved goals exist.

## Forecast method, version 1

- Read existing finalized, owner/workspace-scoped history with effective categories
  and the same legacy interpretation fallback. Partition by currency before any
  calculation. Ignore facts after the UTC as-of date or selected month end.
- Actual spending uses the existing gross spending definition (excludes Transfers
  and Cash / ATM). Outflow includes every negative fact. Returns do not reduce
  gross spending; positive facts contribute to net cash flow.
- Current variable daily pace divides current non-recurring activity by elapsed
  calendar days, including today. Look back at most three consecutive prior months.
  A usable month needs an observation by day 7 and another on/after day 21. Gaps
  break the run; these date bounds do not establish statement completeness.
- With three usable months, blend the current daily pace equally with the mean of
  their daily rates (each uses its own calendar length). Otherwise use current pace
  alone. Multiply by remaining calendar days and add actuals. Apply the same method
  to spending, outflow and inflows; projected net is actual net plus future inflows
  minus future outflow. When positive Income totals in the three usable prior
  months are all within 5% of their positive median, expected remaining income is
  max(median minus current observed Income, zero), counted once instead of applying
  daily pace to Income. Other inflows still use pace. This avoids predicting a
  second already-received salary. No unpaid income is added to a past month.
  Irregular income and the absence of guaranteed payment dates remain limitations.
- Reuse the existing conservative monthly recurrence test: three consecutive
  months, one charge per merchant/month, 21–40-day gaps, amounts within 5% of median,
  known merchant, spending only, excluding return signals. A pattern qualified
  through the preceding month can supply an outstanding commitment. Median day of
  the three charges, clamped to month end, estimates its due date. Current-month
  patterns may describe already observed charges, never invent future ones.
- Remove qualified merchants' spending from variable pace (including reference
  months); retain actual charges once, then add each still-future due commitment
  once to both projected spending and outflow. Any observed charge suppresses a
  future charge for that merchant. Overdue/unobserved charges remain visible but
  are not rescheduled. This intentionally does not model ambiguous multiple charges.
- Past months return imported actual outcomes. Future months and months with no
  current activity have unavailable projections; absence is not a zero forecast.
- Decimal local precision 60; half-even four-place response formatting only at the
  boundary. UI estimates round to whole currency units and use an approximation
  marker. Exact actuals and targets retain their precision. Chart geometry uses
  BigInt decimal units, with only bounded coordinates converted to numbers.

## Quality and goal rules

Display observed date span, latest imported date, elapsed calendar days and usable
prior-month count. Early estimate is the fallback. Developing requires at least
8 days between the first and last current observations (inclusive), latest activity
within 3 days of as-of, and at least one usable prior month. Stronger requires
21 observed-span days, the same freshness condition, and three usable prior months.
Neither label is a probability or a completeness claim. Past periods say observed
outcome; unavailable forecasts say not enough current-month activity.

The progress reference is target × elapsed days / calendar days. Spending is off
track if actuals already exceed target, or both actual progress and projected total
exceed their respective references. Net cash flow is off track if actual progress
and projected total are both below their references. Exactly one unfavorable
comparison means watch closely, otherwise on track. Boundaries are inclusive in
the favorable direction. No projection means awaiting activity; inactive goals
have no active status. Uneven income timing can create an early watch/off-track
label: this is disclosed and does not trigger financial action.

## UI and supported insights

Authenticated /app/goals uses the existing session-scoped period/currency provider.
Goal cards show exact targets/actuals, approximate projections, status, progress
bars and projection markers; a compact straight-line actual-to-projection visual
is explicitly labeled, not represented as an observed daily trajectory. Recurring
charges show observed, still expected or overdue states and human-readable dates.
Overview gets one compact summary and Insights reuses it. Only actual supported
commitment dominance is highlighted (remaining commitments exceed half projected
remaining outflow); no causal category attribution is fabricated. Navigation places
Goals & Forecast after Relationships and before Recurring in Intelligence.

## Alternatives and consequences

Category targets, rolling/recurring goals, inferred paydays, historical intra-month
curve fitting, probabilistic intervals, ML, external forecast services and workers
are deferred. A fixed deterministic blend is maintainable and testable but can be
misleading with partial imports, one-off spending and uneven income. Coverage,
quality and method are visible; users can compare forecasts with their own plans.
No additional dependency, infrastructure, currency conversion or ledger semantics
is introduced. History remains bounded by calendar window rather than row count;
large imports retain the existing loader's memory limitation.
