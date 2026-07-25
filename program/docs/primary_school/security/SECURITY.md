# Primary School Security Guide

> Last Updated: March 2026

## Overview

The Primary School Management System handles sensitive data about children, staff, and families. Security is not optional -- it is a fundamental requirement driven by legal obligations (GDPR, UK Data Protection Act 2018, Children's Code / Age Appropriate Design Code) and safeguarding duties.

This document describes the security measures in place and provides recommendations for production deployment.

---

## Password Security

### bcrypt Hashing

All passwords are hashed using **bcrypt** before storage. bcrypt provides:

- **Adaptive cost factor**: The work factor can be increased as hardware improves.
- **Built-in salting**: Each hash includes a unique random salt, preventing rainbow table attacks.
- **Deliberate slowness**: bcrypt is intentionally slow to compute, making brute-force attacks impractical.

Passwords are **never** stored in plaintext or reversible encryption. The system cannot retrieve a forgotten password -- it can only reset it.

### Password Requirements

- Minimum length enforced at account creation.
- Default accounts use the pattern `<Role>@<System>123` (e.g., `Admin@Primary123`) and **must** be changed before production use.

### Legacy Hash Migration

Accounts with older PBKDF2-SHA256 hashes are transparently migrated to bcrypt on their next successful login. No manual intervention is required. See [AUTHENTICATION.md](../infrastructure/AUTHENTICATION.md) for details.

---

## SQL Injection Prevention

All database queries use **parameterized queries** (also called prepared statements). User-supplied values are never interpolated directly into SQL strings.

### Correct Pattern

```python
# SAFE: Parameterized query
cursor.execute("SELECT * FROM pupils WHERE pupil_id = ?", (pupil_id,))
```

### Prohibited Pattern

```python
# DANGEROUS: String interpolation -- NEVER do this
cursor.execute(f"SELECT * FROM pupils WHERE pupil_id = '{pupil_id}'")
```

The `infrastructure/validation/` module provides additional input sanitisation for values before they reach the database layer.

---

## Role-Based Access Control (RBAC)

Access to system features and data is controlled by the user's assigned role. The Primary School defines four roles:

| Role | Access Level |
|---|---|
| **admin** | Full access to all modules including user management, settings, finance, audit logs, and data export. Can view and manage safeguarding records. |
| **teacher** | Access to pupil records, assessment, attendance, homework, behaviour, and pastoral care for assigned classes. Can raise safeguarding concerns. |
| **student** | Read-only access to own records: timetable, homework, reading log. Minimal functionality. |
| **parent** | Read-only access to linked pupil's records: attendance, assessment, reports. Can submit consent forms and book parents' evening appointments. |

### Enforcement Points

RBAC is enforced at **two levels**:

1. **GUI layer**: Menu items, buttons, and tabs are shown or hidden based on the user's role. This prevents accidental access but is not a security boundary.
2. **Service layer**: Every service method checks the current user's role before executing. This is the authoritative access control point. Even if the GUI is bypassed (e.g., via CLI or API), the service layer rejects unauthorised requests.

### Safeguarding Data

Safeguarding records receive additional access restrictions beyond standard RBAC:

- Only users with explicit safeguarding permissions (typically admin and designated safeguarding leads) can **view** safeguarding concern records.
- Teachers can **raise** a safeguarding concern but cannot view concerns raised by others.
- Safeguarding data is excluded from bulk data exports unless explicitly authorised.

---

## Session Management

Sessions are database-backed and subject to strict lifecycle controls:

| Control | Value |
|---|---|
| Session storage | `sessions` table in `auth.db` |
| Token generation | Cryptographically secure random tokens |
| Timeout | 30 minutes of inactivity |
| Logout | Session record deleted from database |

Sessions cannot be forged because tokens are generated using `secrets.token_urlsafe()` or equivalent CSPRNG. Token length provides sufficient entropy to resist guessing attacks.

See [AUTHENTICATION.md](../infrastructure/AUTHENTICATION.md) for full session lifecycle details.

---

## Account Lockout

Brute-force login attempts are mitigated by automatic account lockout:

| Parameter | Value |
|---|---|
| Maximum failed attempts | 5 |
| Lockout duration | 15 minutes |
| Counter reset | On successful login |

Lockout events are recorded in the audit log. Administrators can manually unlock accounts through the admin panel if needed.

---

## Audit Logging

The `audit_log` table records security-relevant events for accountability and forensic analysis:

| Event Type | Details Recorded |
|---|---|
| Login success | User, timestamp, IP address |
| Login failure | Username attempted, timestamp, IP address |
| Account lockout | Username, timestamp, attempt count |
| Password change | User, timestamp (not the password itself) |
| Role change | User affected, old role, new role, changed by whom |
| Data export | User, timestamp, export type, record count |
| Safeguarding access | User, timestamp, record accessed |
| Record modification | User, timestamp, table, record ID, operation (create/update/delete) |

### Audit Log Protection

- Audit log entries are **append-only** -- they cannot be modified or deleted through the application.
- Only admin users can view the audit log.
- Audit logs should be backed up separately from the main database and retained according to your data retention policy.

---

## Data Protection for Minors

### Legal Framework

The Primary School system processes personal data about children (ages 4-11). This data is subject to enhanced protections under:

- **UK GDPR** (General Data Protection Regulation as retained in UK law)
- **UK Data Protection Act 2018**
- **Children's Code** (Age Appropriate Design Code, ICO)
- **Keeping Children Safe in Education** (DfE statutory guidance)

### Principles Applied

| Principle | Implementation |
|---|---|
| **Data minimisation** | Only data necessary for educational and safeguarding purposes is collected. |
| **Purpose limitation** | Data is used only for the purposes stated in the school's privacy notice. |
| **Storage limitation** | Retention policies should be configured per the school's data retention schedule. |
| **Integrity and confidentiality** | Encryption at rest (recommended), access controls, audit logging. |
| **Lawful basis** | Public task (education provision) and legal obligation (safeguarding). Consent for optional processing (e.g., photographs). |

### Specific Safeguards

- **Parental consent tracking**: The `consent` table records explicit parental consent for activities such as photographs, trips, and data sharing with third parties.
- **Data Subject Access Requests (DSARs)**: The data export module supports generating reports of all data held about a pupil, facilitating DSAR compliance.
- **Right to erasure**: While certain education records must be retained by law, the system supports anonymisation of records after the retention period.
- **Safeguarding records**: Treated as highly sensitive. Access-restricted, separately audited, and excluded from routine data exports.

---

## Safeguarding Data Access Controls

Given the critical nature of safeguarding data in a primary school context:

1. **Designated Safeguarding Lead (DSL)** and deputies should have explicit safeguarding access flags on their accounts.
2. **Teachers** can submit safeguarding concerns but cannot browse or search existing concerns.
3. **Safeguarding records** are never included in:
   - Bulk data exports
   - Parent portal views
   - Student-facing displays
   - General search results
4. **All access** to safeguarding records is individually audited with user identity, timestamp, and record accessed.
5. **Safeguarding data** should be retained according to local safeguarding partnership guidance (often until the child's 25th birthday).

---

## Recommendations for Production Deployment

The following measures are strongly recommended before deploying the Primary School system in a real school environment:

### Authentication

- [ ] Change all default account passwords immediately.
- [ ] Enable MFA for all staff accounts (see [MFA_GUIDE.md](MFA_GUIDE.md)).
- [ ] Set a strong, unique `PRIMARY_SCHOOL_JWT_SECRET` environment variable.
- [ ] Review and tighten session timeout if appropriate for your environment.

### Network

- [ ] Deploy behind HTTPS (TLS 1.2 or later). Never expose the application over plain HTTP.
- [ ] Use a reverse proxy (e.g., nginx) to terminate TLS and limit request sizes.
- [ ] Restrict API access to trusted networks or authenticated clients only.
- [ ] Configure firewall rules to allow only necessary ports.

### Database

- [ ] Encrypt the database file at rest (e.g., using filesystem-level encryption or SQLCipher).
- [ ] Restrict filesystem permissions on `primary_school.db` and `auth.db` to the application user only.
- [ ] Schedule automated daily backups with off-site storage.
- [ ] Test restore procedures regularly.

### Monitoring

- [ ] Monitor audit logs for unusual activity (failed logins, bulk data access, out-of-hours access).
- [ ] Set up alerting for account lockout events.
- [ ] Review access logs periodically.

### Operational

- [ ] Disable debug mode (`PRIMARY_SCHOOL_DEBUG=false`).
- [ ] Keep Python dependencies up to date and scan for known vulnerabilities.
- [ ] Conduct annual security reviews and penetration testing.
- [ ] Maintain an incident response plan covering data breaches involving children's data (72-hour ICO notification requirement).
- [ ] Train staff on data protection responsibilities and phishing awareness.
