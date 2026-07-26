# Security Policy

This is the single security document for the repository: how to report a
vulnerability, what the platform implements, and how to harden a deployment.

## Table of Contents

- [Supported Versions](#supported-versions)
- [Reporting a Vulnerability](#reporting-a-vulnerability)
- [Security Features](#security-features)
- [Authentication & Authorization](#authentication--authorization)
- [Data Protection](#data-protection)
- [Database Security](#database-security)
- [Input Validation](#input-validation)
- [Session Management](#session-management)
- [Error Handling](#error-handling)
- [Audit Logging](#audit-logging)
- [Deployment Security](#deployment-security)
- [Security Best Practices](#security-best-practices)
- [Additional Resources](#additional-resources)

## Supported Versions

Security updates are provided for the current major release line:

| Version | Supported          |
| ------- | ------------------ |
| 9.x     | :white_check_mark: |
| < 9.0   | :x:                |

## Reporting a Vulnerability

We take all security vulnerabilities seriously. If you discover a security
issue, please report it responsibly.

### How to Report

1. **DO NOT** open a public GitHub issue
2. Contact the project maintainers directly rather than filing publicly
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Status Updates**: Weekly until resolved
- **Resolution**: Critical issues within 30 days

### Disclosure Policy

- We follow coordinated disclosure
- We will credit researchers (unless anonymity is requested)
- Please allow us to patch before public disclosure
- We do not currently offer a bug bounty program

## Security Features

The system implements comprehensive security measures following industry best
practices.

### Password Security

- **bcrypt hashing** as the standard password hash (with transparent migration
  from legacy PBKDF2-SHA256)
- Legacy PBKDF2-SHA256 passwords (1,000,000 iterations) are automatically
  re-hashed to bcrypt on first successful login
- Never stores plaintext passwords
- Automatic salt generation and secure random number generation
- Password complexity requirements enforced at registration
- Constant-time dummy verification on unknown usernames, so login timing does
  not reveal whether an account exists

Implementation: `program/education_system/platform/identity/auth/password_manager.py`

### Multi-Factor Authentication

- **TOTP (Time-based One-Time Password)**: Google Authenticator compatible
- **Email OTP**: One-time codes via email (sends to user's configured email)
- **SMS OTP**: Text message verification (optional, via Twilio or free
  Email-to-SMS gateway)
- **PIN Verification**: 4-digit on-screen PIN for users without MFA setup
- **WebAuthn/FIDO2**: Passwordless authentication with security keys and
  platform authenticators
- **Biometric Authentication**: Face and fingerprint enrollment with 128-D
  encoding
- **SSO Integration**: SAML 2.0 and OpenID Connect provider support
- **Account Linking**: Multi-account support with role switching and audit
  trails
- **Delegated Access**: Scoped, time-bound access delegation for
  parents/guardians
- QR code generation for easy 2FA setup
- Unified login dispatcher routing across all authentication methods

### Login Verification Options

The system offers flexible login security levels to balance security and
convenience:

| Security Level | Setting | Verification Method |
|---------------|---------|---------------------|
| **Maximum** | MFA Email enabled | 6-digit code sent to email |
| **Moderate** | Verification ON, no MFA | 4-digit PIN displayed on screen |
| **Convenience** | Verification OFF | Password only (no additional step) |

**Toggle Login Verification:**

- Users can disable all verification via Authentication -> Toggle Login Verification
- When disabled, login only requires username and password
- Setting is per-user and stored in database
- Can be re-enabled at any time

```python
# Check if verification is disabled for a user
from education_system.systems.university.infrastructure.auth.mfa_service import MFAService
mfa_service = MFAService()

if mfa_service.is_verification_disabled(user_id):
    # Password-only login
    pass
else:
    # Require verification (PIN or Email OTP)
    pass

# Toggle verification on/off
mfa_service.set_verification_disabled(user_id, disabled=True)  # Disable
mfa_service.set_verification_disabled(user_id, disabled=False) # Enable
```

### SQL Injection Prevention

- **Parameterized queries** enforced throughout the codebase
- No string concatenation or interpolation in SQL
- ORM-like patterns for safe query construction

```python
# CORRECT: Parameterized query
conn.execute("SELECT * FROM students WHERE id = ?", (student_id,))

# INCORRECT: SQL injection risk
conn.execute(f"SELECT * FROM students WHERE id = {student_id}")
```

### Transaction Safety

- **ACID-compliant** database operations
- Automatic rollback on exceptions via context managers
- Write-Ahead Logging (WAL) for data integrity

```python
# Transaction with automatic rollback on error
with transaction() as conn:
    conn.execute("INSERT INTO students ...")
    conn.execute("INSERT INTO enrollments ...")
    # Auto-commits if no exception, auto-rollbacks on error
```

Implementation: `program/education_system/systems/university/infrastructure/database/db.py`

### Access Control

- **Role-Based Access Control (RBAC)**: Admin, Instructor, Student, Staff,
  Parent roles
- **Fine-grained permissions**: Over 330 distinct permissions across all modules
- **Permission decorators**: `@require_permission('permission_name')`
- **Global auth context**: Shared authentication state across modules
- **UI-Level Access Control**: Dynamic interface filtering based on user roles

#### Role-Based UI Access Control

All GUI modules implement comprehensive role-based navigation and menu
filtering, ensuring users only see features appropriate for their role:

**Admin Users** — Full system access:

- All GUI features unlocked across all modules
- System management and configuration tools
- Export/import data capabilities
- View all records system-wide
- Analytics, reports, and admin panels
- User management and permissions control

**Staff Users** — Operational access:

- Domain-specific management features (teaching, support, health services, etc.)
- Create and edit content within their domain
- View records relevant to their role
- Generate reports and analytics
- Limited to operational tasks (no system-wide administration)

**Student Users** — Self-service access:

- View own records and information
- Submit applications and requests
- Browse available services and opportunities
- Participate in student activities
- No access to administrative or management functions

**Parent Users** (Parent Portal):

- View children's academic records and progress
- Communication with teachers and staff
- Financial management for student accounts
- Health and safety information access
- Admin users can access additional parent management tools

**Implemented Across 15+ GUI Modules**:

- Finance GUI (14 tabs: Admin full, Staff 11, Student 4)
- Health Portal (Admin full, Staff operations, Student personal)
- Student Union/Campus Events (Admin full, Staff operations, Student participation)
- Trip Management (Admin/Staff create, Student register)
- Shop Management (Admin/Staff management, Student shopping)
- Student Support (Admin/Staff all tickets, Student own tickets)
- Parent Portal (Admin with Admin Panel, Parent full features)
- Helpdesk (Admin/Staff management, Student tickets only)
- Internship Portal (Admin/Staff create, Student apply)
- Career Services (Admin/Staff management, Student career development)
- Library Management (Admin full, Staff operations, Student borrow)
- Academic Calendar (Admin full, Staff teaching, Student view)
- Grade Tracking (Admin 16 features, Staff 11, Student 3)
- Assignment System (Admin 5 sections, Staff 4, Student 2)
- Course Management (Admin/Staff manage, Student enroll)

Each module includes standardized role detection methods:

```python
def get_user_role(self):
    """Get current user's role from auth system"""

def is_admin(self):
    """Check if current user is admin"""

def is_staff(self):
    """Check if current user is staff/instructor"""

def is_student(self):
    """Check if current user is student"""
```

### Data Encryption

- **Fernet symmetric encryption** for sensitive data at rest
- **TLS/SSL support** for database connections
- **Encrypted session tokens**
- **Secure key management** via environment variables

### Account Lockout Protection

- **Failed login tracking**: Accounts locked after 5 failed attempts (configurable)
- **Lockout duration**: 15 minutes by default (configurable)
- **Remaining attempts display**: Users see how many attempts remain
- **Emergency unlock functions**: Administrative functions to unlock any account
  - All unlock attempts are logged for security audit
  - Default password: `UnlockMe2024!SecureAdmin`
  - Can be overridden via environment variable: `EMERGENCY_UNLOCK_PASSWORD`

**Available Functions:**

```python
# Unlock a specific account
auth.emergency_unlock(username, emergency_password)

# Unlock ALL locked accounts at once
auth.emergency_unlock_all(emergency_password)

# List all currently locked accounts
auth.list_locked_accounts()
# Returns: [{'username': 'user1', 'failed_attempts': 5, 'locked_at': '...', 'minutes_remaining': 10}, ...]
```

**Security Warning**: Change the emergency unlock password in production by
setting the `EMERGENCY_UNLOCK_PASSWORD` environment variable.

### Rate Limiting

Authentication endpoints are rate limited per IP **and** per username, backed by
a persistent store so limits survive a restart:

- `POST /api/v1/auth/login` — per-IP and per-username limits, returning `429`
- Password reset and MFA verification carry their own attempt limits
- Account lockout (above) applies on top of the request-level limits

Implementation: `program/education_system/platform/delivery/api/auth.py` and
`program/education_system/platform/identity/auth/rate_limit_store.py`

## Authentication & Authorization

### Authentication Flow

```
1. User submits credentials
2. System retrieves user record by username
3. System verifies the submitted password against the stored bcrypt hash
   (a dummy comparison runs for unknown users so timing is constant)
4. Legacy PBKDF2 hashes are transparently re-hashed to bcrypt on success
5. If match: create session, grant access
6. If no match: increment the failure counter and return a generic error
   (prevents username enumeration)
```

### Role-Based Access Control (RBAC)

The system implements RBAC with the following roles:

| Role          | Permissions                                      |
|---------------|--------------------------------------------------|
| **Admin**     | Full system access, user management             |
| **Faculty**   | Course management, grading, student records     |
| **Student**   | Personal records, course enrollment, submissions|
| **Staff**     | Module-specific permissions                     |
| **Parent**    | Linked children's records via the parent portal |

### Permission Checking

```python
from education_system.systems.university.infrastructure.auth import require_permission

@require_permission('courses.create')
def create_course(user_id: int, course_data: dict):
    """Only users with 'courses.create' permission can execute."""
    pass
```

### Session Management

- **Session Timeout**: 3600 seconds (1 hour) by default
- **Token Storage**: Secure, HTTP-only cookies for the web interface
  (`SESSION_COOKIE_SECURE` and `SESSION_COOKIE_HTTPONLY` are set outside
  development environments)
- **Invalidation**: Immediate logout on password change or account lockout
- **Concurrent session limits** per user, with automatic session cleanup
- **Session hijacking prevention**

## Data Protection

### Sensitive Data

Sensitive fields are identified and handled specially:

```python
SENSITIVE_FIELDS = {
    'password',
    'password_hash',
    'salt',
    'ssn',
    'medical_records',
    'financial_data',
    'api_keys',
    'tokens'
}
```

### Encryption

- **At Rest**: Support for encrypted SQLite databases
- **In Transit**: HTTPS/TLS for all web communications
- **Email**: TLS for SMTP connections

### Data Retention

- **Audit Logs**: Retained for 1 year
- **Backups**: 30-day retention by default
- **User Data**: Per institutional policy
- **Medical Records**: 7 years (HIPAA compliance)

## Database Security

### Connection Security

```python
class DatabaseManager:
    def __init__(self, db_path: str, read_only: bool = False):
        """
        Initialize database with security features.

        Args:
            db_path: Path to database file
            read_only: If True, open in read-only mode
        """
        uri = f"file:{db_path}{'?mode=ro' if read_only else ''}"
        self.conn = sqlite3.connect(uri, uri=True)

        # Enable foreign key constraints
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Set secure defaults
        self.conn.execute("PRAGMA journal_mode = WAL")
```

The central `auth.db` and its WAL sidecar are chmod `0600` on every open, so
credentials are never world-readable.

### Query Safety

All queries use one of these safe patterns:

```python
# Pattern 1: Direct parameters
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# Pattern 2: Named parameters
cursor.execute(
    "INSERT INTO courses (name, code) VALUES (:name, :code)",
    {"name": name, "code": code}
)

# Pattern 3: Transaction helper
with get_db_transaction() as (conn, cursor):
    cursor.execute("UPDATE ...", (data,))
```

### Backup Security

```bash
# Backups are created with restricted permissions
chmod 600 backups/*.db

# Only database owner can read/write
chown dbuser:dbgroup backups/*.db
```

## Input Validation

### Validation Principles

1. **Whitelist, Don't Blacklist**: Define what is allowed, not what is forbidden
2. **Validate Early**: Check input at system boundaries
3. **Validate Type and Format**: Ensure data matches expected structure
4. **Sanitize for Context**: Escape/encode based on where data is used

### Example Validation

```python
def create_user(username: str, email: str):
    # Validate username
    if not validate_username(username):
        raise ValueError("Invalid username format")

    # Validate email
    if not validate_email(email):
        raise ValueError("Invalid email format")

    # Additional validation
    if len(username) < 3 or len(username) > 50:
        raise ValueError("Username must be 3-50 characters")
```

### File Upload Security

```python
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.png'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def validate_upload(file_path: str, content: bytes):
    # Check extension
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type {ext} not allowed")

    # Check size
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("File too large")

    # Check for malicious content
    # (implement virus scanning in production)
```

## Session Management

### Session Configuration

```python
SESSION_TIMEOUT = 3600  # 1 hour
MAX_CONCURRENT_SESSIONS = 3  # Per user
SESSION_REFRESH_INTERVAL = 900  # 15 minutes
```

### Session Security

Sessions are invalidated on:

- Explicit logout
- Timeout due to inactivity
- Password change
- Account suspension
- Security event detection

```python
def invalidate_user_sessions(user_id: int):
    """Invalidate all sessions for a user."""
    with get_db_transaction() as (conn, cursor):
        cursor.execute(
            "DELETE FROM sessions WHERE user_id = ?",
            (user_id,)
        )
```

## Error Handling

- **Structured exception hierarchy** preventing information leakage
- **Generic error messages** to users
- **Detailed logging** for administrators
- **No stack traces** in production

### Exception Hierarchy

```python
class UniversitySystemException(Exception):
    """Base exception for all system errors."""
    pass

class DatabaseException(UniversitySystemException):
    """Database-related errors."""
    pass

class ValidationException(UniversitySystemException):
    """Input validation errors."""
    pass

class AuthenticationException(UniversitySystemException):
    """Authentication failures."""
    pass

class AuthorizationException(UniversitySystemException):
    """Permission denied errors."""
    pass
```

### Error Response Guidelines

**DO:**

- Log detailed errors securely
- Return generic messages to users
- Include error codes for support
- Track error patterns

**DON'T:**

- Expose stack traces to users
- Reveal system internals in errors
- Include sensitive data in error messages
- Log passwords or tokens

### Example Error Handling

```python
try:
    result = perform_database_operation()
except DatabaseException as e:
    # Log detailed error
    logger.error(f"Database error: {e}", exc_info=True)

    # Return generic message to user
    return {
        "success": False,
        "error": "A database error occurred",
        "error_code": "DB001",
        "timestamp": datetime.now().isoformat()
    }
```

## Audit Logging

- **Comprehensive activity logs** for all data modifications
- **User attribution** for accountability
- **Timestamp tracking** for compliance
- **Immutable audit trail** for forensic analysis

```python
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Log all data modifications
log_activity('create', 'student', student_id='12345', details={'name': 'John Doe'})
log_activity('update', 'grade', grade_id='456', changes={'old': 'B', 'new': 'A'})
log_activity('delete', 'course', course_id='CS101')
```

### What We Log

Security-sensitive operations are logged:

- Authentication attempts (success and failure)
- Authorization failures
- Data modifications (create, update, delete)
- Administrative actions
- Configuration changes
- File uploads/downloads
- Security policy changes

### Log Format

```python
# Example audit log entry
{
    "timestamp": "2025-01-19T10:30:45.123Z",
    "level": "INFO",
    "event_type": "authentication.login",
    "user_id": 12345,
    "username": "jdoe",
    "ip_address": "192.168.1.100",
    "result": "success",
    "metadata": {
        "user_agent": "Mozilla/5.0...",
        "session_id": "abc123..."
    }
}
```

### Log Security

```bash
# Logs are protected with restricted permissions
chmod 640 logs/*.log
chown appuser:loggroup logs/*.log

# Logs are rotated and archived
# See: /etc/logrotate.d/university-system
```

## Deployment Security

### Production Checklist

- [ ] Change all default credentials
- [ ] Set `DEBUG=False` in production
- [ ] Use HTTPS/TLS for all connections
- [ ] Enable firewall and restrict ports
- [ ] Set up intrusion detection
- [ ] Configure automated backups
- [ ] Enable audit logging
- [ ] Use environment variables for secrets
- [ ] Implement rate limiting
- [ ] Set up monitoring and alerts
- [ ] Review and harden file permissions
- [ ] Disable unnecessary services
- [ ] Keep system and dependencies updated

### Default Accounts

The weak demo accounts (`admin` / `admin123` and friends) are seeded **only**
when `EDU_DEV_SEED=true`, which the test suite sets automatically. A fresh
`auth.db` created without that flag is left empty.

To bootstrap a production database with a single strong administrator, set both
of these before first launch:

```bash
EDU_INITIAL_ADMIN_USER=your_admin_username
EDU_INITIAL_ADMIN_PASSWORD=a_password_of_at_least_12_characters
```

Never enable `EDU_DEV_SEED` on a production or internet-facing deployment. See
[`docs/reference/DEFAULT_ACCOUNTS.md`](program/docs/reference/DEFAULT_ACCOUNTS.md)
for the full per-system list of demo accounts.

### Environment Variables

Never hardcode secrets. Use environment variables:

```bash
# .env (NEVER commit this file)
DB_PASSWORD=strong_random_password_here
SMTP_PASSWORD=email_password_here
SECRET_KEY=random_secret_key_for_sessions
API_KEY=external_api_key_here

# .env.example (commit this template)
DB_PASSWORD=your_database_password
SMTP_PASSWORD=your_email_password
SECRET_KEY=your_secret_key
API_KEY=your_api_key
```

`API_SECRET_KEY` and `JWT_SECRET_KEY` fail closed: the unified API refuses to
start in production if they are unset, rather than falling back to an ephemeral
random key that would silently invalidate every session on restart.

### HTTPS Configuration

The reference deployment terminates TLS at nginx (`docker/nginx.conf`): port 80
redirects to 443, TLSv1.2/1.3 only, and the application container is never
published directly. HSTS is emitted by the API for any `APP_ENV` other than
development/test.

For a standalone Flask deployment without a reverse proxy:

```python
if __name__ == '__main__':
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain('cert.pem', 'key.pem')
    app.run(ssl_context=context, host='0.0.0.0', port=443)
```

## Security Best Practices

### For Administrators

1. **Change Default Credentials Immediately** — see
   [Default Accounts](#default-accounts) above
2. **Use Strong Passwords**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, and symbols
   - Avoid common patterns and dictionary words
3. **Enable Audit Logging**
4. **Regular Backups**
   ```bash
   # Automated daily backups
   0 2 * * * /path/to/backup.sh
   ```
5. **Keep System Updated**
   ```bash
   # Check for updates regularly
   git pull origin main
   pip install -r requirements.txt --upgrade
   ```

### For Developers

1. **Input Validation**
   - Validate all user input
   - Use whitelisting over blacklisting
   - Sanitize data before database operations
2. **Use Parameterized Queries**
   - Never concatenate user input into SQL
   - Always use parameter binding
3. **Handle Exceptions Properly**
   - Don't expose stack traces to users
   - Log detailed errors securely
   - Return generic error messages to clients
4. **Secure Configuration**
   - Never commit secrets to version control
   - Use environment variables for sensitive data
   - Keep `.env` files out of repositories
5. **Code Review**
   - All security-related changes require review
   - Use static analysis tools (`make security-scan` runs bandit; CI also runs
     CodeQL and pip-audit)
   - Test security features thoroughly

## Additional Resources

Related documentation:

| Document | Description |
|----------|-------------|
| [Authentication Guide](program/docs/university/security/AUTHENTICATION.md) | Authentication system documentation |
| [Auth Quick Reference](program/docs/university/security/AUTH_QUICK_REFERENCE.md) | Quick reference for auth operations |
| [MFA Documentation](program/docs/university/security/MFA_SYSTEM_DOCUMENTATION.md) | Multi-factor authentication setup and configuration |
| [MFA Quick Start](program/docs/university/security/MFA_QUICK_START.md) | Get MFA running quickly |
| [Default Accounts](program/docs/reference/DEFAULT_ACCOUNTS.md) | Per-system demo account list |

External references:

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

---

**Remember**: Security is everyone's responsibility. When in doubt, ask before
acting.
