# Secondary School Management System - Security

> Last Updated: March 2026

## Overview

The Secondary School Management System handles sensitive data for minors (students aged 11-16) and must meet stringent security and data protection requirements. This document outlines the security measures in place and recommendations for production deployment.

## Password Security

### bcrypt Hashing

All passwords are hashed using bcrypt with automatic salting:

- **Algorithm**: bcrypt (via the `bcrypt` Python library).
- **Work factor**: Default bcrypt cost factor (12 rounds).
- **Salt**: Automatically generated per password by bcrypt.
- **Storage**: Only the hash is stored in `auth.db` (`users.password_hash`).

Plaintext passwords are never stored, logged, or transmitted in clear text within the system.

### Legacy Hash Migration

Accounts created before the bcrypt migration may use PBKDF2-SHA256 hashing. These are identified by a non-null `legacy_salt` column in the `users` table and are automatically re-hashed to bcrypt on the next successful login. No administrator action is required.

### Password Requirements

Recommended minimum password policy for production:

- Minimum 8 characters.
- At least one uppercase letter, one lowercase letter, one digit, and one special character.
- No reuse of the last 5 passwords.
- Forced password change on first login for new accounts.

## SQL Injection Prevention

All database queries use parameterised statements. String interpolation or concatenation is never used for SQL values.

```python
# Correct -- parameterised query
cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))

# NEVER do this
cursor.execute(f"SELECT * FROM students WHERE student_id = '{student_id}'")
```

The infrastructure database module enforces this pattern. Code reviews should reject any SQL queries that embed user input directly into query strings.

## Role-Based Access Control (RBAC)

Access control is enforced at the service layer based on the user's role in the `user_systems` table.

### Role Hierarchy

| Role | Level | Description |
|------|-------|-------------|
| `admin` | Highest | Full system access |
| `teacher` | Standard | Student data, grades, attendance, pastoral |
| `student` | Restricted | Own records only (read-mostly) |

### Access Control Matrix (Summary)

| Module | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Student records | Full CRUD | Read + own students | Own record (read) |
| Grades | Full CRUD | Own classes | Own grades (read) |
| Attendance | Full CRUD | Own classes | Own record (read) |
| Behaviour | Full CRUD | Create + read | Own record (read) |
| Safeguarding | Full access | DSL-flagged only | No access |
| SEND records | Full CRUD | Read (assigned students) | No access |
| User management | Full CRUD | No access | No access |
| Settings | Full CRUD | No access | No access |
| Finance | Full CRUD | No access | No access |
| Audit log | Read | No access | No access |
| Reports | Full access | Own classes | No access |

### Implementation

```python
def require_role(*allowed_roles):
    """Decorator to enforce role-based access."""
    def decorator(func):
        def wrapper(current_user, *args, **kwargs):
            if current_user["role"] not in allowed_roles:
                raise AuthorisationError("Insufficient permissions")
            return func(current_user, *args, **kwargs)
        return wrapper
    return decorator

@require_role("admin", "teacher")
def update_grade(current_user, student_id, subject, grade):
    # Only admin and teacher can reach this code
    ...
```

## Session Management

Sessions are database-backed and validated on every request:

| Parameter | Value |
|-----------|-------|
| Token generation | `secrets.token_urlsafe(32)` |
| Session timeout | 30 minutes (configurable) |
| Storage | `sessions` table in `auth.db` |
| Validation | Token + expiry + `is_valid` flag |

### Session Security Measures

- **Cryptographic tokens**: Generated using Python's `secrets` module (CSPRNG).
- **Server-side storage**: Tokens are validated against the database, not decoded client-side.
- **Automatic expiry**: Sessions expire after 30 minutes of inactivity.
- **Explicit invalidation**: Logout sets `is_valid = 0` immediately.
- **No concurrent sessions** (recommended): Consider limiting each user to one active session.

## Account Lockout

Brute-force protection is built into the shared auth module:

1. Each failed login increments `failed_login_attempts` on the `users` record.
2. After 5 consecutive failures (`MAX_LOGIN_ATTEMPTS`), the account is locked.
3. `locked_until` is set to 15 minutes in the future.
4. All login attempts are rejected during the lockout period.
5. On successful login after lockout expiry, the counter resets to 0.
6. Administrators can manually unlock accounts via the user management module.

Lockout events are recorded in the audit log.

## Audit Logging

All security-relevant events are recorded in the `audit_log` table:

| Event Type | Details Logged |
|------------|---------------|
| Login success | Username, timestamp, IP (if API) |
| Login failure | Username, timestamp, attempt count |
| Account lockout | Username, lockout expiry |
| Logout | Username, session duration |
| Password change | Username, timestamp (not the password) |
| MFA enable/disable | Username, method |
| Record access | User, table, record ID, action (CRUD) |
| Data export | User, export type, record count |
| Role change | Admin user, target user, old/new role |

Audit log entries are append-only. They cannot be modified or deleted through the application interface.

### Audit Log Retention

- Minimum retention: 7 years (aligned with UK education record-keeping requirements).
- Audit logs should be included in database backups.
- Consider exporting audit logs to a separate, tamper-evident storage system for production.

## GDPR Compliance for Minors

The Secondary School system handles personal data of children under 16, which requires enhanced protections under GDPR and the UK Data Protection Act 2018.

### Key Requirements

| Requirement | Implementation |
|-------------|---------------|
| Lawful basis | Legitimate interest / public task (education) |
| Data minimisation | Only collect data necessary for educational purposes |
| Parental consent | Consent records stored in `consent` table |
| Right of access | Data export via `data_exports` module (subject access requests) |
| Right to erasure | Data deletion support with audit trail |
| Data retention | Automatic purging after configurable retention period |
| Breach notification | Audit log monitoring; 72-hour ICO notification requirement |
| Privacy by design | Role-based access, encryption recommendations, logging |

### Data Subject Access Requests (DSARs)

The system supports generating comprehensive data exports for individual students, including:

- Personal details from `students` table.
- Academic records (grades, attendance, progress).
- Pastoral records (behaviour, rewards, pastoral notes).
- Communication records.
- Consent records.

SEND and safeguarding records may require separate handling with DSL involvement.

### Data Retention Periods

| Data Category | Recommended Retention | Notes |
|---------------|----------------------|-------|
| Student academic records | Duration of enrollment + 6 years | May vary by local policy |
| Attendance records | Current year + 3 years | |
| Behaviour records | Duration of enrollment + 1 year | Excludes permanent exclusions |
| Safeguarding records | Until student turns 25 | May be longer if concerns ongoing |
| SEND records | Duration of enrollment + 6 years | |
| Audit logs | 7 years | Regulatory requirement |

## Safeguarding Access Controls

Safeguarding data requires the highest level of access control:

- **Access restricted** to Designated Safeguarding Lead (DSL) flagged accounts and administrators.
- **No student access** to safeguarding records under any circumstances.
- **Teacher access** limited to those explicitly flagged as DSL or deputy DSL.
- **Audit trail** records every access to safeguarding records.
- **Separate logging** -- safeguarding access events are flagged in audit logs for review.

```python
def access_safeguarding(current_user, student_id):
    """Access safeguarding records with enhanced checks."""
    if not current_user.get("is_dsl") and current_user["role"] != "admin":
        raise AuthorisationError("Safeguarding access requires DSL status")
    log_safeguarding_access(current_user["id"], student_id)
    return get_safeguarding_records(student_id)
```

## Production Security Recommendations

### Deployment

1. **Run behind a reverse proxy** (e.g., nginx) with TLS termination. Never expose the Flask API directly.
2. **Use HTTPS only** -- configure HSTS headers via the reverse proxy.
3. **Restrict file permissions** on the database files (`chmod 600`).
4. **Bind API to localhost** unless accessed from other machines (set `SCHOOL_API_HOST=127.0.0.1`).
5. **Disable debug mode** in production.

### Authentication

6. **Change all default passwords** before production use.
7. **Enable MFA** for all staff accounts (admin and teacher roles).
8. **Review and remove** unused accounts regularly.
9. **Enforce password complexity** requirements.

### Data Protection

10. **Encrypt the database** at rest using OS-level encryption (e.g., LUKS, BitLocker).
11. **Encrypt backups** before off-site storage.
12. **Implement backup rotation** with at least 30 days of retention.
13. **Test restore procedures** quarterly.

### Monitoring

14. **Monitor audit logs** for unusual access patterns.
15. **Set up alerts** for account lockouts and failed login spikes.
16. **Review safeguarding access logs** weekly.
17. **Conduct annual security reviews** of access controls and data retention.

### Network

18. **Firewall rules** should restrict access to the API port (5001) to trusted networks only.
19. **Disable unused network services** on the server.
20. **Keep all dependencies updated** -- monitor for security advisories in Python packages.
