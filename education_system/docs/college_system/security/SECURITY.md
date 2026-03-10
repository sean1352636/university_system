# College System Security Documentation

This document describes the security architecture, mechanisms, and best practices for the Sixth Form College Management System. All details are based on the actual implementation in the codebase.

---

## Table of Contents

1. [Security Architecture Overview](#security-architecture-overview)
2. [Authentication](#authentication)
3. [Authorization](#authorization)
4. [API Security](#api-security)
5. [Audit Logging](#audit-logging)
6. [Data Protection](#data-protection)
7. [Session Security](#session-security)
8. [Best Practices and Production Recommendations](#best-practices-and-production-recommendations)

---

## Security Architecture Overview

The college system implements a layered security architecture with the following components:

- **Authentication layer** -- Password-based login with bcrypt hashing, account lockout, and optional TOTP-based multi-factor authentication.
- **Session management** -- Cryptographically random session tokens for the GUI/CLI interface and JWT tokens for the REST API.
- **Authorization layer** -- Role-Based Access Control (RBAC) with a hierarchical role model and granular resource-action permissions.
- **Input validation** -- Centralized validation utilities that enforce format constraints on all user-supplied data.
- **Audit logging** -- Persistent audit trail of security-relevant events stored in the database.
- **Data protection** -- Parameterized SQL queries throughout to prevent injection attacks; input sanitization on all entry points.

Key source files:

| Component | Location |
|---|---|
| Core auth facade | `infrastructure/auth/core.py` |
| Password hashing | `infrastructure/auth/password_manager.py` |
| Session management | `infrastructure/auth/session_manager.py` |
| Role management | `infrastructure/auth/role_manager.py` |
| MFA service | `infrastructure/auth/mfa_service.py` |
| API JWT auth | `api/auth.py` |
| Audit logging | `infrastructure/security/audit.py` |
| Input validation | `infrastructure/validation/validators.py` |
| Default constants | `core/defaults.py` |

---

## Authentication

### Password Hashing

Passwords are hashed using **bcrypt** via the `bcrypt` Python library. The implementation is in `infrastructure/auth/password_manager.py`.

- `hash_password(password)` -- Generates a bcrypt hash with an automatically generated salt (`bcrypt.gensalt()`).
- `verify_password(password, password_hash)` -- Verifies a plaintext password against a stored bcrypt hash using `bcrypt.checkpw()`.
- Passwords are encoded as UTF-8 before hashing.
- Verification failures (including malformed hashes) return `False` rather than raising exceptions.

### Password Strength Requirements

The `validate_password_strength()` function enforces the following rules before any password is accepted (during account creation or password change):

| Requirement | Detail |
|---|---|
| Minimum length | 8 characters (configurable via `MIN_PASSWORD_LENGTH`) |
| Uppercase letter | At least one `A-Z` character |
| Lowercase letter | At least one `a-z` character |
| Digit | At least one `0-9` character |
| Special character | At least one of `!@#$%^&*(),.?":{}|<>` |

If any requirement is not met, an error message is returned describing the specific failure.

### Account Lockout

The system implements automatic account lockout to defend against brute-force attacks.

- **Maximum attempts:** 5 failed login attempts (configurable via `MAX_LOGIN_ATTEMPTS` in `core/defaults.py`).
- **Lockout duration:** 15 minutes from the time the threshold is reached.
- **Lockout check:** On every login attempt, the system checks the `locked_until` timestamp. If the current time is before that timestamp, the login is rejected with "Account locked due to too many failed attempts."
- **Automatic reset:** Once the lockout period expires, the next login attempt resets the `failed_login_attempts` counter and clears the `locked_until` timestamp.
- **Successful login:** Immediately resets `failed_login_attempts` to 0 and clears `locked_until`.
- **Deactivated accounts:** Accounts with `is_active = 0` are rejected before any password check.

### Login Flow

1. Look up the user by username using a parameterized query.
2. If user not found, raise `AuthError("Invalid username or password.")` -- generic message to avoid username enumeration.
3. If account is deactivated (`is_active = 0`), reject the attempt.
4. If account is locked and lockout has not expired, reject the attempt.
5. If lockout has expired, reset the counter.
6. Verify the password against the stored bcrypt hash.
7. On password failure, increment `failed_login_attempts`; if threshold is reached, set `locked_until` to 15 minutes from now.
8. On password success, reset failure counters.
9. Check if MFA is enabled for the user. If so, return `{"mfa_required": True, ...}` and await MFA verification.
10. If MFA is not required, create a session token and return user information.

### Multi-Factor Authentication

See [MFA_GUIDE.md](MFA_GUIDE.md) for detailed MFA documentation. Summary:

- TOTP-based MFA using the `pyotp` library.
- 10 single-use recovery codes generated at setup time (format: `XXXX-XXXX`).
- TOTP verification allows a 1-step time window tolerance.
- Recovery codes are stored as SHA-256 hashes and marked as used after consumption.

---

## Authorization

### Role-Based Access Control (RBAC)

Authorization is managed by the `RoleManager` class in `infrastructure/auth/role_manager.py`.

#### Role Hierarchy

Roles are organized in a numeric hierarchy. A higher level grants broader access:

| Role | Level |
|---|---|
| `admin` | 100 |
| `staff` | 75 |
| `instructor` | 50 |
| `teacher` | 50 |
| `parent` | 30 |
| `student` | 25 |

- `instructor` and `teacher` are treated at the same hierarchy level.
- Unknown roles default to level 0.

#### Permission Model

Permissions are stored in the database using a `permissions` table linked to a `roles` table. Each permission is a `(resource, action)` pair.

- **Admin bypass:** The `admin` role always returns `True` for any permission check, bypassing the database lookup entirely.
- **has_permission(role, resource, action):** Checks the database for a matching permission entry for the given role.
- **has_minimum_role(user_role, required_role):** Compares hierarchy levels to determine if a user meets the minimum role requirement.
- **get_permissions(role):** Returns all `(resource, action)` pairs assigned to a role.

#### Enforcement Methods

The `UserAuth` facade in `infrastructure/auth/core.py` provides two enforcement methods:

- `check_permission(resource, action)` -- Returns `True`/`False` for the current user.
- `require_permission(resource, action)` -- Raises `AuthError("Access denied. Insufficient permissions.")` if the check fails.
- `require_role(required_role)` -- Raises `AuthError("Access denied. Insufficient role level.")` if the current user's role level is below the required role level.

#### API Decorators

The API layer (`api/auth.py`) provides decorator-based authorization:

- `@token_required` -- Requires a valid JWT token in the `Authorization: Bearer <token>` header. Populates `g.current_user` with `user_id`, `username`, and `role`.
- `@role_required(*roles)` -- Must be used after `@token_required`. Checks that `g.current_user["role"]` is in the specified set of roles. Returns HTTP 403 if the role does not match.

Example usage:

```python
@app.route("/api/admin/users")
@token_required
@role_required("admin", "staff")
def list_users():
    ...
```

---

## API Security

### JWT Tokens

The REST API uses JSON Web Tokens (JWT) for stateless authentication, implemented in `api/auth.py`.

- **Algorithm:** HS256 (HMAC with SHA-256).
- **Secret key:** Configured via `Config.JWT_SECRET_KEY` (sourced from environment or config).
- **Token expiry:** 24 hours by default (`JWT_EXPIRY_HOURS`, configurable via `COLLEGE_JWT_EXPIRY` environment variable).
- **Token payload:** Contains `user_id`, `username`, `role`, `exp` (expiration), and `iat` (issued at).
- **Token transmission:** Sent in the `Authorization` header using the `Bearer` scheme.

Token generation:

```python
token = generate_token(user_id, username, role)
```

Token validation handles two error cases:

| Error | HTTP Status | Message |
|---|---|---|
| `jwt.ExpiredSignatureError` | 401 | "Token expired. Please log in again." |
| `jwt.InvalidTokenError` | 401 | "Token is invalid." |

#### MFA Tokens

When MFA is required during login, a short-lived MFA token is issued:

- **Purpose:** Carries the `user_id` and a `purpose: "mfa_verify"` claim.
- **Expiry:** 5 minutes.
- **Validation:** The `@mfa_token_required` decorator verifies the token and checks that the `purpose` field equals `"mfa_verify"`. This prevents regular session tokens from being used for MFA verification.

### CORS

Cross-Origin Resource Sharing is enabled using `flask-cors`. The `CORS(app)` call in `api/api_server.py` applies default permissive CORS settings. For production, this should be restricted to specific allowed origins.

### Input Validation

The `infrastructure/validation/validators.py` module provides validation functions used across the system:

| Validator | Purpose |
|---|---|
| `validate_email(email)` | Regex-based email format validation; normalizes to lowercase |
| `validate_student_id(student_id)` | Enforces `SFC0001` format |
| `validate_year_group(year_group)` | Validates against allowed year groups |
| `validate_term(term)` | Validates against allowed terms (Autumn, Spring, Summer) |
| `validate_qualification_type(qual_type)` | Validates against allowed qualification types |
| `validate_alevel_grade(grade)` | Validates against the A-Level grade scale |
| `validate_course_code(code)` | Enforces `CS101` / `MATH201` format |
| `validate_date(date_str)` | Validates date format (default `YYYY-MM-DD`) |
| `validate_grade_score(score)` | Ensures score is a float between 0 and 100 |
| `validate_non_empty(value, field_name)` | Rejects empty or whitespace-only strings |
| `validate_positive_int(value, field_name)` | Ensures value is a positive integer |
| `validate_day_of_week(day)` | Validates Mon-Fri day strings |
| `validate_time(time_str)` | Validates `HH:MM` format with range checks |
| `validate_time_range(start, end)` | Ensures start time is before end time |

All validators raise `ValidationError` with descriptive messages on failure.

---

## Audit Logging

The `AuditLogger` class in `infrastructure/security/audit.py` records security-relevant events to the `audit_log` database table.

### What Gets Logged

Each audit log entry contains:

| Field | Description |
|---|---|
| `user_id` | The ID of the user who performed the action (nullable for system events) |
| `username` | The username of the acting user |
| `action` | The type of action performed (e.g., `login`, `create_user`, `change_password`) |
| `resource` | The resource affected (e.g., `user`, `course`, `grade`) |
| `details` | Free-text description of the event |
| `ip_address` | The IP address from which the action originated |
| `timestamp` | UTC ISO-format timestamp of the event |

### Querying the Audit Trail

The `get_logs()` method supports filtering:

- **By user:** Filter entries for a specific `user_id`.
- **By action:** Filter entries by action type.
- **Limit:** Default 100 entries, ordered by timestamp descending (most recent first).

All queries use parameterized SQL to prevent injection.

### Events Logged via Application Logging

In addition to the audit table, the authentication system writes structured log messages using Python's `logging` module. Events logged include:

- Login successes and failures (with username and attempt count)
- Account lockouts
- MFA setup, verification success, and verification failure
- Session creation and invalidation
- User creation (with role and ID)
- Password changes
- Role assignments
- Access denied events on API endpoints

---

## Data Protection

### SQL Injection Prevention

All database queries throughout the authentication, session, role, MFA, and audit modules use **parameterized queries** (the `?` placeholder syntax with SQLite). No user input is ever interpolated directly into SQL strings.

Examples from the codebase:

```python
# Parameterized user lookup
conn.execute("SELECT * FROM users WHERE username = ?", (username,))

# Parameterized session creation
conn.execute(
    "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
    (user_id, token, expires_at.isoformat()),
)

# Parameterized audit log query
conn.execute(
    "SELECT * FROM audit_log WHERE user_id = ? AND action = ? ORDER BY timestamp DESC LIMIT ?",
    (user_id, action, limit),
)
```

### Sensitive Data Handling

- **Passwords** are never stored in plaintext; only bcrypt hashes are persisted.
- **MFA recovery codes** are stored as SHA-256 hashes, not in plaintext. The plaintext codes are shown to the user only once at setup time.
- **MFA TOTP secrets** are stored in the `mfa_secrets` table. In a production environment, these should be encrypted at rest.
- **JWT secret keys** should be stored as environment variables, not in source code.
- **Login error messages** are generic ("Invalid username or password.") to prevent username enumeration.

### Transaction Safety

All write operations use explicit `conn.commit()` calls within `try/finally` blocks that guarantee `conn.close()` is called. Operations that may fail (like user creation) include `conn.rollback()` in the error path.

---

## Session Security

### GUI/CLI Sessions

Managed by the `SessionManager` class in `infrastructure/auth/session_manager.py`.

- **Token generation:** Uses `secrets.token_urlsafe(32)` to produce a cryptographically secure 32-byte URL-safe token.
- **Expiry:** Sessions expire after 30 minutes by default (configurable via `SESSION_TIMEOUT_MINUTES` or the `COLLEGE_SESSION_TIMEOUT` environment variable).
- **Validation:** The `validate_session()` method joins the `sessions` and `users` tables to verify the token is active and not expired. Expired tokens are automatically invalidated on validation.
- **Invalidation:** Individual sessions can be invalidated by token. All sessions for a user can be invalidated at once (used during password changes).
- **Cleanup:** The `cleanup_expired()` method removes expired and inactive sessions from the database.

### API Sessions (JWT)

- JWT tokens are stateless and validated by signature and expiry.
- Token expiry is 24 hours by default.
- MFA verification tokens expire after 5 minutes.
- On password change, all GUI/CLI sessions for the user are invalidated.

### Session Lifecycle

```
Login --> Password verified --> MFA check (if enabled) --> Session token created
                                                              |
                                                              v
                                                  Token stored in database
                                                  (with expiry timestamp)
                                                              |
                                                              v
                                          Subsequent requests validated against DB
                                                              |
                                                              v
                                          Logout / Expiry --> Token marked inactive
```

---

## Best Practices and Production Recommendations

The following recommendations apply when deploying the college system in a production environment.

### 1. Change Default Passwords

The system may ship with default user accounts for initial setup. Before going live:

- Change all default admin and staff passwords immediately.
- Ensure all passwords meet the strength requirements (8+ characters, mixed case, digit, special character).
- Consider increasing `MIN_PASSWORD_LENGTH` beyond the default of 8 for higher security.

### 2. Enable Multi-Factor Authentication

- Enable MFA for all admin and staff accounts at minimum.
- Encourage MFA adoption for all user roles.
- Ensure users securely store their recovery codes.
- See [MFA_GUIDE.md](MFA_GUIDE.md) for setup instructions.

### 3. Configure HTTPS

- Always serve the API and web interface over HTTPS in production.
- Configure TLS certificates from a trusted certificate authority.
- Set `Secure` and `HttpOnly` flags on any cookies.
- Redirect all HTTP traffic to HTTPS.

### 4. Restrict CORS

The default CORS configuration (`CORS(app)`) allows all origins. For production:

- Restrict `CORS` to specific allowed domains.
- Configure appropriate allowed methods and headers.

### 5. Secure the JWT Secret Key

- Use a strong, randomly generated secret key (at least 256 bits).
- Store the key in an environment variable or secrets manager, never in source code.
- Rotate the key periodically and have a plan for token invalidation during rotation.

### 6. Review Audit Logs

- Regularly review audit log entries for suspicious activity (repeated failed logins, privilege escalation attempts, unusual access patterns).
- Set up automated alerts for critical events (account lockouts, admin actions).
- Archive audit logs according to your data retention policy.

### 7. Session Configuration

- Review the session timeout duration (default 30 minutes) and adjust for your security requirements.
- Run the `cleanup_expired()` method on a scheduled basis to clear stale sessions.
- Consider reducing `JWT_EXPIRY_HOURS` from 24 hours for more sensitive deployments.

### 8. Database Security

- Restrict filesystem permissions on the SQLite database file.
- Enable SQLite WAL mode for better concurrency handling.
- Consider encrypting the database at rest using SQLCipher or filesystem-level encryption, particularly for TOTP secrets stored in the `mfa_secrets` table.
- Perform regular database backups.

### 9. Logging and Monitoring

- Configure Python logging to write to persistent log files with appropriate rotation.
- Monitor for patterns indicating attack attempts (high volumes of failed logins, rapid API requests).
- Ensure log output does not contain sensitive data (passwords, tokens, personal information).

### 10. Network Security

- Deploy behind a reverse proxy (e.g., nginx) that handles TLS termination, rate limiting, and request filtering.
- Implement rate limiting on the login and MFA endpoints to further defend against brute-force attacks.
- Consider IP-based allowlisting for admin API endpoints.

### 11. Dependency Management

- Keep `bcrypt`, `PyJWT`, `pyotp`, `Flask`, and `flask-cors` updated to their latest stable versions.
- Regularly audit dependencies for known vulnerabilities.

### 12. Data Protection Compliance

- Ensure the system meets applicable data protection regulations (e.g., UK GDPR, Data Protection Act 2018) when handling student and staff personal data.
- Implement data retention and deletion policies.
- Provide mechanisms for data subject access requests.
