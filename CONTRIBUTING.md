# Contributing

Read `AGENTS.md`, `docs/ARCHITECTURE.md`, and relevant design documents before edits.
The implemented scope is the development foundation, backend authentication and
canonical CSV imports, transaction understanding and the Phase 10 public/product
frontend and Phase 11 financial intelligence Overview. Other financial features
require separate authorization. Analytics semantics are recorded in ADR 0007.
Phase 12 longitudinal intelligence, baselines and recurring patterns are implemented
under ADR 0009. Preserve its evidence thresholds and currency-separated semantics.

Use the installation and check commands in README.md. Commit dependency manifests
and lockfiles together. Use `uv add --bounds exact` (or `--dev --bounds exact`) and
`npm install --save-exact` when intentionally updating dependencies, then rerun checks.
Format Python with `uv run ruff format .` from `apps/api`.

Tests must use synthetic data. Do not commit `.env`, virtual environments, caches,
build outputs, raw statements, or secrets. PostgreSQL integration tests must use
a dedicated database, never SQLite. Every bug fix needs a focused regression test.

Before business features, record their required ADRs and implement their authorization,
accounting, concurrency, error, and test requirements together. No placeholder security
or financial behavior is acceptable. Update `docs/STATUS.md` with actual check evidence.
