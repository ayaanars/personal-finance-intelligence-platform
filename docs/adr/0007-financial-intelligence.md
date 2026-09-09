# ADR 0007: Financial intelligence V1

Status: Accepted for Phase 11, 2026-09-08. The user confirmed the financial
definitions below during implementation.

## Context and decision

Overview interprets finalized imported activity, never account balances. Positive
amounts are inflows; negative amounts contribute their absolute value to outflow.
Net cash flow is all inflows minus all outflows. Income is only positive activity
whose effective category is Income. Other inflows (including refunds and
reimbursements) remain separate; they do not reduce gross spending.

Spending includes negative activity except Transfers and Cash / ATM, shown
separately. Negative Income-category activity is retained in Other spending so
outflow remains fully explained. Other is explicitly unclassified spending, not
proof of consumption. Categories are interpretation, not reconciled accounting.
Effective manual categories win; legacy facts use the existing understanding rules.
Top merchants rank all outflow (including transfers/cash), with null merchants
grouped as Unknown merchant. Each imported fact contributes once, including
legitimate repeated rows. Independently uploaded overlaps remain possible (ADR 0004).

Currencies never combine or convert. Money remains exact four-place strings;
Decimal arithmetic uses a local precision of 60. Only presentation percentages
are quantized, half-even to two places. A zero previous denominator yields null.
Net cash-flow percentages are omitted because negative baselines are misleading.

One GET /api/v1/analytics/overview accepts optional month YYYY-MM. Omission selects
the latest imported month. A six-calendar-month window ends at that selection;
only actual months per currency appear in trends. The picker lists at most the
120 most recent imported months; an explicit month can access older history.
Comparison requires activity in both selected and immediately previous months
for that currency. Missing activity is not evidence of a zero month. Observed
first/last transaction dates do not establish statement completeness. UI and API
disclose that comparisons reflect imported activity and may cover partial months.

Deterministic explanations compare outflow and net cash flow, and rank category
spending deltas and merchant outflow deltas. A category/merchant is called a
majority driver only if its same-direction change represents over half, but no
more than all, of the matching total change. Otherwise describe the delta without
causal language. Category evidence uses spending; merchant evidence uses outflow.
No arbitrary materiality threshold or automated financial action is introduced.

## Architecture and alternatives

Use the existing authenticated transaction and owner/workspace predicates.
PostgreSQL groups persisted enrichment by period/currency/effective category/
merchant/sign; legacy facts are streamed through existing deterministic rules.
No per-transaction queries, storage, caches, queues, new dependencies or migration.
Existing owner indexes and statement timeout remain. Authentication's owner lock
serializes supported imports/corrections during the read. Results reflect current
categories, not historical classification snapshots.

Separate endpoints would permit inconsistent dashboard snapshots and more requests.
Netting refunds would require allocation semantics not approved here. A baseline,
forecast, recurring engine, budget, risk score, ML or LLM is outside this phase.

## Consequences

Incomplete/overlapping imports and incorrect categories can affect interpretation;
the interface states these limitations and links to transaction review. No claim of
financial health, causality outside arithmetic, or production readiness is made.
Pure invariant tests, PostgreSQL ownership/legacy/API tests and UI state tests cover
this boundary. Existing authentication, import and transaction tests remain required.
