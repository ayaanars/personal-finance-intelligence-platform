# ADR 0003: Password authentication and PostgreSQL sessions

Status: Accepted for authentication scope, 2026-09-07. User explicitly confirmed
the proposed lifetime, refresh cadence and CSRF transport before implementation.

## Context

The authentication-only implementation request authorizes registration, login,
current-user retrieval, current/all-session logout, Argon2id, opaque sessions and
CSRF. SECURITY.md explicitly requires lifetime and transport confirmation. The
existing foundation tests pass against PostgreSQL (29 tests, 2026-09-07).

## Decision

- Registration accepts email/password only and creates an active user, one private
  workspace, credential and authentication audit event in one transaction. It
  does not log the user in. Duplicate normalized emails receive a generic 409
  registration failure; the status still allows enumeration, a residual limitation.
- Preserve space trimming and whole-address lowercase lookup, with no provider
  dot/alias rewriting. Preserve the trimmed display form. Validate email syntax at
  the boundary without DNS or email-delivery dependencies. Reject non-ASCII email
  until an internationalization policy is approved. Passwords accept 15–128 Unicode
  characters without composition rules, normalization or trimming.
- Use maintained argon2-cffi with explicit RFC 9106 low-memory Argon2id parameters
  (64 MiB, three iterations, four lanes, 16-byte salt, 32-byte output), individual
  random salts and rehash on successful login when parameters change. Calibrate
  before public deployment. Never normalize, truncate or log passwords.
- Generate independent 256-bit random opaque session and CSRF secrets using the
  standard library CSPRNG; store only SHA-256 digests. High-entropy secrets do not
  need password hashing. Sessions contain no encoded identity.
- Approved expiry: 30-minute idle and seven-day absolute limits; refresh idle
  activity at most once per minute, capped by absolute expiry. Reject equality at
  either deadline. Revocation must remain effective during concurrent requests.
- A successful login always creates a fresh session. Revoke a presented prior
  session only when it belongs to the same authenticated user. Never let one
  user's login revoke another user's sessions through a supplied cookie.
- Resolve the acting user and workspace from a validated session, require active
  user status, and expose a reusable dependency that also enforces CSRF on unsafe
  methods. Serialize identity lifecycle operations with a user-row lock, then a
  session-row lock, in consistent order. Logout-all revokes sessions existing at
  its serialized point; a later successful password login can establish a new one.
- Centralize host-only, HttpOnly, SameSite=Lax, Path=/ cookies with no Domain.
  Local HTTP uses an unprefixed development name. HTTPS uses Secure and a __Host-
  name. The foundation still rejects production runtime configuration until its
  deployment security gates are implemented.
- Approved CSRF transport: authenticated GET /api/v1/auth/csrf rotates the session's
  CSRF token hash and returns the new token in a no-store JSON response. Mutations send
  X-CSRF-Token; compare digests with constant-time comparison. Rotation invalidates
  previously fetched tokens, so multiple tabs must fetch again after rejection.
  Reject untrusted Origin/Referer headers and simple content types. Anonymous
  registration/login require JSON and the same origin checks, without creating
  anonymous sessions. CORS allows only the configured exact first-party origin.
- Safe error envelopes never echo credential input, library exceptions or SQL.
  Authentication audit records contain identifiers and fixed event codes only.

## Alternatives

JWTs contradict the approved model. Redis is unnecessary. Plaintext stored session
tokens make a database read leak directly usable credentials. SameSite alone does
not provide the required CSRF control. An in-memory limiter cannot provide the
required shared production guarantees.

## Consequences and deferrals

Rate limiting is deferred under the explicit task exception: current docs specify
neither concrete parameters nor an MVP-compatible shared implementation. Do not
publicly launch these endpoints before a tested abuse-control policy, hardware
hash calibration, least-privilege roles, TLS and deployment verification exist.
No failed-attempt/lockout columns are added without that policy.

Email verification, password recovery, OAuth, MFA, email delivery and all financial
features remain outside scope. There is no recovery bypass. Session/audit purge
retention and tamper-resistant audit export require an operational decision; no
cleanup silently deletes records. Migration downgrade removes authentication
records and is for disposable testing only; populated environments need backup and
a reviewed roll-forward strategy.

## References

- [Argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html)
- [Argon2 parameter guidance](https://argon2-cffi.readthedocs.io/en/stable/parameters.html)
- SECURITY.md, API.md, DATABASE.md and ADR 0002.
