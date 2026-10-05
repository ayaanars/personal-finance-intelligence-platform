# Authentication threat model

Scope: opaque cookie sessions, owner-scoped private financial resources, and
one-time recovery under ADRs 0003 and 0016.

## Assets and boundaries

Passwords, encoded hashes, session/CSRF secrets and login emails cross the browser
to API boundary. Only password hashes, session/CSRF digests and safe lifecycle
audit identifiers cross into PostgreSQL. CORS uses one exact first-party origin.
The API derives user/workspace identity from the validated session; neither body
fields nor query parameters select a principal. Operators and the database owner
remain privileged actors outside the protection of application row checks.

## Abuse cases and controls

| Threat | Implemented control | Verification / residual limit |
|---|---|---|
| Password database disclosure | Salted Argon2id, RFC 9106 low-memory profile | Encoded parameters, unique salts, verification and login rehash tests; production calibration pending |
| Credential stuffing / hash-work exhaustion | Bounded 15–128 character passwords, generic login error, dummy-hash verification for absent users | PostgreSQL global attempt budgets cap production auth work; per-client edge controls, request-byte limits and host load testing remain launch gates |
| Email enumeration | Generic 409 registration failure and generic 401 login failure | Registration status still reveals a duplicate; no claim of complete enumeration resistance or equal end-to-end timing |
| Session fixation / prediction | Fresh 256-bit CSPRNG token on every successful login; same-user prior session revoked | Fixation/rotation tests and generator inspection; random-sample uniqueness is not a proof of entropy |
| Read-only session-table disclosure | SHA-256 digests only; no session token in response JSON | Database storage assertions; active client/session theft still permits impersonation |
| CSRF | Session-bound token hash, constant-time digest comparison, JSON-only unsafe routes, origin checks, SameSite=Lax | Missing/invalid/rotated/other-session token tests; registration/login use JSON + origin protection without anonymous sessions |
| Session resurrection | User then session row locks held through protected transaction commit; server deadlines and revocation checked after locking | Current/all logout, deadline equality, refresh bounds, concurrent refresh/logout-all tests |
| Cross-user principal substitution | Session digest resolves owner; workspace lookup has owner predicate; logout-all owner-scoped | Different-user session and CSRF tests; transaction/import/analytics/goal queries require user/workspace predicates |
| Partial registration / logout | User, credential, workspace and audit transaction; revocation and audit transaction | Injected DB failures, duplicate race, rollback tests |
| Secret leakage through errors/logs/cache | Generic validation envelope, no input/exception serialization, fixed-shape audit, no-store responses | Captured application logs and error tests; hosting proxies/APM still need deployment sampling |
| Audit rewriting | PostgreSQL trigger rejects UPDATE/DELETE/TRUNCATE | Direct SQL tests; privileged owner can disable/drop trigger, so this is not protection against administrators |
| Cookie theft / scope confusion | HttpOnly, host-only, Path=/, Lax; Secure and __Host- on HTTPS; centralized matching deletion | Cookie tests for HTTP/HTTPS; deployed browser/TLS checks deferred |

## Credential lifecycle and recovery

Registration creates an active account with an unverified email login identifier.
Passwords are not normalized or truncated; ASCII email syntax is validated without
DNS, then space-trimmed and lowercased for lookup. Provider aliases are preserved.
Internationalized email is explicitly rejected until its policy is approved.
Hash upgrades happen after successful verification. Recovery uses 256-bit random,
SHA-256-hashed tokens with a 20-minute expiry and user-first row locks. Issuance
replaces older tokens; completion consumes them and revokes every session atomically.
Token fragments are removed from browser history. SMTP requires TLS; disabled
delivery returns a uniform unavailable response. No token is returned by the API.
Responses do not disclose account existence, but SMTP latency can differ. Provider
email delivery, mail-log redaction and sender ownership need operational verification.
No verification email, OAuth, MFA or support impersonation endpoint exists.

The approved session limits are 30-minute idle and seven-day absolute, with idle
refresh at most once per minute. A later valid password login can create a session
after logout-all. Logout does not retroactively undo a request already committed.
CSRF GET rotates material; another tab holding the old token must fetch again.

## Deployment gates

Production settings require HTTPS and explicit PostgreSQL TLS. Vercel rewrites
keep cookies first-party while Render hosts FastAPI and PostgreSQL. Deployment
requires provider accounts, runtime/migration roles, mail configuration, retention
policies, backup/restore rehearsal, edge abuse controls and hosted browser checks.
The four PostgreSQL counters are distributed global budgets, not per-client limits;
one attacker can consume shared capacity. No production-readiness claim is made
until these gates are verified. See [the production runbook](../runbooks/production.md).
