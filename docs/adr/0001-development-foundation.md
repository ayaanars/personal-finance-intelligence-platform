# ADR 0001: Development foundation

Date: 2026-09-07
Status: Accepted within the user-authorized foundation scope

## Context

The user authorized implementation of the no-feature foundation described in
ARCHITECTURE.md. Product, accounting, identity, and production decisions remain open.

## Decision

- Use independent `apps/web` (Next.js App Router, strict TypeScript, Tailwind) and
  `apps/api` (FastAPI, Pydantic settings, SQLAlchemy 2, synchronous psycopg 3).
- Use Python 3.13, Node.js 22, and PostgreSQL 17 for development. Production must
  retain the PostgreSQL major version or approve and test an explicit migration.
- Pin direct dependencies and retain npm and uv locks. Pin container images by digest.
- Own SQLAlchemy engines through application lifespan; application services will
  own explicit session transaction boundaries when they exist.
- Use Alembic with an empty baseline; never create domain tables speculatively.
- Implement the documented unversioned operational paths `/health/live` and
  `/health/ready`; readiness checks PostgreSQL. No `/api/v1` business API exists yet.
- Bind development ports to loopback. Compose uses a disposable development database
  owner role; production role separation is a required later deployment task.
- Accept development/test settings only. Production deployment is deliberately not
  configured. No browser API integration or CORS policy is needed for the static page.

## Alternatives

SQLite would not validate PostgreSQL behavior. Async DB access, Redis, workers, and
additional domain scaffolding add no value to this bounded foundation. Framework
startup schema creation would bypass the required explicit migration workflow.

## Consequences

The apps can be installed, checked, and run separately. PostgreSQL is required for
readiness and integration tests, but liveness/unit tests can run without it. Docker
images currently include development tooling and reload servers; they are not a
production deployment. Authentication, isolation, money, imports, ledger, and risk
ADRs remain prerequisites for their respective implementations.
