# Authentication System

This document describes the authentication, session management, and access control infrastructure for the Sixth Form College Management System. Authentication is shared across all seven systems through the central `var/data/platform/db_files/auth.db`.

Source files:

- `src/education_system/platform/identity/auth/core.py` -- `UserAuth` facade class
- `src/education_system/platform/identity/auth/password_manager.py` -- bcrypt hashing and password validation
- `src/education_system/platform/identity/auth/session_manager.py` -- token-based session management
- `src/education_system/platform/identity/auth/role_manager.py` -- role hierarchy and per-system roles
- `src/education_system/systems/sixth_form/domain/governance/user_management/access.py` -- sixth form capabilities
- `src/education_system/platform/identity/auth/mfa_service.py` -- TOTP multi-factor authentication
- `src/education_system/platform/delivery/api/security/authentication.py` -- JWT token generation and API decorators
- `src/education_system/platform/delivery/api/routes/auth_routes.py` -- login, MFA and related routes

---

## Architecture

The authentication system is composed of several focused components, brought together by the `UserAuth` facade:

```
UserAuth (core.py)
  |-- password_manager.py                     -- hashing, verification, strength rules
  |-- SessionManager  (session_manager.py)    -- CLI/GUI session tokens
  |-- RoleManager     (role_manager.py)       -- RBAC with hierarchical roles
  |-- MFAService      (mfa_service.py)        -- TOTP setup and verification

API layer (security/authentication.py)
  |-- JWT generation and decoding
  |-- @token_required decorator
  |-- @role_required decorator
  |-- @system_required decorator
```

`UserAuth` is used for GUI/CLI authentication and maintains current-user state in memory. The API layer uses stateless JWT tokens and Flask decorators.


---

## UserAuth Facade

`UserAuth` is instantiated with an optional `db_path` and composes a `SessionManager` and `RoleManager` internally. It tracks the currently logged-in user and their session token as instance state.

### Key Properties

| Property | Type | Description |
|---|---|---|
| `current_user` | `dict or None` | The logged-in user's info, including `user_id`, `username` and `systems` |
| `is_logged_in` | `bool` | Whether a user is currently authenticated |

### Key Methods

| Method | Description |
|---|---|
| `login(username, password)` | Authenticate credentials, create session, return user dict |
| `verify_mfa(user_id, code)` | Complete login after MFA challenge |
| `logout()` | Invalidate session and clear current user |
| `create_user(...)` | Create a new user account |
| `change_password(user_id, old_password, new_password)` | Change password with old-password verification |
| `get_role_for_system(system_key)` | The current user's role in one system |
| `get_user_by_id(user_id)` | Look up user info by ID |


---

## Login Flow

### Standard Login (No MFA)

1. **Lookup:** Query the `users` table by username. If not found, raise `AuthError`.
2. **Active check:** If `is_active = 0`, raise the same generic `AuthError`, so a deactivated account cannot be told apart from a wrong username.
3. **Lockout check:** If `locked_until` is set and in the future, reject the attempt. If the lockout has expired, reset `failed_login_attempts` and `locked_until`.
4. **Password verification:** Call `verify_password()` to compare the plaintext input against the stored bcrypt hash.
   - On failure: increment `failed_login_attempts`. If attempts reach 3, set `locked_until` to 15 minutes from now. Raise `AuthError`.
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

Implemented in `password_manager.py` using the `bcrypt` library. Passwords in the older PBKDF2 format still verify, and are re-hashed with bcrypt on login.

### Hashing

Passwords are hashed with `bcrypt.hashpw()` using a randomly generated salt (`bcrypt.gensalt()`). The hash is stored as a UTF-8 string in the `password_hash` column.

### Verification

`verify_password(password, password_hash)` uses `bcrypt.checkpw()` to compare a plaintext password against a stored hash. Returns `False` (rather than raising) on malformed hashes.

### Password Strength Rules

`validate_password_strength()` enforces the following requirements. It returns a `(bool, str)` tuple indicating validity and a descriptive message.

| Rule | Requirement |
|---|---|
| Minimum length | 12 characters (`MIN_PASSWORD_LENGTH` in `platform/identity/auth/defaults.py`) |
| Uppercase letter | At least one `A-Z` |
| Lowercase letter | At least one `a-z` |
| Digit | At least one `0-9` |
| Special character | At least one of `!@#$%^&*(),.?":{}|<>` |
| Not common | Must not be on the common-passwords list |

Password strength is validated both during `create_user()` and `change_password()`.

### Account Lockout

After 3 consecutive failed login attempts (`MAX_LOGIN_ATTEMPTS`), the account is locked for 15 minutes (`LOCKOUT_DURATION_MINUTES`) by setting the `locked_until` timestamp in the `users` table. The lockout resets automatically after the period expires or on a successful login.


---

## Session Management

Implemented in `session_manager.py`. Sessions are used for GUI/CLI authentication.

### Token Creation

`create_session(user_id)` generates a 32-byte URL-safe token using `secrets.token_urlsafe(32)`, calculates an expiry time (default 30 minutes from creation, `EDU_SESSION_TIMEOUT`), and stores both in the `sessions` table. It keeps at most `EDU_MAX_SESSIONS` sessions per user (default 5), revoking the oldest.

### Token Validation

`validate_session(token)` performs:

1. Query `sessions` joined with `users` where `token` matches and `is_active = 1`.
2. Check if `expires_at` is in the future.
3. If expired, mark the session inactive and return `None`.
4. If valid, return the session's user details.

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

Roles are implemented in `role_manager.py`, and sixth form capabilities in `domain/governance/user_management/access.py`.

### Role Hierarchy

Roles are ordered by a numeric level in `ROLE_HIERARCHY`. Higher levels inherit more authority. These are the levels the sixth form uses most:

| Role | Level | Description |
|---|---|---|
| `admin` | 100 | System administrator |
| `staff` | 75 | Staff member |
| `instructor` | 50 | Course instructor |
| `teacher` | 50 | Subject teacher (same level as instructor) |

A user's role is held per system in the `user_systems` table, so one account can have different roles in different systems. `superadmin` is admin across all seven.

### Permission Model

The sixth form resolves a `Principal` once per session (GUI/CLI) or request (API), carrying a set of *capabilities*. Capabilities come from:

1. the shared-auth role for `sixth_form` (admin gets everything);
2. the linked `staff` record's job role and designations (DSL, SENCO, exams officer, finance officer and so on);
3. per-user grant or revoke overrides, set in User Management.

**Safeguarding:** Role defaults never grant it. It comes only from admin, a DSL or deputy DSL designation, or an explicit per-user grant.

### Permission Checks

| Method | Description |
|---|---|
| `RoleManager.has_minimum_role(user_role, required_role)` | Check if user's role level meets or exceeds a threshold |
| `RoleManager.get_user_role_for_system(user_id, system_key)` | The user's role in one system |
| `RoleManager.grant_system_access(user_id, system_key, role)` | Set a user's role in a system |
| `access.capabilities_for(role, ...)` | The capabilities for a role and job |
| `access.current()` | The principal bound to the current session or request |

### Menu and Route Access

**Menus:** Every menu label maps to one capability in `MENU_CAPABILITIES`. A label missing from the map is admin-only.

**Routes:** `RULES` in `src/education_system/api/sixth_form/access_gate.py` gives each route a read and a write capability. A route without a rule is refused. Students get through only on rules that name an owner, and only for their own record.


---

## Multi-Factor Authentication (MFA)

Implemented in `mfa_service.py` using the `pyotp` library for TOTP.

### Setup

`setup_totp(user_id, username)` performs:

1. Remove any existing MFA configuration for the user.
2. Generate a random Base32 TOTP secret via `pyotp.random_base32()`.
3. Create a provisioning URI for authenticator apps (issuer: "Education System").
4. Store the secret in `mfa_secrets` with `is_enabled = 1`.
5. Generate 10 recovery codes in `XXXX-XXXX` format (uppercase alphanumeric).
6. Store bcrypt hashes of the recovery codes in `mfa_recovery_codes`.
7. Return `{"secret", "provisioning_uri", "recovery_codes"}`.

The provisioning URI can be encoded as a QR code for scanning by apps such as Google Authenticator or Authy.

### TOTP Verification

`verify_totp(user_id, code)` validates a 6-digit TOTP code with a 1-step window tolerance (accepts codes from the previous, current, and next 30-second interval).

### Recovery Codes

- 10 codes are generated during setup.
- Codes are stored as bcrypt hashes; older SHA-256 hashes still verify (the plaintext is shown to the user once and never stored).
- `verify_recovery_code()` checks the input against unused codes, and marks the code as used on success.
- `get_remaining_recovery_codes()` returns the count of unused codes.

### Disabling MFA

`disable_mfa(user_id)` removes both the TOTP secret and all recovery codes from the database.


---

## API Token Authentication

The REST API uses JWT tokens rather than session tokens. This layer is implemented in `platform/delivery/api/security/authentication.py`.

### JWT Token Generation

`generate_token(user_id, username, systems, token_type)` creates a JWT with:

| Claim | Value |
|---|---|
| `user_id` | The user's database ID |
| `username` | The username string |
| `systems` | The user's systems and their role in each |
| `type` | `access` or `refresh` |
| `exp` | Expiry timestamp (access: default 24 hours from issuance; refresh: 7 days) |
| `iat` | Issued-at timestamp |

The token is signed with HS256 using the secret from the `JWT_SECRET_KEY` environment variable. Production deployments must set it.

### `@token_required` Decorator

Applied to Flask route functions. Behavior:

1. Extract the token from the `Authorization: Bearer <token>` header.
2. If missing, return 401 with `{"error": "Authentication required"}`.
3. Decode the JWT. On `ExpiredSignatureError`, return 401. On `InvalidTokenError`, return 401.
4. Re-read the user from the auth database, and return 401 if the account is no longer active.
5. On success, populate `g.current_user` with `user_id`, `username`, `systems` and `role`, and proceed to the route handler. The role is the user's role in the system named in the URL, and a user with no access to that system gets a 403.

### `@role_required(*roles)` Decorator

Applied after `@token_required`. Checks that `g.current_user["role"]` is in the provided list of allowed roles. Returns 403 if the role does not match.

Usage:

```python
@app.route("/api/v1/admin/users")
@token_required
@role_required("admin")
def list_users():
    ...
```

### MFA Token

The MFA verification route validates a short-lived JWT (5-minute expiry) that contains `"purpose": "mfa_verify"` and a `user_id`. This token is issued by `_create_mfa_token()` when login detects that MFA is required.

### API Authentication Flow

1. Client sends `POST /api/v1/auth/login` with `{"username", "password"}`.
2. If MFA is not required, the response includes a JWT access token.
3. If MFA is required, the response includes a short-lived MFA token. The client sends `POST /api/v1/auth/mfa/verify` with the MFA token and a TOTP code to receive the full JWT access token.
4. Subsequent requests include `Authorization: Bearer <jwt_token>`.
