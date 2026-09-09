# Private intelligence experience: Phase 13

Implemented 2026-09-09. This is a presentation and navigation overhaul. ADR 0007
and ADR 0009 remain authoritative for financial definitions and evidence thresholds.
No backend, API schema, authentication protocol, migration or dependency changes.

## Information architecture

- Overview (/app): three financial-state values, prominent change hero, baseline,
  spending trend and recurring snapshots, plus two supported observations.
- Insights (/app/insights): existing personal baseline, deterministic explanations,
  their calculation evidence and full category/merchant driver exploration.
- Trends (/app/trends): one selectable chart for spending, income, outflow, signed
  net cash flow, category, merchant or recurring observations; 3/7-month windows;
  exact month inspection; existing metric/category baseline explorer.
- Recurring (/app/recurring): monthly/annual estimates, actual matched composition,
  ranked payments, observed cadence and three evidence records. Same/varying amount
  labels describe equality of observed decimal strings, not a new stability model.
- Behaviour (/app/behaviour): date patterns, purchase statistics, category/merchant
  concentration and momentum, largest purchases, new merchants, cash/transfer/returns.
- Transactions and Import retain their existing feature logic and API calls.

The private Next.js layout wraps all destinations in the existing Protected boundary,
then a period provider and Shell. Protected's principal key and unmount behavior
remain intact. Only month/currency selection is shared across private navigation;
financial responses remain component-local. Logout and session changes tear down
private content. No financial data or selections are persisted in browser storage.

## API reuse and charts

Every intelligence page uses GET /api/v1/analytics/intelligence with its existing
optional month parameter, runtime Zod validation and authenticated no-store transport.
No new endpoint. Deep Trends selections lazily read at most six earlier month
responses alongside the selected month's response. These are presentation reads,
not a new intelligence engine. The whole set must resolve before a historical chart
is shown; a failed read displays a retry state rather than partial financial history.
Unmounted/obsolete results are ignored. Separate monthly reads are not a database-wide
snapshot; concurrent edits may change observations between responses.

Categories use returned monthly category totals. Merchant history is explicitly
limited to each month's top five spending merchants, because that is what Phase 12
exposes. Missing categories/merchants are gaps, not zeros. Recurring history plots only
supported monthly estimates; insufficient evidence is not a zero commitment.
No new trend-direction, volatility, unusual-weekend, or commitment-change claim is
inferred. Insights prioritize the available personal baseline, subject-specific
server explanations, then aggregate explanations; this is editorial order, not a
new materiality threshold or risk score.

SVG chart geometry uses BigInt decimal units and converts only bounded pixel ratios
to number. No authoritative money is calculated using floating point. The signed
zero reference and explicit calendar gaps are preserved. Every observation has an
accessible button with an exact formatted value; focus, hover and click select a
month. Chart graphics do not replace textual evidence. Baseline bands reuse server
coordinates and all financial totals/estimates remain server-provided.

## Visual system and accessibility

Original LedgerX forest palette with layered green surfaces, mint financial ink,
warm hatched decreases, tabular numeric figures and strong typography. Public/auth
pages retain their established appearance. Private CSS tokens are scoped to Shell.
The desktop rail becomes an expandable navigation grid below 1024px. Dense layouts
stack below 768px; transaction tables retain horizontal scrolling inside their region.

Overview intentionally contains summaries and exploration links; evidence and broad
lists live in dedicated destinations. Details are collapsed by default, with larger
lists expandable. Brief entry transitions and hover/focus feedback express state
changes. Reduced-motion preference disables animations and transitions. No animation
interpolates financial values. No new chart, icon, motion or component dependency.

## Deliberate limits

No anomaly detection, Phase 14 work, ML/LLM, forecasting, bank integrations, scores,
new recurring frequencies, essential/discretionary taxonomy, or FX. Source coverage
can be partial or overlapping; this experience makes no complete-history claim.
