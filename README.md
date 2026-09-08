# LedgerX

Personal financial intelligence platform. The repository implements a development
foundation, backend authentication and canonical CSV statement imports with
PostgreSQL staging and explicit finalization. Phase 10's public product page and
login/register flow are complete. The existing authenticated statement-to-history
implementation is preserved in progress; private-app completion is a separate task.
The implemented CSV contract is documented in [API.md](docs/API.md) and
[ADR 0004](docs/adr/0004-canonical-csv-import.md).

## Requirements

- Python 3.13, Node.js 22 (at least 22.16), npm 10, uv 0.12.10.
- Docker Engine/Desktop with Compose v2 for the full development stack.
- PostgreSQL 17 if running the database outside Docker.

## Docker development

From the repository root:

```powershell
Copy-Item .env.example .env
# Edit .env: set a local password and matching URL (URL-encode credentials).
docker compose config --quiet
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose ps
```

Open <http://localhost:3000>, <http://localhost:8000/health/live>, and
<http://localhost:8000/health/ready>. API documentation: <http://localhost:8000/docs>.
All published ports bind to loopback; PostgreSQL data persists in a named volume.
Source edits reload in containers. Rebuild after dependency/configuration changes.
`docker compose down` stops the stack and preserves database data.

This is development infrastructure. Never use real statements or production data.
The local database owner role is not a production runtime credential.

## Native application development

Start the database with `docker compose up -d db` after configuring root `.env`,
or supply your own PostgreSQL 17 database. In `apps/api`:

```powershell
Copy-Item .env.example .env
# Edit the URL to match the development database.
uv sync --locked
uv run alembic upgrade head
uv run uvicorn ledgerx.main:create_app --factory --reload --host 127.0.0.1 --no-access-log
```

In a separate terminal, from `apps/web`:

```powershell
npm ci
npm run dev
```

The public landing page is `/`. Authentication lives at `/login` and `/register`;
the private product starts at `/app`. Upload at `/app/import` and review history at
`/app/transactions`. Existing preview/detail URLs redirect to their `/app` equivalents.

The frontend forwards `/api/v1/*` to FastAPI using the server-only
`LEDGERX_API_ORIGIN` (native default `http://127.0.0.1:8000`; Compose sets
`http://api:8000`). Open the browser at `http://localhost:3000` to match the backend
first-party origin. Rebuild/restart Next.js after changing this setting.
`LEDGERX_FIRST_PARTY_ORIGIN` defaults to `http://localhost:3000`. Set one exact
browser origin, without a trailing slash. HTTP origins are restricted to loopback;
HTTPS enables Secure cookies with the `__Host-` prefix. Production runtime remains
disabled pending deployment/security gates; this is development/test infrastructure.
Backend settings read `apps/api/.env` when launched from that directory; environment
variables override the file. The URL is required. Liveness works with an unavailable
database; readiness returns a generic 503. No migrations run at application startup.

## Checks

From `apps/api`:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run alembic heads
uv run alembic upgrade head --sql
```

The PostgreSQL tests skip explicitly unless `LEDGERX_TEST_DATABASE_URL` points to
a dedicated PostgreSQL database. To run them, set that variable and run
`uv run pytest -m integration`. An unreachable configured database fails the tests. Foundation tests create and clean up a unique schema per test; the dedicated test role needs schema creation privileges.
Migration verification uses a disposable database: `uv run alembic upgrade head`,
`uv run alembic check`, `uv run alembic downgrade base`, `uv run alembic upgrade head`.

From `apps/web`:

```powershell
npm run test
npm run lint
npm run typecheck
npm run build
```

These commands also work through `docker compose exec api ...` (omit `uv run`)
and `docker compose exec web npm run ...`. Never place secrets in `NEXT_PUBLIC_*`.

## Architecture and status

`apps/web` owns presentation. `apps/api/src/ledgerx/main.py` composes configuration,
HTTP routes, and database lifecycle. `api/`, `core/`, and `db/` separate transport,
operational concerns, and persistence. The identity module owns transactional
registration, Argon2id credentials, opaque sessions and authentication audit events.
Revision `0003_authentication` follows the users/workspaces foundation. See the
[authentication ADR](docs/adr/0003-authentication-sessions.md) and
[authentication threat model](docs/threat-model/authentication.md).

## Authentication API

All routes use `/api/v1`. `POST /auth/register` accepts only `email` and `password`,
creates a user/private workspace atomically, and returns 201 with a safe profile.
Passwords allow 15–128 characters without composition rules or trimming. Email
syntax is ASCII-only, space-trimmed and lowercased for lookup; aliases are preserved.
Registration does not sign in. `POST /auth/login` accepts the same fields and returns
204 with an HttpOnly session cookie; it never returns the session token in JSON.

`GET /me` returns the user/workspace. `GET /auth/csrf` returns a newly rotated
`csrf_token`; send it as `X-CSRF-Token` with `Content-Type: application/json` on
`POST /auth/logout` or `POST /auth/logout-all` (empty JSON object is sufficient).
Both return 204 and clear the cookie after committing revocation. Read-only requests
do not require the CSRF header. Browser requests use the configured first-party
origin and credentialed cookies. CSRF rotation invalidates tokens held in other tabs.

Sessions expire after 30 idle minutes or seven absolute days. Server idle refresh
runs at most once per minute. Logout-all revokes existing sessions; a subsequent
successful password login can create a new one. Future protected endpoints use
`Authenticated` from `api/auth_security.py`, retain its transaction through their
operation, and add owner-scoped object authorization.

Rate limiting, production hash calibration, email verification, password recovery,
OAuth and MFA are deferred. No recovery bypass exists. Public launch requires
abuse controls and the deployment gates documented in the threat model.

See [architecture](docs/ARCHITECTURE.md), [foundation ADR](docs/adr/0001-development-foundation.md),
[current verification status](docs/STATUS.md), and [contribution guide](CONTRIBUTING.md).

## Product scope

The client uses cookie sessions, CSRF-protected raw CSV uploads, explicit
whole-import finalization, bounded transaction pages and versioned category corrections.
Amounts remain exact decimal strings. The landing-page example is clearly labeled
synthetic; private screens always read the real backend. Behavioral analytics and
other planned intelligence remain unavailable. See [ADR 0006](docs/adr/0006-public-entry-and-product-client.md).
