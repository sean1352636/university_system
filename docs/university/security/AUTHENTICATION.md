# Authentication Flow Documentation

## Overview

The University Management System implements a secure, centralized authentication system with role-based access control (RBAC). This document describes the authentication and authorization flows, security measures, and implementation details.

## Table of Contents

- [Architecture](#architecture)
- [Authentication Flow](#authentication-flow)
- [Password Security](#password-security)
- [Session Management](#session-management)
- [Authorization](#authorization)
- [Role-Based Access Control](#role-based-access-control)
- [Implementation Examples](#implementation-examples)
- [Security Features](#security-features)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │   CLI    │    │   GUI    │    │    Web Interface     │  │
│  └────┬─────┘    └─────┬────┘    └──────────┬───────────┘  │
└───────┼────────────────┼────────────────────┼───────────────┘
        │                │                    │
        └────────────────┼────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────────┐
│                        v                                     │
│              Authentication Layer                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     platform/identity/auth/core.py (UserAuth)        │  │
│  │  - User authentication                               │  │
│  │  - Password hashing/verification                     │  │
│  │  - Session management                                │  │
│  │  - Permission checking                               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────────┐
│                        v                                     │
│                   Database Layer                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │  users   │    │sessions  │    │ security_audit_log   │  │
│  └──────────┘    └──────────┘    └──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Files

- `src/education_system/platform/identity/auth/core.py`: Shared `UserAuth`, which signs users in against the central `auth.db` (`var/data/platform/db_files/auth.db`)
- `src/education_system/platform/identity/auth/password_manager.py`: Password hashing and validation
- `src/education_system/platform/identity/auth/session_manager.py`: Session tokens
- `src/education_system/systems/university/infrastructure/auth/facade.py`: The university's `UserAuth` façade, which delegates sign-in to the shared auth
- `src/education_system/systems/university/infrastructure/auth/core_utils/constants.py`: Role and permission definitions
- `src/education_system/systems/university/infrastructure/database/db.py`: Database operations

## Authentication Flow

### 1. Login Process

```
┌─────────┐           ┌──────────────┐           ┌──────────┐
│  User   │           │   Auth       │           │ Database │
│         │           │  System      │           │          │
└────┬────┘           └──────┬───────┘           └─────┬────┘
     │                       │                         │
     │  1. Submit            │                         │
     │  credentials          │                         │
     ├──────────────────────>│                         │
     │                       │                         │
     │                       │  2. Query user by       │
     │                       │     username            │
     │                       ├────────────────────────>│
     │                       │                         │
     │                       │  3. Return user record  │
     │                       │     (hash, role)        │
     │                       │<────────────────────────┤
     │                       │                         │
     │                       │  4. Verify submitted    │
     │                       │     password (bcrypt)   │
     │                       │                         │
     │                       │  5. Compare hashes      │
     │                       │                         │
     │                       ├─┐                       │
     │                       │ │ If match:             │
     │                       │ │                       │
     │                       │ │ 6. Create session     │
     │                       │ │    token              │
     │                       │<┘                       │
     │                       │                         │
     │                       │  7. Store session       │
     │                       ├────────────────────────>│
     │                       │                         │
     │                       │  8. Log successful      │
     │                       │     login to audit log  │
     │                       ├────────────────────────>│
     │                       │                         │
     │  9. Return session    │                         │
     │     token + user info │                         │
     │<──────────────────────┤                         │
     │                       │                         │
     ├─┐                     │                         │
     │ │ 10. Store token     │                         │
     │ │     for subsequent  │                         │
     │ │     requests        │                         │
     │<┘                     │                         │
     │                       │                         │
```

### 2. Failed Login Attempt

```
If password doesn't match:
  1. Increment failed_login_attempts
  2. Log failed attempt to security_audit_log
  3. If attempts >= MAX_LOGIN_ATTEMPTS (3):
     - Set locked_until (15 minutes)
  4. Return generic error message (prevent username enumeration)
```

### 3. Logout Process

```
┌─────────┐           ┌──────────────┐           ┌──────────┐
│  User   │           │   Auth       │           │ Database │
└────┬────┘           └──────┬───────┘           └─────┬────┘
     │                       │                         │
     │  1. Logout request    │                         │
     │     with session token│                         │
     ├──────────────────────>│                         │
     │                       │                         │
     │                       │  2. Delete session      │
     │                       ├────────────────────────>│
     │                       │                         │
     │                       │  3. Log logout event    │
     │                       ├────────────────────────>│
     │                       │                         │
     │  4. Confirmation      │                         │
     │<──────────────────────┤                         │
     │                       │                         │
```

## Password Security

### Hashing Algorithm

The system uses bcrypt for password hashing (`src/education_system/platform/identity/auth/password_manager.py`):

```python
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
```

### Password Verification

Legacy PBKDF2-SHA256 hashes from migrated university accounts are still verified when a legacy salt is present.

```python
def verify_password(password: str, password_hash: str, legacy_salt: str | None = None) -> bool:
    """Verify a password against its hash.

    Supports bcrypt (default) and legacy PBKDF2-SHA256 hashes for migrated
    university accounts.  When *legacy_salt* is provided the hash is treated
    as a PBKDF2 hex digest; otherwise bcrypt verification is used.

    Returns True if the password matches, False otherwise.
    """
    if legacy_salt:
        return _verify_pbkdf2_legacy(password, legacy_salt, password_hash)
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        # Run dummy comparison to prevent timing oracle
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))
        return False
```

### Password Requirements

Default password requirements, with `MIN_PASSWORD_LENGTH = 12` in `src/education_system/platform/identity/auth/defaults.py`:

```python
def validate_password_strength(password: str) -> tuple[bool, str]:
    """Check password meets minimum strength requirements.

    Returns (is_valid, message).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."

    if password.lower() in _COMMON_PASSWORDS:
        return False, "Password is too common. Please choose a more unique password."

    return True, "Password meets requirements."
```

## Session Management

Sessions are held in the `sessions` table of `auth.db` and managed by `SessionManager` in `src/education_system/platform/identity/auth/session_manager.py`.

### Session Creation

```python
from education_system.platform.identity.auth.session_manager import SessionManager

sessions = SessionManager()

# Returns a secure random token. At most MAX_SESSIONS_PER_USER sessions stay
# active; the oldest is revoked to make room for a new one.
token = sessions.create_session(user_id)
```

### Session Validation

```python
# Returns a dict if the token is valid, None if invalid or expired.
# Pass system_key to also check the user's access to that system.
session = sessions.validate_session(token, system_key="university")
```

### Session Timeout

`SESSION_TIMEOUT_MINUTES` defaults to 30 and can be overridden with the `EDU_SESSION_TIMEOUT` environment variable. `MAX_SESSIONS_PER_USER` defaults to 5 (`EDU_MAX_SESSIONS`). Both are in `src/education_system/platform/identity/auth/defaults.py`.

### Session Cleanup

```python
sessions.invalidate_session(token)            # One session
sessions.invalidate_user_sessions(user_id)    # All of a user's sessions
sessions.cleanup_expired()                    # Remove expired sessions
```

## Authorization

### Permission System

Permissions are named strings. Each role's list is defined in `PERMISSIONS` in `src/education_system/systems/university/infrastructure/auth/core_utils/constants.py`:

```python
PERMISSIONS: Dict[str, List[str]] = {
    'admin': [
        'access_academic_support', 'access_ai_detector', 'add_module', 'add_student',
        # ...
    ],
    'instructor': [...],
    'staff': [...],
    'student': [...],
    # ...
}
```

### Role Definitions

```python
# src/education_system/systems/university/infrastructure/auth/core_utils/constants.py
ROLES: Dict[str, str] = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records',
    # ...
}
```

### Permission Checking

The university `UserAuth` checks the signed-in user's permissions:

```python
auth.has_permission('add_student')                          # True or False
auth.check_permission('add_student', raise_exception=True)  # Raises if not allowed
auth.get_user_permissions(user_id)                          # All of a user's permissions
```

### Permission Decorator

```python
from functools import wraps
from education_system.systems.university.infrastructure.exceptions import PermissionDeniedError

def require_permission(permission: str):
    """
    Decorator to require a specific permission.

    Usage:
        @require_permission('add_module')
        def create_course(auth, course_data):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract the auth instance from arguments
            auth = kwargs.get('auth') or args[0]

            if not auth.has_permission(permission):
                raise PermissionDeniedError(resource=permission)

            return func(*args, **kwargs)
        return wrapper
    return decorator
```

## Role-Based Access Control

### User Roles

| Role       | Access Level | Description                              |
|------------|-------------|------------------------------------------|
| Admin      | Full        | Complete system access                   |
| Instructor | High        | Assigned modules and student grades      |
| Staff      | Medium      | Student records and reports              |
| Student    | Limited     | Own records only                         |
| Parent     | Limited     | Their children's records                 |

The full list, including the health roles, is `ROLES` in `core_utils/constants.py`.

### Role Assignment

Roles are held in `auth.db` and managed by `RoleManager` in `src/education_system/platform/identity/auth/role_manager.py`, and by the university's `src/education_system/systems/university/infrastructure/auth/managers/role_manager.py`.

## Implementation Examples

### CLI Authentication

```python
# src/education_system/launcher/auth.py
from education_system.launcher.auth import cli_universal_login

# Returns (user_info, system_key, system_role, auth), or None if cancelled
result = cli_universal_login(target_system="university")
```

The prompt itself is in `src/education_system/platform/delivery/cli/login_cli.py`.

### GUI Authentication

```python
# src/education_system/launcher/auth.py
from education_system.launcher.auth import gui_universal_login

# Shows UniversalLoginWindow and returns (user_info, system_key, system_role, auth),
# or None if cancelled
result = gui_universal_login(target_system="university")
```

The window itself is in `src/education_system/platform/delivery/gui/login_gui.py`.

### Direct Sign-In

```python
from education_system.platform.identity.auth.core import UserAuth

auth = UserAuth()

# Returns a user info dict on success. Raises AuthError on failure.
user_info = auth.login(username, password)
```

### Web API Authentication

The API's sign-in routes are in `src/education_system/platform/delivery/api/routes/auth_routes.py`. Principals and bearer-token handling are in `src/education_system/platform/delivery/api/security/principals.py`, with the route decorators in `src/education_system/platform/delivery/api/security/decorators.py`.

## Security Features

### Account Lockout

Protect against brute force attacks. The limits are in `src/education_system/platform/identity/auth/defaults.py`, and `UserAuth.login` in `core.py` applies them:

```python
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION_MINUTES = 15
```

### Audit Logging

Authentication events are written to the `security_audit_log` table in `auth.db`:

```sql
CREATE TABLE IF NOT EXISTS security_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    NOT NULL,
    username    TEXT,
    user_id     INTEGER,
    detail      TEXT,
    ip_address  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

## API Reference

### Core Functions

#### `UserAuth.login(username, password)`

Authenticate a user against the shared auth database (`education_system.platform.identity.auth.core`).

**Parameters:**
- `username` (str): Username
- `password` (str): Password (plaintext, verified against the stored hash)

**Returns:**
- `dict`: User info, including the systems the user can access

**Raises:**
- `AuthError`: If sign-in fails, including when the account is locked

#### `SessionManager.create_session(user_id)`

Create a new session for a user (`education_system.platform.identity.auth.session_manager`).

**Parameters:**
- `user_id` (int): User ID

**Returns:**
- `str`: Session token

#### `SessionManager.validate_session(token, system_key=None)`

Validate a session token.

**Parameters:**
- `token` (str): Session token to validate
- `system_key` (str, optional): System to check access against

**Returns:**
- `dict`: Session info if valid, None if invalid

#### `SessionManager.invalidate_session(token)`

Invalidate a session.

**Parameters:**
- `token` (str): Session token to invalidate

#### `has_permission(permission)`

Method of the university `UserAuth`. Check if the current user has a specific permission.

**Parameters:**
- `permission` (str): Permission string

**Returns:**
- `bool`: True if user has permission

## Troubleshooting

### Common Issues

**Account Locked**
```
Error: "Account is locked until YYYY-MM-DD HH:MM:SS"

Solution:
1. Wait for lockout period to expire, or
2. Sign in as the system admin and clear the lockout from the admin panel
```

**Session Expired**
```
Error: "Session expired or invalid"

Solution:
1. User must log in again
2. Increase EDU_SESSION_TIMEOUT if sessions expire too quickly
3. Check for clock synchronization issues
```

**Permission Denied**
```
Error: "User does not have permission: add_module"

Solution:
1. Check user role
2. Verify role has required permission in PERMISSIONS definition
3. Assign appropriate role if needed
```

### Debug Mode

Enable debug logging for the auth loggers:

```python
import logging

logging.getLogger("education_system.platform.identity.auth").setLevel(logging.DEBUG)
```

## Best Practices

1. **Never Log Passwords**: Never log plaintext passwords or hashes
2. **Use HTTPS**: Always use HTTPS in production for web interfaces
3. **Secure Session Tokens**: Treat session tokens like passwords
4. **Regular Session Cleanup**: Clean up expired sessions regularly
5. **Monitor Failed Logins**: Alert on suspicious login patterns
6. **Strong Passwords**: Enforce password complexity requirements
7. **Multi-Factor Authentication**: Consider implementing 2FA for sensitive accounts
8. **Regular Audits**: Review audit logs regularly

## References

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [NIST Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)
- [PBKDF2 Specification](https://tools.ietf.org/html/rfc2898) (legacy hashes only)

---

For questions or issues, contact the development team or see [SECURITY.md](../../../SECURITY.md).
