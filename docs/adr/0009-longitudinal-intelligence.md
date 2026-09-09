# ADR 0009: Longitudinal financial intelligence

Status: Implemented for Phase 12, 2026-09-09. The baseline and recurring policy
was presented for confirmation; the user instructed work to resume, and the
implementation continues with that proposed policy. Financial definitions in
ADR 0007 remain unchanged.

## Context

Phase 11 provides correct monthly summaries but loses individual dates and amounts
in its aggregation. Phase 12 requests richer longitudinal context without ML,
external financial services, new infrastructure, or changes to accounting semantics.
ADR 0007's money, currency, ownership, exclusions, and gross-spending rules remain.

## Implemented decision

GET /api/v1/analytics/intelligence?month=YYYY-MM returns one coherent response under
the authenticated owner lock. It uses the same completed-import user/workspace
predicates as transaction reads. A streaming outer join loads facts and enrichment
for the selected month and six preceding calendar months. The month picker remains
bounded to 120 actual months. Legacy facts use existing understanding rules without
writes; persisted manual categories win. Each currency is processed separately.
The previous /overview endpoint keeps its six-month window and calculation semantics.

Descriptive dimensions answer the following questions:

- How large and frequent were purchases? Gross spending divided by purchase count,
  plus purchase count and distinct observed spending dates. No invented daily rate.
- When did spending occur? Totals/counts/shares for Monday-Friday vs Saturday-Sunday,
  and days 1-10, 11-20, 21-month-end. This explicitly defines the displayed weekend,
  not the user's work schedule. Unequal durations and partial coverage are disclosed.
- How concentrated was spending? Top-five category and merchant shares. Unknown
  merchants form one visibly unknown group. These are overlapping views, never added.
- Which purchases were largest? Five spending facts ranked by magnitude, date, UUID,
  with authorized transaction detail links. Transfers and Cash / ATM are excluded.
- Which merchants changed? Spending deltas against the immediately previous month,
  sorted by absolute delta then name. Up to ten; zero denominators yield null.
- Which merchants newly appeared in the window? Known merchants present this month
  but absent from earlier imported activity in this currency/window. At least one
  prior observation is required. Never claim a first-ever purchase.
- What moved outside purchases? Existing cash/transfer outflow plus transfer inflow
  by effective category and positive existing `return_*` rule matches. Return
  evidence includes refunds, reimbursements, cashback, and reversals. It is an
  overlapping descriptive signal, not proof of settlement or a new category override.

Exact totals retain four decimal places. Derived average purchase values are
quantized only for response presentation to four places using Decimal half-even;
ratios/scales use two-place half-even. Local precision is 60. No float money.
Chart widths use server percentages; frontend formats monetary strings only.

Category change scales use absolute delta divided by maximum absolute category
delta. Income/outflow/spending trend scales use each metric's window maximum.
Zero maxima produce zero scales. Direction remains visible in signed text and
hatched decreasing bars; color is not the sole indicator.

## Personal baseline policy

Require at least three consecutive prior calendar months with activity in the
same currency, using up to six. Exclude the selected month. Display arithmetic
mean and observed min-max range, explicitly not a confidence interval or proof of
complete coverage. Missing months break the qualifying run; insufficient history
produces no invented normal values. Three- and six-month averages require the
corresponding history. Compare only imported activity, never financial health.

Metrics cover spending, outflow and income. Categories require purchases in at
least three reference months, preventing a newly seen category from receiving
an invented zero baseline. An absent category in an otherwise observed reference
month contributes zero imported spending, with an explicit completeness caveat.
No selected-month activity returns no_activity and no current comparison.
Means are quantized half-even to four decimal places at their boundary; deltas
and relative percentages reconcile to that published mean. A zero mean yields
null relative percentage. Above/within/below labels compare the exact current
total to the exact observed endpoints. Equal endpoints remain a valid flat range.
Server-computed chart geometry uses a zero origin and 10% headroom over the larger
of current and historical maximum; visual coordinates never enter money logic.

## Recurring policy

Known merchant, exactly one eligible charge in each of three consecutive months,
21-40-day gaps, every amount within 5% of the median. Exclude Transfers and Cash /
ATM. Show evidence dates/amounts and label likely monthly recurrence, never a
confirmed subscription. Monthly typical amounts sum by currency; annualization
assumes twelve unchanged payments. Ambiguous and weak evidence stays insufficient.
No automated action, prediction of a contractual obligation, or generic score.

The rolling three-month evidence window ends in the selected month, including
that month's charge. Unknown merchants and existing return-rule signals are
ineligible. Missing selected activity is no_activity. Three observed currency
months without a qualifying merchant is insufficient_evidence; fewer observed
months is insufficient_history. Candidate examples (at most five, alphabetical)
explain missing months, multiple charges, timing or amount variation. All matching
patterns contribute to totals and sort by median amount descending, then name.

Newly qualified is true only when an additional prior currency month exists and
the prior rolling merchant window did not qualify; otherwise it is false for
continuing matches or null for insufficient earlier context. It never means a
newly purchased subscription. Groceries or other regular purchases can qualify;
these are patterns, not proof of fixed obligations. Multiple services charged by
one merchant remain unresolved rather than guessed apart.

Composition uses actual selected-month charges matched to these patterns and
the residual gross spending, which sum exactly to gross spending. It does not
use the estimated median as an actual charge or label the residual as variable.
Every displayed evidence item links to an independently authorized transaction.

## Alternatives and consequences

Monthly-only SQL aggregates cannot support exact date/amount recurrence evidence.
One additional synchronous read model avoids separate inconsistent UI requests.
No new dependency, migration, durable derived table, queue, Redis, or external data.
This bounded history query streams DB results but retains observations for pure
calculations; memory scales with the user's seven-month fact count. This is not a
new performance SLA. Existing DB timeouts remain. A future measured scale limit
must fail explicitly rather than return silently truncated financial totals.

Overlapping uploads, incomplete periods, unknown merchants, and current category
corrections limit interpretation. Salary and essential/discretionary taxonomies,
weekly/annual recurring frequencies, risk scores, forecasting, and FX are deferred.
No recurring promise or guaranteed financial normality is implied.

## Design review

Preserve Geist, emerald #126346, neutral canvas, 8px controls and 12px grouped
surfaces. Existing routes, primary navigation, wordmark, and session teardown stay.
Apply the user-requested GPT Taste skill's applicable redesign rules to this dense
product UI, acknowledging its dashboard exclusion. Dials: variance 4, motion 2,
density 7. Ranked bars, before/after values, category share bars, selectable trend
metrics and date patterns, baseline comparison bands, recurring evidence disclosures,
section navigation and purchase detail controls replace prose-only emphasis.
No decorative images/animation or extra component library. Existing light theme
is preserved; a broader theme redesign is outside this phase.
