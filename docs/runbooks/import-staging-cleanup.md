# Expired import staging cleanup

Scope: Phase 8 normalized staging only. Raw CSV files never reach disk.

Access to unfinalized staging expires exactly 24 hours after creation. The API hides
expired row contents and rejects finalization even if cleanup has not run. Finalize
deletes staging in its own atomic transaction. Physical deletion of abandoned/invalid
staging needs this operator command; expiry is not a promise of immediate physical
erasure from PostgreSQL pages or backups.

From apps/api with the intended database configuration:

```powershell
uv run python -m ledgerx.modules.imports.cleanup
```

For the existing development container:

```powershell
docker compose exec -T api python -m ledgerx.modules.imports.cleanup
```

Run at least hourly through the approved deployment scheduler. No scheduler,
Redis or queue is installed by Phase 8. Each invocation handles at most 100 expired
batches in one transaction and prints only the count. If the count is 100, repeat
until it is lower; a later scheduled pass handles any locked batches skipped during
active work. Monitor failures and the oldest unpurged expiry before public launch.

Cleanup locks batches using FOR UPDATE SKIP LOCKED, deletes only their owner-scoped
normalized rows, marks them expired and appends fixed audit metadata. It never
removes completed transaction facts, identities, other live staging or raw files.
Repeating/concurrently running the command is safe. A failure rolls back its batch;
fix the database/configuration issue and rerun. Finalize and cleanup serialize on
the same batch lock. This is a privileged operator path, not a public API endpoint.

Minimal batch counts/provenance and audit metadata remain for traceability and retry
results. Their broader deletion and backup retention await the approved account
erasure policy. Do not manually delete immutable imported facts or disable audit
triggers as a cleanup workaround. No production readiness is claimed.
