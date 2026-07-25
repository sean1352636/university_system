# Shared Authentication System

The Education System uses a single, unified authentication module shared by all four subsystems (University, College, Secondary School, Primary School).

Source: `education_system/shared/auth/`

---

## Architecture

```
shared/auth/
├── core.py              # UserAuth facade — login, logout, user CRUD
├── password_manager.py  # bcrypt hashing, verification, strength rules
├── session_manager.py   # DB-backed token sessions with expiry
├── role_manager.py      # RBAC with hierarchical roles
├── mfa_service.py       # TOTP setup and verification
├── db.py                # SQLite connection helper
├── schema.py            # Table creation / migrations
├── defaults.py          # Default accounts and system definitions
└── exceptions.py        # AuthError and subclasses
```

Each subsystem's `infrastructure/auth/` re-exports from `shared.auth` (thin wrappers). The University system adds a legacy-compatibility layer that falls back to its old `user_accounts` table.

## Database

Central auth database: `education_system/shared/data/db_files/auth.db`

### Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts — username, email, bcrypt hash, `legacy_salt` for PBKDF2 migration |
| `sessions` | Active sessions — token, user_id, expiry timestamp |
| `mfa_secrets` | TOTP secrets per user |
| `mfa_recovery_codes` | One-time recovery codes |
| `user_systems` | Maps users to systems (`university`, `college`, `school`, `primary`) with per-system roles |

## Password Hashing

- **Current**: bcrypt (via `bcrypt` library)
- **Legacy**: PBKDF2-SHA256 supported via the `legacy_salt` column in `users`
- Legacy hashes are transparently re-hashed to bcrypt on first successful login
- Password strength rules enforced at creation/change time

## Sessions

- Cryptographically random token generated at login
- Stored in `sessions` table with expiry timestamp
- Validated on each authenticated request
- GUI/CLI use session tokens; the University and College REST APIs issue JWT tokens via their own `api/auth.py` layers

## Roles and Access Control

Role hierarchy is defined per system. The `user_systems` table stores a user's role in each system they can access. A single user can have different roles in different systems (e.g. `admin` in College, `staff` in Secondary School).

## Cross-System Access

The `user_systems` table enables a single account to access multiple systems. The Universal Login window (see [UNIVERSAL_LOGIN.md](UNIVERSAL_LOGIN.md)) lists the systems available to the authenticated user and lets them choose which to launch.

## Default Accounts

18 default accounts are created on first run:

- **superadmin** — access to all 4 systems
- Per system: **admin**, **staff**, **student**, **parent**
- Password pattern: `<Role>@<System>123` (e.g. `Admin@University123`, `Staff@College123`)

## Per-System Auth Wrappers

| System | Wrapper location | Notes |
|--------|-----------------|-------|
| University | `university_system/infrastructure/auth/` | Wraps shared auth; falls back to legacy `user_accounts` table; `current_user` includes both `id` and `user_id` keys |
| College | `college_system/infrastructure/auth/` | Thin re-export from shared |
| Secondary | `secondary_school/infrastructure/auth/` | Thin re-export from shared |
| Primary | `primary_school/infrastructure/auth/` | Thin re-export from shared |

## Migration

University users from the old standalone auth can be migrated using:
`university_system/infrastructure/auth/migration_to_shared.py`

---

See also: [MFA Guide](MFA_GUIDE.md) | [Universal Login](UNIVERSAL_LOGIN.md)
