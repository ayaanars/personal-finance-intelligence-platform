# ADR 0016: Production hosting and credential recovery

Status: accepted for implementation; deployment awaits provider accounts and smoke tests.

## Context

The application uses opaque, hashed PostgreSQL sessions and exact first-party
Origin/Referer checks. Provider-generated Vercel and Render domains are separate
sites. Direct browser-to-backend authentication would require third-party cookies.

## Decision

Use Vercel for Next.js and Render for a persistent Docker FastAPI service and
PostgreSQL 17. Proxy `/api/v1` through Next.js; cookies remain host-only on the
frontend, Secure, HttpOnly and SameSite=Lax. Production accepts one exact HTTPS
frontend origin. Preview deployments must not access the production API.
Use explicit TLS PostgreSQL URLs, bounded pools and a separate Alembic release
step. No automatic table creation or migrations in application startup.
Migration-owner credentials stay in the operator's release environment, never
in the running API. Production readiness requires the release's Alembic revision.

Recovery tokens contain 256 random bits, expire after 20 minutes, and are stored
only as SHA-256 digests. Issuance invalidates older tokens. Completion locks the
user before the token, changes the Argon2id credential, consumes all outstanding
tokens and revokes every session in one transaction, including an append-only
authentication audit event. Concurrent login/reset uses the existing user-first
lock order. Recovery does not automatically sign in.
An SMTP adapter with mandatory STARTTLS is provider-independent. Unconfigured
delivery returns the same unavailable response for every email. Local operators
can issue a link through a development-only command, never a public API response.
Tokens travel in URL fragments, not query strings, and are removed from browser
history immediately. No token or password appears in application logs.

PostgreSQL enforces small global fixed-window budgets on anonymous auth endpoints
in production, across all workers. This caps hashing/email load without trusting
forwarded client IP headers or adding infrastructure. It is not comprehensive
bot/DDoS protection: one attacker can exhaust the shared budget. Provider edge
controls and monitoring remain required before a large public launch.

Demo exploration uses a downloadable, deterministic, clearly fictional CSV and
the normal private registration/import workflow. There is no shared demo password,
privileged account or bypass of ownership checks.

## Alternatives and consequences

Direct cross-site cookies and JWT migration add browser restrictions or change
the auth model. Hosting FastAPI as short-lived functions complicates connection
handling. Redis is unnecessary for a small PostgreSQL-backed auth budget.
SMTP delivery is synchronous and bounded; it is not a durable mail queue, and
delivery timing can reveal account existence. Responses never explicitly reveal
whether an account exists. Reliable queued email is deferred pending demand.
Paid persistent hosting/backups are needed for dependable production service.
Provider accounts, backup/restore verification and deployed browser tests remain
release gates, not implied by a successful local build.
