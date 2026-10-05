# Production deployment

Architecture: browser → Vercel Next.js `/api/v1` rewrite → Render FastAPI Docker
service → Render PostgreSQL 17. Use the stable `*.vercel.app` production hostname
and `*.onrender.com` API hostname. Browser requests never use the API hostname
directly. See [ADR 0016](../adr/0016-production-deployment-and-recovery.md).

## Accounts and services to create

1. A Vercel account and Next.js project, root directory **apps/web**. Use Node 22,
   the checked-in `vercel.json`, and a stable production project URL. Keep preview
   environments separate from production and do not give them production variables.
2. A Render account: create PostgreSQL 17 and one Docker web service in the same
   region (the blueprint uses Frankfurt). `render.yaml` defines these resources.
   Review the paid plan/billing selection before creating them. The API uses 2 GB
   to leave room for Argon2 and scikit-learn; no Redis or worker service is required.
3. For real password recovery, an SMTP service and a verified sender address
   supported by that service. No email provider is needed for the local reset-link
   command. Production recovery remains visibly unavailable until SMTP is configured.

No hosting accounts, projects, database or live URLs have been provisioned yet.
The repository has not been committed or pushed for deployment. Render's Git-based
blueprint flow requires a hosted repository; authorize the release commit/push
separately when ready. Vercel can also deploy through its CLI from a local checkout.

## Environment inventory

Set these in the provider's secret settings, never in Git or `NEXT_PUBLIC_*`.

| Setting | Production value / purpose |
| --- | --- |
| `LEDGERX_ENVIRONMENT` | `production`; requires HTTPS and explicit database TLS |
| `LEDGERX_DATABASE_URL` | Runtime role: `postgresql+psycopg://USER:ENCODED_PASSWORD@HOST/ledgerx?sslmode=require` |
| `LEDGERX_MIGRATION_DATABASE_URL` | Owner/migrator URL with the same TLS parameters; operator release environment only, never the API host |
| `LEDGERX_FIRST_PARTY_ORIGIN` | Exact `https://YOUR_PROJECT.vercel.app`, no trailing slash; CORS and CSRF allowlist |
| `LEDGERX_API_ORIGIN` | Vercel only: exact `https://YOUR_API.onrender.com`; required at build time |
| `LEDGERX_LOG_LEVEL` | `INFO` (also permits `WARNING` or `ERROR`) |
| `LEDGERX_DATABASE_POOL_SIZE` | `5` per worker |
| `LEDGERX_DATABASE_MAX_OVERFLOW` | `5` per worker; leave DB connections for migrations/admin |
| `LEDGERX_RESET_DELIVERY` | `disabled` or `smtp` |
| `LEDGERX_SMTP_HOST`, `LEDGERX_SMTP_PORT` | Provider hostname and STARTTLS port, normally `587` |
| `LEDGERX_SMTP_USERNAME`, `LEDGERX_SMTP_PASSWORD` | Provider credentials |
| `LEDGERX_RESET_FROM_EMAIL` | Verified sender address |

`DATABASE_URL` alone is not consumed: LedgerX consistently uses the prefixed
`LEDGERX_DATABASE_URL`. Convert a provider's `postgres://`/`postgresql://` scheme
to `postgresql+psycopg://`, preserving URL-encoded credentials. Use Render's
direct internal PostgreSQL endpoint with `sslmode=require`. Render's internal
TLS uses self-signed certificates and does not support `verify-full`; external
endpoints should use verified certificates where the provider supports them.
No currency, precision or timestamp types change. Psycopg preserves Decimal;
connections set UTC and have bounded statement/connect/pool timeouts.

Cookie policy is not user-configurable: production HTTPS enables
`__Host-ledgerx_session`, Secure, HttpOnly, Path=/, no Domain and SameSite=Lax.
Sessions retain 30-minute idle/seven-day absolute expiration, login rotation,
CSRF rotation and logout/current-all. Local development uses its own exact
loopback origin and database. Production does not allow localhost or wildcard
origins. Do not add preview-domain wildcards.

Argon2id uses the existing RFC 9106 low-memory profile: 64 MiB, time cost 3,
parallelism 4. Benchmark on the chosen host before changing these parameters;
there is no unsafe environment override. Session/reset tokens are random and
hashed, not signed: no JWT/session-signing secret or localStorage token is needed.

## Database and release procedure

1. Provision PostgreSQL and enable backups/PITR according to the chosen plan.
   Keep external access disabled (`ipAllowList: []`) between releases. For the
   operator's migration connection, temporarily allow only the operator's current
   IP, use the external TLS endpoint, and remove that access after verification.
2. Create a non-owner login role `ledgerx_app` with a generated secret using the
   provider's secure console. Give it CONNECT to the database and USAGE on public,
   but no CREATE, superuser or role-management privileges. Keep the owner URL for
   migrations. Revoke public CREATE on the schema where it is enabled.
3. Set the migration URL and production origin in a trusted release environment.
   Back up before upgrading an existing deployment. Only one release process may
   migrate at a time. Run `python -m ledgerx.db.migrate` from `/app` (or
   `uv run alembic upgrade head` from `apps/api` with the owner URL explicitly set).
   The release command takes a PostgreSQL advisory transaction lock, runs upgrade
   and checks model drift in one transaction. Concurrent releases fail safely;
   lock/statement waits are bounded. Application startup never creates tables.
   Stop the release on any error.
4. After the initial migration, grant runtime SELECT/INSERT/UPDATE/DELETE on
   application tables and SELECT on `alembic_version`; grant sequence usage where
   needed. Set equivalent default table/sequence privileges for future migrations.
   Revoke UPDATE/DELETE/TRUNCATE on `auth_audit_events`, `import_audit_events` and
   `transaction_audit_events`; append-only triggers remain an additional defense.
   Do not give the runtime role ownership of tables/functions. Never store the
   owner/migrator secret in Render's running API environment. Run migrations
   explicitly from a trusted operator environment before releasing the API.
5. Verify `alembic current`, `alembic heads` and `alembic check` using the migrator
   connection. Expected head is `0010_recovery_audit`; `check` must report no drift.
6. Start the production image only after the separate migration step passes.
   Render's health check is `/health/ready`. Verify `/health/live` and
   `/health/ready` return 200 and safe JSON. An unavailable DB or mismatched Alembic
   revision returns 503. No DDL credential or automatic migration is needed in the API.
7. Set Vercel's production API origin, deploy, and confirm the stable frontend
   hostname matches the backend first-party origin. Rebuild after changing it.

Test `upgrade head → downgrade base → upgrade head → alembic check` only on a
dedicated disposable database. Never downgrade production to base. Recovery
downgrade refuses to discard recorded password-reset audit events. Earlier recovery
downgrade removes outstanding reset tokens and budgets; use a tested backup or
forward fix for production rollback. Rehearse restore to a separate database and
verify users/import counts, ownership and exact transaction totals before launch.
Define retention, RPO/RTO, restore ownership and alerts before claiming readiness.

## Recovery, demo and operational limits

Request at `/forgot-password`; reset at `/reset-password`. Token lifetime is 20
minutes, single-use, hashed at rest. Successful reset revokes all sessions and
requires sign-in. Links use fragments, removed from history on page load. They
must not be copied into logs, screenshots or analytics. Mail delivery uses the
`recovery.deliver` adapter with STARTTLS, certificate validation and a timeout.
Delivery failures emit only `reset_delivery_failed`; monitor that event. SMTP is
synchronous and has no durable retry queue. Requests return the same body for
known/unknown users, but delivery latency can differ.

Local development: `docker compose exec api python -m
ledgerx.modules.identity.dev_reset_link --email user@example.com` prints a link
only to the trusted operator. This command refuses production/remote databases.
The older direct development password command is not a production recovery path.

`/demo` provides a 193-row fictional CSV, eight months January–August 2026. Register
a separate private account, download it, use Import Statement, review and finalize.
All nine requested analysis/history pages use normal ownership and import rules.
No shared credentials, real financial data, fabricated customer claims or auth
bypass. Historical Forecast correctly retains its normal historical limitations.

Production global per-minute budgets: login 60, registration 10, reset requests
10, reset completion 30. They are atomic PostgreSQL counters shared across workers;
only four rows are used. Failed attempts consume capacity. These are coarse abuse
budgets, not per-client protection: an attacker can deny other users capacity.
Add provider edge controls before broad exposure. No fake in-memory protection.
The production image also bounds concurrent requests to 16; load-test actual
memory and latency before raising concurrency.

Logs contain lifecycle, safe rejection codes, DB readiness failures, exception
types and correlation IDs. They omit bodies, SQL, cookies, credentials, filenames
and reset links. Access logs are disabled. Configure provider log retention and
alerts; do not enable request/body capture on the proxy or SMTP provider.

## Release smoke gate

Run the complete PostgreSQL backend suite, frontend tests/lint/typecheck/build,
Ruff/mypy, migration cycle/check and Docker health smoke before deploying.
After deployment, use a real browser to register, login, visit `/me` and each
private page, import the demo via recognition/preview/finalize, log out/in and
confirm persistence, test current/all logout, expiry and CSRF rejection. Use a
second account to verify transaction/import isolation. Exercise reset request,
valid completion, used/expired rejection and old-session revocation. Inspect
Set-Cookie at the frontend proxy and verify Secure/HttpOnly/SameSite/host scope.
Test DB unavailability on staging, never by disrupting production. Check frontend
and backend logs for safe failures. Local tests do not replace these hosted checks.

Provider references: [Vercel rewrites](https://vercel.com/docs/routing/rewrites),
[Render deploys](https://render.com/docs/deploys),
[Render PostgreSQL](https://render.com/docs/postgresql-creating-connecting),
[Render blueprint](https://render.com/docs/blueprint-spec).
