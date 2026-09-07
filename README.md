# LedgerX

Personal financial intelligence platform. This repository currently implements only
the development foundation: a Next.js page, FastAPI operational endpoints, and
PostgreSQL/SQLAlchemy/Alembic plumbing plus users/workspaces ownership tables. No financial or authentication features exist.

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

The frontend page has no API dependency and requires no environment variables.
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
npm run lint
npm run typecheck
npm run build
```

These commands also work through `docker compose exec api ...` (omit `uv run`)
and `docker compose exec web npm run ...`. Never place secrets in `NEXT_PUBLIC_*`.

## Architecture and status

`apps/web` owns presentation. `apps/api/src/ledgerx/main.py` composes configuration,
HTTP routes, and database lifecycle. `api/`, `core/`, and `db/` separate transport,
operational concerns, and persistence. The identity module contains User and Workspace persistence models. Alembic revision 0002_identity_ownership follows the empty baseline. See [database ownership ADR](docs/adr/0002-database-ownership-foundation.md).

See [architecture](docs/ARCHITECTURE.md), [foundation ADR](docs/adr/0001-development-foundation.md),
[current verification status](docs/STATUS.md), and [contribution guide](CONTRIBUTING.md).
