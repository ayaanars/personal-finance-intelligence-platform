# ADR 0005: Deterministic transaction understanding

Status: Accepted for the explicitly authorized Phase 9 scope, 2026-09-07.

## Context

Finalized CSV facts are immutable under ADR 0004. Transaction understanding must
provide explainable metadata for future personal financial intelligence while
preserving facts, privacy, and authoritative transaction-level user corrections.
No accounting, retention, authentication, or risk policy is changed here.

## Decision

Use a pure deterministic Python rules module and separate PostgreSQL enrichment.
The 15 stable category values are Income, Groceries, Food & Dining, Transport,
Shopping, Entertainment, Housing, Bills & Utilities, Health, Education, Travel,
Transfers, Cash / ATM, Banking Fees, and Other. These are descriptive labels, not
proof of income, spending, a reconciled transfer, or ledger movements. Categories
are code-defined with database checks; changing the taxonomy requires a migration.
Adding merchant aliases or keyword rules does not require a schema change.

Normalization (`description-v1`) uppercases text, collapses whitespace, and reduces
repeated identical formatting separators (`| * _ . ! ; : / -`) to one. Only trailing
numeric references explicitly labeled REF, REFERENCE or TXN ID with at least six
digits are removed, repeatedly to a fixed point. Bare numbers, location/store
numbers, dates, decimals and short/alphanumeric references remain. There is no
claim of universal bank-description parsing or sensitive-identifier redaction.
Raw description is preserved byte-for-character as already accepted by the importer.
Normalized text is private financial data and must never enter logs or telemetry.

Merchant rules are immutable data definitions with alias groups and explicit
specialization (Uber Eats specializes Uber). Word boundaries prevent substring
matches such as DU in DUBAI. Multiple unrelated merchant matches yield null.
Careem needs ride/taxi context, ADNOC needs fuel/station context, Emirates and Etihad
need airline context. Unknown merchants remain null; no external resolution occurs.

Automatic precedence is explicit:

1. Return/refund/reversal/reimbursement/cashback evidence: known merchant category,
   otherwise Other. Never infer income or a new transfer from these descriptions.
2. Recognized movement rules: transfers/card repayments in either direction;
   ATM withdrawals and bank fees only on outflows.
3. Known merchant category, ahead of generic description keywords.
4. Explicit income descriptions on inflows only (salary, payroll, freelance payment,
   interest credit, dividends, income credit).
5. Broad everyday keyword groups on outflows only.
6. Other when unmatched. Conflicting categories within a tier also produce Other.

Within a tier, stable rule codes break same-category ties; declaration/dictionary
iteration order has no semantic effect. An explicit manual category always wins
at presentation, independently of the automatic precedence above.

Coverage includes supermarkets, dining/delivery/cafes, fuel/transport/tolls/parking/
vehicle repair, shopping/e-commerce/clothing/electronics/home goods, entertainment/
streaming/gaming, housing, utilities/telecom, health/fitness, education and travel.
Software subscriptions and explicit insurance premiums use the broad Bills &
Utilities category. Government fees, charity, professional/business expenses and
miscellaneous purchases have explainable Other rules. Ambiguous inflows stay Other.
This is broad rule coverage, not a promise to recognize every wording or merchant.

Store source (`merchant_rule`, `description_rule`, `fallback`), fixed safe reason,
rule ID, rule-set version (`understanding-v1`), normalization version and update
instant. Do not fabricate confidence percentages; confidence is omitted entirely.
Reprocessing replaces only the current automatic result. Old rule executables and
all historical automatic outputs are not archived by this phase.

## Transactions, API and concurrency

Finalization inserts enrichment in bounded batches after copying facts and before
completion commits. Failure rolls back facts, enrichment, staging deletion, completion
metadata and import audit together. Original finalization idempotency remains intact.
No workers or queues. The expiry check still occurs after enrichment processing.

GET list/detail is owner/workspace-scoped and only includes completed imports.
Collections follow the documented opaque cursor envelope, limit 50/default and
100/maximum, with immutable UUID ascending order and owner-bound cursors. This
ordering is not chronological and pagination is not a cross-request snapshot;
new concurrent imports with earlier UUIDs require a fresh traversal. Cursor contents
are validated, never trusted as authorization and contain no financial descriptions.

PATCH category accepts a taxonomy value or null to clear the correction. It requires
JSON, authenticated CSRF/origin checks, and a quoted integer If-Match equal to the
returned version (409 on stale version, including retries after an applied change).
Clients refetch after an uncertain response. This explicit conflict strategy prevents
retry overwrites without a second mutation-key store. Unchanged assignments are
no-ops. Unknown payload fields and invalid categories are rejected.

POST per-transaction reprocess accepts JSON {} and existing authentication/CSRF.
It is an idempotent recomputation for the deployed rule version. Unchanged output
leaves timestamps/version/audit unchanged. A changed automatic result increments
version and preserves manual_category and manual_updated_at. Authentication's
existing user-then-session locks serialize corrections and reprocessing; If-Match
prevents stale editors from silently replacing intervening changes.

Safe append-only audit records correction/reprocess changes with owner, transaction,
event, correlation and timestamp only. No arbitrary notes, raw descriptions or
financial values. Initial enrichment is covered by the atomic import-finalized audit.
Database composite ownership FKs prohibit cross-user links. No auth weakening.

## Migration and existing data

0005_understanding adds transaction_enrichments (one row per fact),
transaction_audit_events and a unique (user_id, id) fact key supporting owner FKs
and cursor lookup. Automatic and manual fields share a record but are independently
updated; facts are neither duplicated nor rewritten. Timestamps are TIMESTAMPTZ.
Category/source/version/manual-shape checks and append-only audit trigger apply.

No migration-time financial-data backfill. Existing Phase 8 facts remain visible:
GET computes current automatic metadata without writing, returns version 0 and
`enrichment_persisted: false`. Explicit reprocess or correction persists enrichment
and returns version 1. This avoids hiding legacy facts or blocking deployment on a
large backfill. Clients must not treat transient results as a historical snapshot.
Future bulk reprocessing can reuse the owner-scoped application boundary.

Upgrade is additive. Downgrade destroys enrichment, corrections and their audit;
use only on disposable databases. Facts and import provenance remain intact.
For populated deployments back up and roll forward; a migration operator can bypass
triggers, so existing least-privilege/public-launch limitations still apply.

## Alternatives and consequences

Embedding metadata in immutable facts would conflict with reprocessing and is
rejected. Separate override tables would add joins without improving the current
single-correction boundary. Read-time-only enrichment would lack persisted rule
lineage for new imports. Queues, merchant learning, ML/LLMs and external merchant
services add complexity/privacy decisions beyond this phase.

Explicit rules can miss synonyms and misclassify context. Null merchants, Other,
fixed explanations and authoritative corrections make these limitations visible.
No analytics, balance calculations, budgets, recurring detection, personal learning,
financial-health analysis, risk scores or frontend product screens are implemented.
