# ADR 0008: Local development password reset command

Status: Accepted under the explicit local-development-only user request, 2026-09-08.

The operator may run python -m ledgerx.modules.identity.dev_reset_password --email
from the configured local environment. Require development settings, a loopback
or local Compose db hostname, and no database URL query overrides. These guards
prevent accidental remote use; trusted operators must never point local forwarding
or the Compose hostname at production. Possession of development DB access is the
authorization boundary. No HTTP route, recovery UI, email flow or production reset.

Read and confirm the password through non-echoing getpass; abort if secure input
is unavailable. Reuse CredentialsInput validation/normalization and Passwords.hash
Argon2id. Lock the matching user as login does, then update only that credential's
password_hash and password_changed_at in one transaction. Missing users are not
created. Other credentials, users, workspaces, imports, facts and sessions are
untouched. Existing sessions intentionally remain valid under the requested
credential-only scope. No new audit event/schema is introduced for this local tool.
The command reports only fixed safe outcomes, never passwords, hashes or SQL.

This is a narrow exception to ADR 0003's absence of recovery tools, not a change to
product authentication. Broader recovery, revocation and audit policy are deferred.
