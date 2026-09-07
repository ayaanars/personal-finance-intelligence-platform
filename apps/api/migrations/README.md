# Migrations

Run Alembic from `apps/api` with `LEDGERX_DATABASE_URL` configured (or its local `.env`).
`0001_foundation` is an intentionally empty, reversible baseline. Alembic creates only
its own version table. There are no product models, tables, or seed records.

Apply explicitly with `uv run alembic upgrade head`. The API never runs migrations
or `metadata.create_all()` at startup. Check drift with `uv run alembic check`.
Create future revisions with `uv run alembic revision --autogenerate -m "description"`,
then review constraints and upgrade/downgrade behavior before applying.

On a disposable development database, verify `upgrade head`, `downgrade base`, then
`upgrade head`. Never run downgrade checks against real data. Production credential
separation and migration/backup procedures must be established before deployment.
