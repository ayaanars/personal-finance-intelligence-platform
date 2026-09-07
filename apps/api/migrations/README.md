# Migrations

Run Alembic from apps/api with LEDGERX_DATABASE_URL configured (or its local .env).
0001_foundation remains an empty baseline. 0002_identity_ownership creates users,
workspaces, their constraints, and the users.updated_at trigger/function. No seeds.
0003_authentication adds credentials, hash-only sessions, fixed-shape authentication
audit events and an audit append-only trigger/function. It creates no financial
tables. Downgrade to 0002 removes all credentials/sessions/auth audit data while
retaining users/workspaces, so use it only for disposable verification. Existing
foundation users without credentials cannot log in; this phase adds no credential
backfill or operator password-reset bypass.

Apply with `uv run alembic upgrade head`; check drift with `uv run alembic check`.
The API never runs migrations or metadata.create_all() at startup. Register future
models in ledgerx/db/models.py before generating a revision, and review generated
SQL. Trigger/function and check-expression changes require manual migration review;
Alembic check alone does not verify them.

On a disposable database verify upgrade head, downgrade base, upgrade head, check,
and heads. Downgrade deletes foundation records: do not use it on real data without
an approved backup/recovery plan; prefer roll-forward once populated.

Automated integration tests use LEDGERX_TEST_DATABASE_URL and unique schemas, running
real migrations and dropping only their own schema afterward. The test role requires
schema creation privileges. Never point the test URL at production. Alembic accepts
an explicit connection through Config.attributes for isolated migration tests.
