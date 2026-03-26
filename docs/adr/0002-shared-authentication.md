# 0002 — Centralised Authentication Module

**Date:** 2025-06-01
**Status:** Accepted

---

## Context

Each of the four education systems (University, College, Secondary School, Primary School)
originally maintained its own user tables, login screens, and password hashing logic. This led
to duplicated code, inconsistent security practices (e.g. the University used PBKDF2-SHA256
with a custom salt column; other systems used plain bcrypt), and no cross-system single sign-on.

Staff and administrators who work across systems were forced to maintain separate credentials.
There was no centralised MFA or session revocation.

Alternatives considered:
- Federate via an external IdP (Keycloak, Auth0) — rejected as too heavy for a self-hosted
  deployment
- Keep per-system auth but share via a library — rejected because user identity would still
  be fragmented across four databases

## Decision

We will implement a single shared authentication module at `education_system/shared/auth/`
backed by a central SQLite database at `education_system/shared/data/db_files/auth.db`.

Key design choices:

**Schema** (`shared/auth/schema.py`):
- `users` — stores credentials; includes `legacy_salt` for backward-compat migration
- `sessions` — DB-backed tokens with expiry; supports force-logout
- `mfa_secrets` / `mfa_recovery_codes` — TOTP via `pyotp`
- `user_systems` — maps each user to one or more systems with a per-system role

**Password hashing**: bcrypt via the `bcrypt` library. Legacy PBKDF2-SHA256 hashes (from the
original University system) are detected via the `legacy_salt` column and transparently
re-hashed to bcrypt on the first successful login.

**MFA**: TOTP (RFC 6238) with 8 single-use recovery codes per user. Enforced optionally per
user; the `mfa_gui.py` dialog handles both the tkinter GUI and the REST flow.

**Sessions**: tokens are random 32-byte hex strings stored in `sessions` with an expiry
timestamp. The university system also issues JWTs for the REST API (via `jwt_utils.py`).

**Per-system roles**: the `user_systems` table allows a single account to be
`admin` in the university and `staff` in the college. The `system_required()` decorator in
the API layer gates routes based on the JWT's `systems` claim.

**Backward compatibility**: the University auth wrapper (`university_system/infrastructure/auth/`)
tries shared auth first and falls back to the legacy `user_accounts` table. The `current_user`
dict includes both `id` and `user_id` keys so existing university code continues to work.

18 default accounts are seeded: one superadmin (all four systems) and per-system
admin/staff/student/parent accounts. Password pattern: `<Role>@<System>123`.

## Consequences

### Positive
- Single set of credentials works across all four systems
- Consistent bcrypt hashing and lockout policy (configurable via `shared/auth/defaults.py`)
- Force-logout any session from the superadmin dashboard
- MFA state and recovery codes managed in one place

### Negative / Trade-offs
- `auth.db` is a single point of failure; if it is corrupted, all four systems lose login
- Migration script (`university_system/infrastructure/auth/migration_to_shared.py`) must be
  run once when upgrading existing deployments
- Per-system legacy code that reads `current_user["user_id"]` depends on the compatibility shim

### Neutral
- College, Secondary, and Primary `infrastructure/auth/` directories are thin re-export
  wrappers; they exist only to preserve import paths used elsewhere in each system

---

*See also: [0001](0001-unified-flask-server.md) (unified server), [0003](0003-sqlite-per-system.md) (database strategy)*
