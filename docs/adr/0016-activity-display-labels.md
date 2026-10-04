# ADR 0016: Activity display labels without inferred merchant identity

Status: Accepted for Phase 20 presentation polish

## Context

An imported fact can identify an activity (RENT PAYMENT) without identifying its
merchant or landlord. Persisted enrichment may also predate the existing merchant
catalog. Rendering every null merchant as Unknown merchant obscures that context.
Using a generic activity name as merchant identity would change recurrence and
risk decisions and incorrectly imply a known counterparty.

## Decision

Add a pure `activity_label` presentation function, preserving an existing merchant
first, then using the existing conservative catalog/explicit POS-label resolver.
A small exact-description vocabulary labels rent, housing and specific bill payments.
Explicit, unambiguous financial-counterparty phrases have readable labels. Unmatched
or conflicting descriptions remain unknown. No landlord identity is inferred.

Transaction responses add nullable `display_name`; clients retain the existing
merchant/description fallback for older responses. Merchant fields, codes, preferences,
categories, source descriptions and monetary facts remain unchanged. Read operations
never persist this presentation fallback.

Date-level analytics carry a separate optional entity label. Composition, change
prose and largest-purchase displays may group by that label. Newly observed merchants,
recurring qualification, unusual-rule evaluation, ML and relationship calculations
continue to use actual merchant identity. Unusual-activity subjects may display the
label without changing evidence or severity. Current private intelligence endpoints
use this projection; the legacy aggregate overview endpoint remains unchanged.

## Alternatives

- Store Rent as a merchant: rejected because an activity is not a counterparty.
- Guess names from arbitrary descriptions: rejected because precision matters.
- Replace all unknowns with their category: rejected because that erases uncertainty.
- Introduce a persistent entity model: deferred beyond this presentation phase.

## Consequences

Existing imports gain readable labels without reprocessing or a data migration.
Merchant-oriented composition can include activity labels; explanatory copy makes
this distinction explicit. Labels do not enable merchant preferences or establish
recurring obligations. Existing explicit refresh remains the way to update persisted
merchant enrichment. Regression tests protect unknowns and separate rent display
from recurrence/new-merchant inference. No financial or risk thresholds change.
