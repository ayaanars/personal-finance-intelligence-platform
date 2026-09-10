# ADR 0012: Deterministic merchant intelligence and private category preferences

Status: Accepted for the explicitly authorized Phase 16 implementation.

## Context

Phase 15 stores immutable imported facts separately from versioned enrichment and
manual categories. Analytics already consume the effective enrichment category.
The small merchant catalog leaves recognizable UAE transactions unidentified, and
individual corrections cannot inform later imports.

## Decision

Extend the structured MerchantRule catalog with stable codes, canonical display
names, aliases and default categories. Identify merchants independently of category
inference. Normalize Unicode compatibility forms, case, whitespace and reference
suffixes for derived descriptions; match alias punctuation as word separators.
Word boundaries prevent substring matches. Explicit exclusions prevent Emirates
NBD/Islamic/Post/Coop and Etihad Credit/Rail from being mistaken for airlines.
Conflicting merchant matches remain unidentified; specialization retains Uber Eats.
A conservative explicitly labeled POS/card purchase name can be displayed without
claiming catalog confidence or making it eligible for reusable preferences.

Category precedence is:

1. Direct transaction correction (persisted separately).
2. Saved user/workspace preference for a confidently matched catalog merchant.
3. Explicit product-line override: Amazon/AMZN Fresh and Noon Minutes/Grocery are
   Groceries; Careem Food is Food & Dining.
4. Existing explicit movement rules (transfer, withdrawal and bank fee) take
   priority over merchant defaults. Returns retain their existing movement guard.
5. Known merchant default, across exact names and aliases in the same catalog.
6. Direction-aware income and category keyword rules.
7. Other for insufficient/conflicting evidence or activity outside the taxonomy.

Exact names and aliases do not need separate category tiers: they resolve to the
same canonical merchant. Weak keywords cannot override a known merchant. Known
merchants can still be Other if explicitly selected by the user or if stronger
conflicting movement evidence warrants it. Return rule identifiers retain their
return_ marker even when preferences or product rules apply, preserving analytics'
refund interpretation. No money, ledger, currency or immutable import semantics change.

Learning is explicit opt-in in the existing category form: keep the existing
preference (default), remember the selected category, or remove the preference.
PATCH category accepts merchant_preference = keep|save|forget. Save requires a
non-null category and a catalog match derived server-side from the original fact.
Clients cannot choose an owner, workspace or merchant key. Clearing a transaction's
manual category and forgetting a preference are independent actions; both may be
requested together. A different individual correction never silently changes the
saved preference. User decisions may deliberately choose any existing category.

The merchant_preferences primary key is (user_id, workspace_id, merchant_code),
with a composite foreign key to the workspace owner and a category constraint.
The existing authenticated owner lock serializes supported mutations. The existing
transaction If-Match version rejects stale corrections. Explicit saves from other
transactions update the same merchant preference in owner-lock order. Preference,
correction, enrichment refresh, version and append-only transaction audit commit
atomically. Repeating the same resulting state makes no additional audit/version
change; there are no new imported facts or balance writes.

Imports load preferences once per batch. Reprocessing loads current preferences,
refreshes only derived enrichment, and leaves direct corrections intact. GETs do
not persist changes. Legacy facts without enrichment use current rules/preferences
on reads, including both shared analytics loaders. Already persisted historical
metadata changes only through explicit reprocessing, including the focused detail
page refresh control. Removing/updating a preference affects future imports and
explicitly reprocessed records, not every historical transaction immediately.

Enrichment additionally stores merchant_code and merchant_source; existing rows
have null provenance until refreshed. Category source user_preference and reason
identify learned results. Raw/normalized descriptions, canonical merchant, rule
and normalization versions remain available. The normal UI exposes actionable
preference controls and human-readable explanations rather than rule identifiers.

## Migration and operation

0006_merchant_preferences is additive apart from broadening the source constraint.
Apply it before loading the new API. No automatic historical backfill or facts
rewrite runs. Downgrade refuses while saved preferences or enrichment with a
user_preference source exists: remove preferences and reprocess their records
first, or restore a compatible backup. Prefer a forward fix; do not discard user
choices to roll back. Empty-data upgrade/downgrade cycles and populated-fact
preservation are covered against PostgreSQL.

## Alternatives

Global learning would violate isolation. Implicit learning on every edit would
turn one-off exceptions into persistent policy. Free-form merchant learning and
fuzzy matching would spread uncertain identities. LLMs and external merchant
services are outside the authorized deterministic scope.

## Consequences and limits

All seven intelligence views inherit improved source enrichment through existing
shared analytics, without duplicate calculations. Historical groupings can change
after explicit reprocessing. Catalog coverage remains maintained and bounded;
there is no measured claim of real-world recognition accuracy. Ambiguous POS
references remain unknown/Other. No custom taxonomy, merchant-editing workflow,
fuzzy identity model, bulk background reprocessing, ML/LLM integration, external
API, dependency, queue, or Phase 17 work is introduced.
