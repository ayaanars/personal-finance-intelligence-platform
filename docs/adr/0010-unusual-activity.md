# ADR 0010: Explainable unusual activity

Status: Implemented for the user-requested Phase 14, 9 September 2026.

## Context

Identify what is unusual relative to a person's own imported history. These are
advisory observations, never fraud findings, financial-health judgments or an
authorization to block or modify activity. Accounting and import semantics remain
those of ADRs 0007 and 0009. Thresholds below are conservative initial product
heuristics, not calibrated probabilities or validated fraud-detection thresholds.

## Decision

`GET /api/v1/analytics/unusual?month=YYYY-MM` uses the same authenticated owner
context and finalized-import query as Phase 12. The shared `load_history` reads
the selected month and six prior calendar months, preserving legacy enrichment
fallback and manual category precedence. Each currency is evaluated independently.
No new persistence, accounting writes, migrations, background work or caches.

The existing `baselines()` determines the consecutive reference-month run and
category mean/range. Missing months break that run; selected-month data never
trains a baseline. Transaction statistics are evidence over those same months,
not a second calendar-window or financial-baseline system. Imported coverage can
be partial or overlapping; neither the model nor the rules establish completeness.

### Rules, version unusual-v1

| Observation | Eligibility and threshold | High severity |
| --- | --- | --- |
| Large purchase | At least 20 reference purchases over 3+ consecutive prior months; current amount at least 3× reference median and greater than every reference purchase | At least 6× median |
| First observed merchant | Same 20-purchase/3-month gate; known merchant absent from all prior purchases in the seven-month window; only its first selected-month observation is surfaced | Never by novelty alone |
| Category spending | Existing Phase 12 category baseline is available; current total at least 1.5× mean and greater than historical maximum | At least 3× mean |
| Purchase frequency | 20-purchase/3-month gate; monthly purchase count at least 2× mean and above every reference month | At least 3× mean |
| Merchant spending | 20-purchase/3-month gate; merchant occurs in at least 3 reference months; current total at least 2× mean and above every reference month | At least 3× mean |
| Recurring amount | Existing recurring detector qualified the prior month; exactly one eligible selected-month charge with a 21–40-day gap; absolute change at least 20% of typical amount | Absolute change at least 100% |

Purchase rules exclude Transfers, Cash / ATM, nonnegative amounts and existing
return signals. Category rules retain Phase 12 gross-spending semantics. Recurring
comparisons can still work with fewer than 20 total purchases. A category needs
positive spending in three reference months, as before. Normal repeated activity
does not qualify merely because a model returns an outlier label.

Signals on the same transaction merge. Category, merchant and frequency findings
remain overlapping observations and must not be summed as unique incidents or
money lost. High items rank first, then evidence count, ML support, largest
current/reference ratio, and stable identifier. Other findings are Notable. The
response returns the first 100 ranked items, total count and up to five transaction
links per item; no input financial totals are truncated. The UI discloses the cap.
Money arithmetic uses local Decimal precision 60; existing `money` and `percent`
provide four/two decimal half-even response boundaries.

### Contained ML assistance, features/model unusual-v1

Isolation Forest is a modest multivariate support signal, selected because it
works without labels and has bounded training samples. scikit-learn 1.9.0 and
transitive dependencies are locked. The adapter creates a fresh model for one
owner/currency/request, with no shared fitted state, files, registry or training
service. It needs 100 eligible prior purchases and at least three consecutive
reference months; small histories return `insufficient_history` before importing
the library. No current purchases returns `no_activity`.

Features are amount/reference-median ratio, day-of-month/31, Saturday/Sunday flag
and purchase count on that calendar day. Only dimensionless ML features become
floats; money remains Decimal. Ratios and counts are capped at 1000. No location,
clock time, inferred employment schedule or cross-user features. Daily count uses
observed dates and is not a claim of complete bank coverage. Training retains the
latest 2,000 reference purchases in stable date/identifier order. The model uses
64 trees, `max_samples=min(256, training_count)`, `random_state=14`, one job, and
`contamination="auto"`; it does not force a configured share of purchases to be
flagged. Inference is selected-month only, outside the training period.

A model outlier may add `ml_supported` to a rule-backed item and break ranking
ties; it cannot create an unexplained item or change severity. Raw scores and
probability claims are absent from the API and UI. Import/OS/model failures return
`unavailable`; deterministic findings remain intact. See the
[Isolation Forest documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).

## Reproduction, evaluation and limitations

Versioned rules/features, locked library versions, fixed parameters, selected
month, owner/currency and reference months define the calculation. Source facts
remain authoritative; current enrichment/corrections are inputs. Findings are
ephemeral read-time views, not persisted risk decisions. Repeating a request with
unchanged source state reproduces the result; later imports/corrections can change
it. Historical snapshots across corrections, durable model decisions and drift
monitoring are deliberately deferred with all automated decision policy.

Synthetic tests cover rule boundaries, normal activity, insufficient/gapped
history, timing ambiguity, currency separation, deterministic fallback and model
activation/repeatability. PostgreSQL tests cover finalized-only visibility,
authenticated reads, cross-user object denial, independent model histories and
category-correction effects. These establish correctness, not real-world model
precision or recall. False positives from incomplete imports and legitimate new
merchants are expected; missed moderate deviations are the cost of conservative
thresholds. No sensitive subgroup is inferred or used. Before expanding model
influence, evaluate labelled synthetic scenario sets and consented user feedback,
track nuisance rates and missed meaningful changes, and review threshold stability
across history sizes and currencies. No claims of calibration or fraud accuracy.

## Alternatives and consequences

Rules alone remain the fallback and the explanatory authority. A standalone ML
feed would produce opaque alerts and was rejected. Separate baseline storage,
queues, Redis, external fraud services, LLMs and MLOps would add unnecessary scope.
The model adds scientific-computing dependencies and per-request CPU; training is
bounded, but the existing seven-month history load still scales with owned facts.
Production scale and rate limiting remain existing deployment gates.

The private UI adds only `/app/unusual`, a navigation item and a short Overview
summary. Evidence bars, Notable/High labels and transaction links preserve the
existing visual system. Native CSS entrance/bar/disclosure transitions honor
reduced motion. Shared calendar-date presentation formats months and dates in
English without timezone shifts. ISO dates stay in API/storage and in the CSV
format instructions where the exact input syntax matters. Phase 15 is not started.
