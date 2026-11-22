# Shared Authentication System

The Education System uses a single, unified authentication module shared by all seven systems (Nursery, Primary School, Secondary School, Sixth Form College, FE College, Apprenticeships, University).

Source: `src/education_system/platform/identity/auth/`

---

## Architecture

```
src/education_system/platform/identity/auth/
├── core.py              # UserAuth facade — login, logout, user CRUD
├── password_manager.py  # bcrypt hashing, verification, strength rules
├── session_manager.py   # DB-backed token sessions with expiry
├── role_manager.py      # RBAC with hierarchical roles
├── mfa_service.py       # TOTP setup and verification
├── db.py                # SQLite connection helper
├── schema.py            # Table creation, migrations and default accounts
├── defaults.py          # Timeouts, lockout settings and system definitions
└── exceptions.py        # AuthError and subclasses
```

Systems import from `education_system.platform.identity.auth` directly. Only the University has its own `infrastructure/auth/` package, a compatibility layer that falls back to its old `user_accounts` table.

## Database

Central auth database: `var/data/platform/db_files/auth.db`

### Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts — username, email, bcrypt hash, `legacy_salt` for PBKDF2 migration |
| `sessions` | Active sessions — token, user_id, expiry timestamp |
| `mfa_secrets` | TOTP secrets per user |
| `mfa_recovery_codes` | One-time recovery codes |
| `user_systems` | Maps users to systems (`university`, `sixth_form`, `secondary`, `primary`, `nursery`, `fe_college`, `apprenticeships`) with per-system roles |

## Password Hashing

- **Current**: bcrypt (via `bcrypt` library)
- **Legacy**: PBKDF2-SHA256 supported via the `legacy_salt` column in `users`
- Legacy hashes are transparently re-hashed to bcrypt on first successful login
- Password strength rules enforced at creation/change time

## Sessions

- Cryptographically random token generated at login
- Stored in `sessions` table with expiry timestamp
- Validated on each authenticated request
- GUI/CLI use session tokens; the unified REST API issues JWT tokens through `src/education_system/platform/delivery/api/security/authentication.py`

## Roles and Access Control

Role hierarchy is defined per system. The `user_systems` table stores a user's role in each system they can access. A single user can have different roles in different systems (e.g. `admin` in Sixth Form College, `staff` in Secondary School).

## Cross-System Access

The `user_systems` table enables a single account to access multiple systems. The Universal Login window (see [UNIVERSAL_LOGIN.md](UNIVERSAL_LOGIN.md)) lists the systems available to the authenticated user and lets them choose which to launch.

## Default Accounts

26 demo accounts are created only when `EDU_DEV_SEED=true`; a fresh `auth.db` without the flag starts empty:

- **superadmin** — access to all 7 systems
- Per-system accounts, listed in [DEFAULT_ACCOUNTS.md](../reference/DEFAULT_ACCOUNTS.md)

## Per-System Auth Wrappers

Only the University has a wrapper:

| System | Wrapper location | Notes |
|--------|-----------------|-------|
| University | `src/education_system/systems/university/infrastructure/auth/` | Wraps shared auth; falls back to legacy `user_accounts` table; `current_user` includes both `id` and `user_id` keys |

## Migration

University users from the old standalone auth can be migrated using:
`src/education_system/systems/university/infrastructure/auth/migration_to_shared.py`

---

See also: [MFA Guide](MFA_GUIDE.md) | [Universal Login](UNIVERSAL_LOGIN.md)
