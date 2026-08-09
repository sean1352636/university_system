# Authentication System

This document describes the authentication, session management, and access control infrastructure for the Sixth Form College Management System.

Source files:

- `infrastructure/auth/core.py` -- `UserAuth` facade class
- `infrastructure/auth/password_manager.py` -- bcrypt hashing and password validation
- `infrastructure/auth/session_manager.py` -- token-based session management
- `infrastructure/auth/role_manager.py` -- role hierarchy and RBAC
- `infrastructure/auth/mfa_service.py` -- TOTP multi-factor authentication
- `api/auth.py` -- JWT token generation and API decorators

---

## Architecture

The authentication system is composed of several focused components, brought together by the `UserAuth` facade:

```
UserAuth (core.py)
  |-- PasswordManager (password_manager.py)   -- hashing, verification, strength rules
  |-- SessionManager  (session_manager.py)    -- CLI/GUI session tokens
  |-- RoleManager     (role_manager.py)       -- RBAC with hierarchical roles
  |-- MFAService      (mfa_service.py)        -- TOTP setup and verification

API layer (api/auth.py)
  |-- JWT generation and decoding
  |-- @token_required decorator
  |-- @role_required decorator
  |-- @mfa_token_required decorator
```

`UserAuth` is used for GUI/CLI authentication and maintains current-user state in memory. The API layer uses stateless JWT tokens and Flask decorators.


---

## UserAuth Facade

`UserAuth` is instantiated with an optional `db_path` and composes a `SessionManager` and `RoleManager` internally. It tracks the currently logged-in user and their session token as instance state.

### Key Properties

| Property | Type | Description |
|---|---|---|
| `current_user` | `dict or None` | The logged-in user's info (`user_id`, `username`, `role`, `email`) |
| `is_logged_in` | `bool` | Whether a user is currently authenticated |

### Key Methods

| Method | Description |
|---|---|
| `login(username, password)` | Authenticate credentials, create session, return user dict |
| `verify_mfa(user_id, code)` | Complete login after MFA challenge |
| `logout()` | Invalidate session and clear current user |
| `create_user(username, password, role, email)` | Create a new user account |
| `change_password(user_id, old_password, new_password)` | Change password with old-password verification |
| `check_permission(resource, action)` | Check if current user has a specific permission |
| `require_permission(resource, action)` | Raise `AuthError` if permission is missing |
| `require_role(required_role)` | Raise `AuthError` if user's role level is insufficient |
| `get_user_by_id(user_id)` | Look up user info by ID |


---

## Login Flow

### Standard Login (No MFA)

1. **Lookup:** Query the `users` table by username. If not found, raise `AuthError`.
2. **Active check:** If `is_active = 0`, raise `AuthError` ("Account is deactivated").
3. **Lockout check:** If `locked_until` is set and in the future, reject the attempt. If the lockout has expired, reset `failed_login_attempts` and `locked_until`.
4. **Password verification:** Call `verify_password()` to compare the plaintext input against the stored bcrypt hash.
   - On failure: increment `failed_login_attempts`. If attempts reach 5, set `locked_until` to 15 minutes from now. Raise `AuthError`.
   - On success: reset `failed_login_attempts` to 0 and clear `locked_until`.
5. **MFA check:** If the user has MFA enabled (row exists in `mfa_secrets` with `is_enabled = 1`), return a partial result with `mfa_required: True` instead of completing login.
6. **Session creation:** Generate a cryptographic token via `SessionManager.create_session()` and store it in the `sessions` table.
7. **Return:** Set `_current_user` and `_current_token` on the `UserAuth` instance. Return the user info dict.

### MFA Login

When `login()` returns `mfa_required: True`, the caller must collect a TOTP code and call `verify_mfa(user_id, code)`:

1. Attempt TOTP verification first.
2. If TOTP fails, attempt recovery code verification.
3. If both fail, raise `AuthError`.
4. On success, create a session and return the full user dict.


---

## Password Management

Implemented in `password_manager.py` using the `bcrypt` library.

### Hashing

Passwords are hashed with `bcrypt.hashpw()` using a randomly generated salt (`bcrypt.gensalt()`). The hash is stored as a UTF-8 string in the `password_hash` column.

### Verification

`verify_password(password, password_hash)` uses `bcrypt.checkpw()` to compare a plaintext password against a stored hash. Returns `False` (rather than raising) on malformed hashes.

### Password Strength Rules

`validate_password_strength()` enforces the following requirements. It returns a `(bool, str)` tuple indicating validity and a descriptive message.

| Rule | Requirement |
|---|---|
| Minimum length | 8 characters (configurable via `MIN_PASSWORD_LENGTH`) |
| Uppercase letter | At least one `A-Z` |
| Lowercase letter | At least one `a-z` |
| Digit | At least one `0-9` |
| Special character | At least one of `!@#$%^&*(),.?":{}|<>` |

Password strength is validated both during `create_user()` and `change_password()`.

### Account Lockout

After 5 consecutive failed login attempts (`MAX_LOGIN_ATTEMPTS`), the account is locked for 15 minutes by setting the `locked_until` timestamp in the `users` table. The lockout resets automatically after the period expires or on a successful login.


---

## Session Management

Implemented in `session_manager.py`. Sessions are used for GUI/CLI authentication.

### Token Creation

`create_session(user_id)` generates a 32-byte URL-safe token using `secrets.token_urlsafe(32)`, calculates an expiry time (default 30 minutes from creation), and stores both in the `sessions` table.

### Token Validation

`validate_session(token)` performs:

1. Query `sessions` joined with `users` where `token` matches and `is_active = 1`.
2. Check if `expires_at` is in the future.
3. If expired, mark the session inactive and return `None`.
4. If valid, return `{"user_id", "username", "role"}`.

### Session Invalidation

| Method | Scope |
|---|---|
| `invalidate_session(token)` | Deactivates a single session |
| `invalidate_user_sessions(user_id)` | Deactivates all sessions for a user |

`invalidate_user_sessions()` is called during password changes to force re-authentication across all devices.

### Cleanup

`cleanup_expired()` deletes all sessions that are past their expiry time or already marked inactive.


---

## Role-Based Access Control

Implemented in `role_manager.py`.

### Role Hierarchy

Roles are ordered by a numeric level. Higher levels inherit more authority:

| Role | Level | Description |
|---|---|---|
| `admin` | 100 | System administrator -- implicitly has all permissions |
| `staff` | 75 | Staff member |
| `instructor` | 50 | Course instructor |
| `teacher` | 50 | Subject teacher (same level as instructor) |
| `parent` | 30 | Parent/Guardian |
| `student` | 25 | Student |

### Permission Model

Permissions are stored in the `permissions` table as `(role_id, resource, action)` tuples. Resources and actions are strings (e.g., resource = `"grades"`, action = `"update"`).

**Admin bypass:** The `admin` role always returns `True` for `has_permission()` without checking the database.

### Permission Checks

| Method | Description |
|---|---|
| `has_permission(role, resource, action)` | Check if a specific role has a permission |
| `has_minimum_role(user_role, required_role)` | Check if user's role level meets or exceeds a threshold |
| `get_permissions(role)` | List all permissions for a role |
| `assign_role(user_id, role)` | Change a user's role |

### Default Permissions (Seeded)

**Admin:** Full CRUD on `users`, `students`, `courses`, `enrollments`, `grades`, `attendance`.

**Instructor / Teacher:** Read `students`, `courses`, `enrollments`. Create/read/update `grades` and `attendance`. Update `courses`.

**Student:** Read-only access to `students`, `courses`, `enrollments`, `grades`, `attendance`.


---

## Multi-Factor Authentication (MFA)

Implemented in `mfa_service.py` using the `pyotp` library for TOTP.

### Setup

`setup_totp(user_id, username)` performs:

1. Remove any existing MFA configuration for the user.
2. Generate a random Base32 TOTP secret via `pyotp.random_base32()`.
3. Create a provisioning URI for authenticator apps (issuer: "College Management System").
4. Store the secret in `mfa_secrets` with `is_enabled = 1`.
5. Generate 10 recovery codes in `XXXX-XXXX` format (uppercase alphanumeric).
6. Store SHA-256 hashes of the recovery codes in `mfa_recovery_codes`.
7. Return `{"secret", "provisioning_uri", "recovery_codes"}`.

The provisioning URI can be encoded as a QR code for scanning by apps such as Google Authenticator or Authy.

### TOTP Verification

`verify_totp(user_id, code)` validates a 6-digit TOTP code with a 1-step window tolerance (accepts codes from the previous, current, and next 30-second interval).

### Recovery Codes

- 10 codes are generated during setup.
- Codes are stored as SHA-256 hashes (the plaintext is shown to the user once and never stored).
- `verify_recovery_code()` hashes the input, checks against unused codes, and marks the code as used on success.
- `get_remaining_recovery_codes()` returns the count of unused codes.

### Disabling MFA

`disable_mfa(user_id)` removes both the TOTP secret and all recovery codes from the database.


---

## API Token Authentication

The REST API uses JWT tokens rather than session tokens. This layer is implemented in `api/auth.py`.

### JWT Token Generation

`generate_token(user_id, username, role)` creates a JWT with:

| Claim | Value |
|---|---|
| `user_id` | The user's database ID |
| `username` | The username string |
| `role` | The user's role |
| `exp` | Expiry timestamp (default 24 hours from issuance) |
| `iat` | Issued-at timestamp |

The token is signed with HS256 using the secret from `Config.JWT_SECRET_KEY` (sourced from `core/defaults.py`, overridable via the `COLLEGE_JWT_SECRET` environment variable).

### `@token_required` Decorator

Applied to Flask route functions. Behavior:

1. Extract the token from the `Authorization: Bearer <token>` header.
2. If missing, return 401 with `{"error": "Authentication required"}`.
3. Decode the JWT. On `ExpiredSignatureError`, return 401. On `InvalidTokenError`, return 401.
4. On success, populate `g.current_user` with `{"user_id", "username", "role"}` and proceed to the route handler.

### `@role_required(*roles)` Decorator

Applied after `@token_required`. Checks that `g.current_user["role"]` is in the provided list of allowed roles. Returns 403 if the role does not match.

Usage:

```python
@app.route("/api/admin/users")
@token_required
@role_required("admin")
def list_users():
    ...
```

### `@mfa_token_required` Decorator

Used for the MFA verification endpoint. Validates a short-lived JWT (5-minute expiry) that contains `"purpose": "mfa_verify"` and a `user_id`. This token is issued by `_create_mfa_token()` when login detects that MFA is required, and is consumed by the MFA verification route.

### API Authentication Flow

1. Client sends `POST /api/auth/login` with `{"username", "password"}`.
2. If MFA is not required, the response includes a JWT access token.
3. If MFA is required, the response includes a short-lived MFA token. The client sends `POST /api/auth/verify-mfa` with the MFA token and a TOTP code to receive the full JWT access token.
4. Subsequent requests include `Authorization: Bearer <jwt_token>`.
