# ADR 0004: Canonical CSV statement import

Status: Accepted for Phase 8, 2026-09-07. The user explicitly approved currencies,
NUMERIC(20,4)/Decimal without rounding, 24-hour staging expiry and whole-import validation.

## Context

The Phase 8 request authorizes authenticated CSV upload, normalized preview and
explicit atomic finalization in the user's private workspace. It excludes bank
connections, financial-account UI, ledger posting and downstream financial features.
Before this phase, financial schemas were proposals and no financial tables existed.

## Decision

- Canonical columns: transaction_date, description, amount, currency. Require each
  once, permit reordered headers, reject additional columns. UTF-8 with optional
  BOM; comma-separated RFC-style quoting. Record numbers include the header as 1.
- Preserve raw description as a bounded fact. Positive amounts are inflows and
  negative amounts are outflows, as explicitly requested. No conversion or balances.
- Approved policy: AED/USD/EUR/GBP initially, NUMERIC(20,4)
  with Decimal parsing and rejection of excess precision, no rounding. Normalized
  previews expire after 24 hours; any rejected row prevents whole-import finalization.
- Use named/versioned adapters behind a common candidate interface and a separate
  canonical normalization boundary. No named bank compatibility is claimed.
- Transport: raw text/csv request body with a restricted X-Filename header.
  This replaces the earlier multipart proposal for this phase, permits enforcing
  byte bounds during streaming and requires no multipart dependency or disk spool.
  Only the upload dependency permits CSV; existing JSON mutations stay unchanged.
  Authentication, origin checks and session-bound CSRF remain mandatory.
- Bounds from the security baseline: 5 MiB, 25,000 records, 4,096 bytes per field,
  15-second upload and parser budgets. Four canonical columns only. Raw bytes live
  only in request memory; filenames are checked and discarded, never used as paths.
- Finalization uses owner-scoped import locking, unique import/source-record
  constraints and one database transaction. Identical rows remain separate facts.
  The explicit retry and cross-upload behavior is recorded below.

## Alternatives and consequences

Multipart remains possible later but adds parsing/spooling machinery. Automatic
bank detection is excluded without verified formats. Imported facts must not become
ledger entries, account balances, categories or analytics in this phase.

Dates use exactly YYYY-MM-DD. Amounts use an optional sign, 1–16 integer digits and
an optional decimal point followed by 1–4 digits. Zero is rejected, following the
existing imported-transaction design. No grouping, exponent notation, whitespace,
NaN or infinity. Even excess trailing fractional zeros are rejected; no quantization
or rounding changes input. Output pads to four decimal places. Currency-specific
settlement rounding is outside scope. Descriptions preserve up to 500 characters;
blank descriptions are invalid. Invalid records retain only record numbers and
fixed field/error codes, not their source values. Any invalid record prevents finalize.

Import batches belong directly to private workspaces: no fictitious institution or
financial account is created. Provenance retains parser/version, file SHA-256,
record number and normalized-record fingerprint. No account compatibility is claimed.
Upload and finalize require UUID Idempotency-Key headers scoped independently to the
owner and operation. Upload retries return the same batch for matching file/parser;
key reuse with different content conflicts. The batch identifier and source-record
uniqueness additionally prevent multiple finalizations even with different keys.
Finalization with a different key after completion conflicts; same-key retries return
the persisted result. No content-based row deduplication is performed across new
uploads: different keys create independent batches, and overlapping files can duplicate
facts. Clients must retain upload keys for retries. Fingerprints support later reviewed
duplicate detection; repeated legitimate rows are preserved now.

Staged imports become logically expired at the exact 24-hour boundary even before
cleanup runs. Expired data is never returned or finalized. Finalization deletes staging
immediately after copying facts in the same transaction. A bounded operational cleanup
command removes expired normalized rows and marks batches expired; run at least hourly.
Expiry is an access deadline; physical deletion can lag until the command runs. No raw
CSV is written to disk. Minimal batch metadata and append-only import audit remain;
broader account erasure and backup retention require a later approved runbook.

## Persistence and verification

Alembic 0004_csv_import adds statement_imports, import_rows, imported_transactions
and import_audit_events. Batch-to-workspace and child-to-batch foreign keys include
owner identity. Imported facts inherit workspace and parser provenance through their
immutable completed batch. No financial account or ledger tables are introduced.
Finalization retains the authentication dependency's user/session locks, locks the
batch, verifies the entire staged row count and absence of errors, inserts facts,
sets completion/key metadata, removes staging and appends audit before commit.

Database triggers enforce valid state transitions, complete finalization counts,
fact insertion only during ready-to-completed processing, and append-only facts and
audit. Ordinary runtime code cannot reopen a completed batch. PostgreSQL administrators
can disable triggers; least-privilege runtime roles remain a deployment gate.
NUMERIC's direct-SQL typmod coercion is not input validation: the application boundary
rejects excess scale before insertion. The API never accepts raw SQL financial values.

Synthetic PostgreSQL tests cover owner isolation, CSRF/origin enforcement, exact-money
extremes, invalid/expired imports, atomic rollback, concurrency, retry keys, 25,000-row
capacity, cleanup locking and constraints. Migration tests include downgrade and
re-upgrade with trigger-function cleanup and schema drift checks. Downgrade destroys
these import tables and is only for disposable data; otherwise back up and roll forward.
