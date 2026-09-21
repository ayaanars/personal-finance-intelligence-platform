# ADR 0015: Automatic recognition and useful partial history

- Status: Accepted for Phase 19
- Date: 2026-09-21

## Context

Phase 18 made CSV layouts flexible but opened mapping controls for every upload.
Several intelligence pages emphasized missing history even though canonical
current-period facts were already available. Phase 19 authorizes deterministic
recognition and partial-history views, not a new ingestion or analytics system.

## Decision: recognition

Extend the existing transient inspect operation with a deterministic
recognition policy, named evidence, executable mapping when possible, and
recognized / needs_confirmation / needs_mapping states. No confidence percentages.

A unique compatible saved configuration is applied automatically. Profiles remain
owner/workspace scoped, match exact header-name sets (order independent), and are
not bank identification. Equivalent profiles are interchangeable; conflicting
configurations require explicit selection or reviewed custom mapping. All rows
are revalidated, even when a profile matches.

Otherwise, unique header aliases and value patterns identify columns. Debit/credit
aliases include withdrawal/deposit and money/paid in/out. A wholly blank side is
allowed as structural evidence; normalization still requires a populated other
side. Signed split values require mapping review and are never absolute-valued.
Single amounts preserve signs. Positive-only noncanonical amounts require the
user to confirm that positives are inflows; canonical headers retain their defined
signed contract. No outflow/inflow sign inversion is inferred from spending names.

Currency is supported ISO codes in a unique source column, explicit ISO code in
source headers when no column exists, or a reviewed profile's fixed currency.
Without that evidence the user chooses it. No location/default currency and no
conversion. A date format is selected only when exactly one supported format
fits every structurally valid row, or a saved profile explicitly defines it.
Ambiguous slash dates always require confirmation unless such a profile applies.
Multiple plausible field assignments require mapping; isolated date/currency/sign
questions expose only those controls. Review mapping remains available throughout.

Automatic recognition returns the existing normalized samples and whole-file
validation count without staging. Confirm import then calls existing stage and
finalize operations with stable retry keys. No finalization occurs merely from
uploading, recognizing, applying a profile or previewing. After staging succeeds,
bytes/mapping remain locked for uncertain finalize retries. Raw-file transience,
canonical schemas, Decimal, ownership, expiry and atomic finalization are unchanged.
No migration or dependency is needed beyond Phase 18's migration 0008.

## Decision: current-period first

Reuse intelligence totals, category/merchant breakdowns, behaviour observations,
and existing goal forecast calculations. No separate first-month math, invented
prior-month zeros, imputed comparisons or additional forecast policy. Existing
history states and counts drive compact developing notices. Relationships and
Unusual Activity also request the existing currency-selected intelligence view
for current-period facts; no shared persistent browser cache is introduced.

- Overview / Insights: show current facts and composition while comparisons develop.
- Trends: retain available observations and missing gaps; show current composition.
- Behaviour: current metrics remain available; default to largest purchases when
  adjacent-month momentum is unavailable.
- Relationships: current drivers/composition remain usable; relationships still
  require six usable observations and retain their existing screening rules.
- Recurring: expose bounded current charges, amounts and observed-month counts for
  existing candidates. Potential recurring is not established recurrence. Confirmed
  monthly pattern means the existing three-month timing/amount rule is met, never
  a confirmed contract. Candidates do not enter forecast commitments or annualize.
- Goals: existing actual progress and current-pace projections remain available,
  labeled limited-history when fewer than three usable prior months exist. Past
  months show observed outcomes, not fabricated future forecasts.
- Transactions and Import remain independent of history depth.

## Advisory current-month signal (unusual-v2)

When broad historical purchase rules lack their three prior months / 20 purchases,
allow one explained current-period peer signal. Require at least six eligible
purchases in the same currency/month. Flag a purchase only if it is at least four
times that month's median purchase AND at least 25% of eligible spending. The
median includes the purchase itself. Use exact Decimal arithmetic. This is always
Notable, with basis=current_month, never a historical anomaly, High severity,
fraud finding, probability, or model-supported observation. Cash, transfers and
return signals remain excluded. Sparse and uniform activity produces no signal.

Historical rules keep their thresholds and basis=historical; ML remains restricted
to prior observations. Unknown history is not risk evidence. This descriptive
threshold is a conservative product heuristic, not statistical significance;
partial or duplicate imports can distort it. Version the report as unusual-v2.

## Alternatives and consequences

Always showing a full mapping form was rejected as avoidable friction. Always
guessing was rejected because ambiguous dates/currencies/signs change financial
meaning. A separate first-month analytics engine was rejected to prevent drift.
Broad anomaly inference or subscription confirmation from one charge was rejected.

No new bank schemas, ML mapping, raw retention, currency conversion, reconciliation,
financial posting changes or historical threshold relaxation. XLSX, locale amount
parsing, account-type-dependent sign inversion and zero-filled split conventions
remain deferred. Import still requires human review; additional history improves
only the sections whose existing evidence requirements are met.
