# ADR 0011: Descriptive longitudinal relationships

Status: Implemented for Phase 15, 10 September 2026.

## Context

The user requests a focused, explainable view of dimensions repeatedly observed
together, with no causal claims or new infrastructure. Phase 12 monthly accounting
and recurring semantics remain authoritative. No discretionary-spending taxonomy
has been approved; this phase does not invent one.

## Decision

`GET /api/v1/analytics/relationships?month=YYYY-MM` uses the existing authenticated,
owner/workspace-scoped, finalized-import history loader. Optional month defaults
to the latest imported month. Its output window is that month and 12 preceding
calendar months. Two additional months are read only to warm up the existing
three-month recurring detector. Phase 12/14 callers keep their seven-month window.
No new dependencies, writes, migrations, caches, workers or models are introduced.

Within each currency, existing `Bucket`/`Activity` arithmetic supplies spending,
outflow, cash outflow, categories and net cash flow. Existing `behaviour()` supplies
Saturday/Sunday spending. Existing `recurring()` supplies qualified monthly pattern
estimates. Facts are keyed by transaction identifier once before any aggregation;
overlapping views do not multiply observations. Separate legitimate fact identifiers
remain separate purchases. This does not claim to resolve duplicate source uploads
beyond the established importer behavior. Manual categories and legacy understanding
fallback remain effective inputs.

Five fixed comparisons avoid an unrestricted search through every pair:

| Comparison | Interpretation limits |
| --- | --- |
| Spending / net cash flow | Spending is part of outflow, which is subtracted from net cash flow; shared arithmetic is explicit. |
| Weekend spending / total outflow | Part/whole overlap is explicit. Weekend means Saturday/Sunday, not an inferred work schedule. |
| Cash withdrawals / spending | Cash / ATM is excluded from spending. Withdrawal records do not reveal where cash was spent. |
| Likely recurring monthly amount / net cash flow | Only months with qualified patterns. A failed qualification is missing, never zero; the qualified merchant set can change. Estimates are not contracts or available balances. |
| Food & Dining change / net cash-flow change | Absolute changes between adjacent observed calendar months only. Shared arithmetic and overlapping month pairs are disclosed. |

Missing calendar months remain absent. A category missing from an otherwise
observed month retains the existing zero-imported-spending definition; that does
not establish complete bank coverage. Change pairs never bridge gaps. No normalization
for partial month duration or fabricated full-month extrapolation is applied.

## Statistical method and gates (relationships-v1)

Centered Pearson correlation is calculated with Decimal precision 60, including
the square root; no monetary values become floats. At least six usable monthly
pairs are required, and both dimensions must vary. Findings require absolute r
at least 0.65. Removing any single pair must preserve direction and absolute r
at least 0.35. This sensitivity screen avoids presenting a relationship wholly
driven by one month; it is not a significance test or confidence interval.

Evidence groups split X strictly above its median versus at/below the median.
Each group needs at least three observations; ties are never split arbitrarily.
The direction of the Y group-mean difference must agree with the correlation.
Means and median use existing four-decimal half-even presentation boundaries;
descriptive r is returned to three decimal places. No confidence/probability
percentage or p-value is manufactured. Points, exact months, group memberships,
means, caveats and eligible sample counts are returned.

Cards rank by absolute displayed r, then sample count, then stable code. Weak,
constant, insufficient and single-month-sensitive comparisons stay out of the
feed; their screening states remain available in the coverage disclosure.
At 12 or more usable observations, an earlier group and the recent six are
evaluated separately with the same correlation and leave-one-out gates. The UI
reports direction or no clear pattern, and explicitly disclaims a statistically
established change. This earlier/recent check is descriptive; overlapping change
pairs are not independent samples.

These thresholds are initial conservative presentation heuristics, not proof of
reliability. Six monthly observations can still be misleading due to common time
trends, seasonality, incomplete statements, income variation and selection effects.
Displaying five predeclared associations does not remove multiple-comparison risk.
The UI discloses these observations as associations, never independent effects,
causes, predictions or financial-health judgments.

## Frontend and API

The authenticated `/app/relationships` page uses the shared period/currency state
and runtime-validated API schema. Ranked cards offer keyboard-operable monthly
scatter inspection, paired trend charts with separately labeled scales and gaps,
above-median comparison panels, exact evidence tables and methodology/evolution
disclosures. Geometry alone uses bounded numeric coordinates. Money remains strings
and BigInt in presentation. Existing forest/mint styles and reduced-motion behavior
are preserved.

Insights displays only the first supported relationship and a link. Overview is
unchanged. Navigation groups are Intelligence (Overview, Insights, Trends, Unusual
activity, Relationships, Recurring, Behaviour) and Data (Transactions, Import).
All existing routes and session teardown behavior remain.

Response fields: `month`, `window_start`, `available_months`, `minimum_observations`,
`methodology_version`, `coverage_note`, and per-currency `state`, `observed_months`,
`missing_months`, `items`, `screening`. Private/no-store, origin checks and strict
query validation match other analytics endpoints. No caller-supplied owner is accepted.

## Alternatives, verification and deferrals

Recomputing authoritative money in the frontend and creating independent monthly
baselines were rejected. Arbitrary pairwise mining, LLM explanations, heavy ML,
Redis, external services and queues are unnecessary. Pearson was selected for
transparent paired monetary evidence; nonlinear effects, detrending, seasonality,
lagged relationships, forecasting and causal inference remain deferred.

Travel/discretionary and new-merchant/discretionary associations await an approved
discretionary definition. Concentration/volatility and merchant-specific outcome
mining are deferred to keep the hypothesis set small. Existing anomalies remain
their own advisory feature rather than being recounted as independent evidence.

Synthetic tests cover exact correlations/means, sensitivity, history thresholds,
all five calculations, gaps, currencies, fact deduplication, evolution eligibility,
authentication, finalization replay, category corrections and cross-user isolation.
Frontend tests cover cards, evidence exploration, insufficient/error states, Insights
integration and the navigation order. Verification results are in `docs/STATUS.md`.
No Phase 16 work, commits or pushes are part of this change.
