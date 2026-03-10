# Secondary School Management System - Authentication

> Last Updated: March 2026

## Overview

The Secondary School Management System uses a shared authentication module located at `education_system/shared/auth/`. This module is shared across all four Education System platforms (University, College, Secondary School, Primary School), providing centralised user management, session handling, and multi-factor authentication.

The Secondary School system accesses shared auth through a thin wrapper at `secondary_school/infrastructure/auth/`, which re-exports shared auth functionality with school-specific defaults.

## Architecture

```
education_system/
  shared/
    auth/                          # Shared auth module (single source of truth)
      __init__.py
      auth_service.py              # Core authentication logic
      session_manager.py           # Session creation/validation
      mfa_service.py               # TOTP and recovery codes
    data/
      db_files/
        auth.db                    # Shared auth database
  secondary_school/
    infrastructure/
      auth/                        # Thin wrapper re-exporting shared auth
        __init__.py
```

## Auth Database (auth.db)

All authentication data is stored in `education_system/shared/data/db_files/auth.db`.

### Tables

#### `users`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `username` | TEXT | Unique username |
| `password_hash` | TEXT | bcrypt hash |
| `legacy_salt` | TEXT | PBKDF2-SHA256 salt (for migration, nullable) |
| `email` | TEXT | User email address |
| `is_active` | INTEGER | Account active flag (0/1) |
| `failed_login_attempts` | INTEGER | Consecutive failed login count |
| `locked_until` | TIMESTAMP | Account lockout expiry (nullable) |
| `created_at` | TIMESTAMP | Account creation timestamp |
| `updated_at` | TIMESTAMP | Last modification timestamp |

#### `sessions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK to users.id |
| `token` | TEXT | Unique session token |
| `created_at` | TIMESTAMP | Session start time |
| `expires_at` | TIMESTAMP | Session expiry (default: 30 minutes) |
| `is_valid` | INTEGER | Session active flag |

#### `mfa_secrets`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK to users.id |
| `secret` | TEXT | TOTP secret key |
| `is_enabled` | INTEGER | MFA active flag |
| `created_at` | TIMESTAMP | Setup timestamp |

#### `mfa_recovery_codes`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK to users.id |
| `code` | TEXT | Hashed recovery code |
| `is_used` | INTEGER | Whether the code has been consumed |
| `created_at` | TIMESTAMP | Generation timestamp |

#### `user_systems`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK to users.id |
| `system` | TEXT | System identifier (`school` for secondary) |
| `role` | TEXT | Role within that system |
| `is_active` | INTEGER | Mapping active flag |

## System Identifier

The Secondary School system is identified as `"school"` in the `user_systems` table. When authenticating, the system queries `user_systems` for entries where `system = 'school'` to determine the user's role and access level.

## Password Hashing

### bcrypt (Standard)

All new passwords and password changes use bcrypt hashing:

```python
import bcrypt

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
```

### Legacy PBKDF2-SHA256 Migration

Older accounts may have passwords hashed with PBKDF2-SHA256 (indicated by a non-null `legacy_salt` column). These are transparently migrated to bcrypt on first successful login:

1. User submits credentials.
2. System detects `legacy_salt` is not null.
3. Password is verified against the PBKDF2-SHA256 hash using the stored salt.
4. If valid, the password is re-hashed with bcrypt.
5. The `password_hash` column is updated and `legacy_salt` is set to null.
6. Login proceeds normally.

This migration is seamless and requires no action from users or administrators.

## Session Management

Sessions are database-backed with token-based validation:

- **Session timeout**: 30 minutes of inactivity (configurable via `SESSION_TIMEOUT`).
- **Token format**: Cryptographically random tokens generated with `secrets.token_urlsafe()`.
- **Validation**: Each request validates the session token against `auth.db`, checking `is_valid` and `expires_at`.
- **Renewal**: Session expiry is extended on each valid request.
- **Logout**: Sets `is_valid = 0` for the session record.

```python
# Session validation flow
session = get_session(token)
if session and session["is_valid"] and session["expires_at"] > now():
    extend_session(token)  # Reset expiry timer
    return session["user_id"]
else:
    return None  # Session invalid or expired
```

## Account Lockout

To prevent brute-force attacks, accounts are locked after repeated failed login attempts:

| Parameter | Value |
|-----------|-------|
| Max failed attempts | 5 (`MAX_LOGIN_ATTEMPTS`) |
| Lockout duration | 15 minutes |
| Counter reset | On successful login |

When an account is locked:

1. The `locked_until` timestamp is set to 15 minutes in the future.
2. All login attempts are rejected until the lockout expires, regardless of password correctness.
3. The `failed_login_attempts` counter is preserved.
4. On successful login after lockout, the counter resets to 0.

## Roles

The Secondary School system defines three roles in `user_systems`:

| Role | Description | Typical Access |
|------|-------------|----------------|
| `admin` | School administrators | Full system access, user management, settings, reports |
| `teacher` | Teaching staff | Student records, grades, attendance, pastoral care, timetable |
| `student` | Students | Own records, homework, timetable (read-only for most modules) |

Role-based access control (RBAC) is enforced at the service layer. Each module checks the current user's role before allowing operations.

## Default Accounts

The system ships with pre-configured accounts for each role. These are intended for initial setup and testing and should be changed in production.

| Username | Password | System | Role |
|----------|----------|--------|------|
| `superadmin` | `Superadmin@All123` | All 4 systems | admin |
| `school_admin` | `Admin@School123` | school | admin |
| `school_teacher` | `Staff@School123` | school | teacher |
| `school_student` | `Student@School123` | school | student |
| `school_parent` | `Parent@School123` | school | parent |

**Important**: Change all default passwords before deploying to production. The `superadmin` account has access to all four systems and should be secured with MFA immediately.

## Universal Login Flow

The Education System platform provides a universal login window (`education_system/shared/gui/login_gui.py`) that handles authentication across all four systems.

### Flow

1. User launches the application via `run.py`.
2. The Universal Login Window (`UniversalLoginWindow`) is displayed.
3. User enters credentials (username + password).
4. Shared auth module validates credentials against `auth.db`.
5. If MFA is enabled, the user is prompted for a TOTP code or recovery code.
6. On success, `user_systems` is queried for the user's system mappings.
7. If the user has access to multiple systems, a system selector is shown.
8. The selected system's GUI launcher is invoked with `user_info=`, `role=`, and `shared_auth=` parameters, bypassing any local login screen.

### Direct Launch (Bypassing Universal Login)

Individual system launchers can also be started directly for development or testing:

```bash
/home/seancatchpole989/venv/bin/python -m secondary_school.main
```

This will show the system's own login screen, which delegates to the shared auth module.

## Integration Points

- **Audit logging**: All authentication events (login, logout, failed attempts, lockouts) are recorded in the secondary school's `audit_log` table.
- **Session validation**: GUI and API endpoints validate session tokens on each operation.
- **Role checks**: Service layer methods verify the user's role before executing operations.
