# ADR 0014: Explicit, transient CSV mapping

- Status: Accepted for Phase 18
- Date: 2026-09-20

## Context

Canonical-only CSV uploads force users to transform bank exports outside LedgerX.
The existing bounded parser, canonical normalization, owner-scoped staging, expiry,
whole-import validation, and atomic/idempotent finalization remain authoritative.
Phase 18 explicitly authorizes flexible layouts without rebuilding ingestion.

## Decision

Add transient inspection to the existing import API. The browser holds the selected
File only in component memory and resends it for mapping preview and staging.
Inspection creates no database record. Source samples are returned with no-store
headers and never written to the database, filesystem, browser storage, or logs.
The first five records and up to five later invalid records are shown; displayed
source cells are truncated at 500 characters. Every row is validated, not just the
sample. Mapping edits invalidate the checked preview. A separate confirmation
stages canonical rows; existing explicit finalization remains unchanged.

Support UTF-8 comma-separated CSV (optional BOM), reordered/renamed columns and
extra ignored columns. Retain the 5 MiB/25,000-row/4,096-byte-field limits and parser
time checks; cap headers at 64 unique nonblank names of 120 characters. Duplicate
names after trimming and case folding are rejected. No bank identity is inferred.
XLSX is deferred: archive expansion, formulas, workbook ambiguity and numeric cell
handling require their own bounded and exact parsing design.

Header aliases plus basic value checks suggest columns only. Multiple date or
description aliases are not ranked into a silent choice. Date candidates are
checked against the whole file. The supported formats are YYYY-MM-DD, DD/MM/YYYY,
MM/DD/YYYY and DD-MM-YYYY, with exact digit widths and valid calendar dates.
An explicit date_format is required for every mapped request, even if a suggestion
is unique. Ambiguous slash dates leave the UI format unselected; the user may
confirm either interpretation. No location-based date or currency defaults exist.

Each mapped field uses a distinct existing column. Single amount mode preserves
signs. Split debit/credit mode accepts unsigned plain decimals with exactly one
populated cell, negating debit and keeping credit positive. Both populated cells
(including zero placeholders), signed split amounts, blanks in both cells, zero
transactions, separators and excess precision fail validation. We deliberately
require correction of these ambiguous source conventions rather than taking
absolute values or netting two populated columns. Mapping strips surrounding
whitespace before canonical validation. Decimal/NUMERIC(20,4) remain unchanged.

Currency comes from a selected source column OR an explicit fixed AED/USD/EUR/GBP
choice. No inference or conversion. All mapped rows enter the existing Candidate
and normalize boundary. Invalid normalized rows retain error codes only. Posting,
ledger, reconciliation, and enrichment semantics do not change.

Persist configuration (mapping and source headers) on mapped imports, never source
cell values or filenames. The original file SHA-256 remains a file digest; replay
comparison includes canonicalized mapping configuration, adapter version and hash.
Changes to either bytes or mapping under an existing upload key return conflict.
Owner locking, atomic finalization, 24-hour staging expiry and cleanup are reused.
Legacy canonical requests without a mapping header keep their original behavior.

Reusable named profiles are user AND workspace scoped with a composite ownership
foreign key and unique owner/workspace/name constraint. Only a ready/completed
owned mapped import can supply configuration. Up to 50 profiles per workspace;
retrying the same name/configuration is repeatable, different configuration under
that name conflicts. Exact header-name sets suggest compatible profiles even when
column order changes. Profiles must still be selected/reviewed. They never stage
or finalize automatically. Profile editing/deletion is deferred.

## Alternatives

- Store raw uploads pending mapping: rejected because transient resubmission avoids
  a new sensitive storage lifecycle and preserves the existing retention policy.
- Normalize in the browser: rejected because backend validation must remain
  authoritative and monetary processing must stay exact.
- Bank-specific parsers/ML: unnecessary for this bounded column-mapping phase.
- XLSX now: deferred to avoid unsafe ZIP/XML/formula or float shortcuts.

## Consequences and operations

Migration 0008 adds nullable configuration columns and import_mapping_profiles;
existing imports need no backfill. Upgrade before serving the updated API.
Downgrade refuses to discard saved profiles: export and deliberately remove them
first. It then removes only mapping metadata, preserving transactions/import facts.
Back up before downgrade; prefer roll-forward fixes. Downgrading an in-flight mapped
import loses its mapping replay metadata, so finish or expire mapped staging first.

Source data is transient but may be visible to the signed-in user in samples.
Headers and user-supplied profile names are retained configuration; users should
avoid putting account identifiers in them. Separate uploads still do not deduplicate
financial facts across statements; this existing limitation remains visible.
No new dependencies, job queues, bank schemas, or accounting representations.
