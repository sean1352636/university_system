# Security Policy

## Overview

The University Management System takes security seriously. This document outlines our security policies, practices, and guidelines for reporting vulnerabilities.

## Table of Contents

- [Supported Versions](#supported-versions)
- [Security Features](#security-features)
- [Reporting a Vulnerability](#reporting-a-vulnerability)
- [Security Best Practices](#security-best-practices)
- [Authentication & Authorization](#authentication--authorization)
- [Data Protection](#data-protection)
- [Database Security](#database-security)
- [Input Validation](#input-validation)
- [Session Management](#session-management)
- [Error Handling](#error-handling)
- [Audit Logging](#audit-logging)
- [Deployment Security](#deployment-security)

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 5.0.x   | :white_check_mark: |
| 4.x.x   | :white_check_mark: |
| < 4.0   | :x:                |

## Security Features

### Password Security

- **Hashing Algorithm**: PBKDF2-SHA256 with 100,000 iterations
- **Salt**: Unique 32-byte random salt per user
- **Storage**: Passwords are never stored in plaintext
- **Minimum Requirements**: Configurable password complexity rules

```python
# Example from infrastructure/auth/user_authentication.py
def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """
    Hash a password using PBKDF2-SHA256.

    Args:
        password: The password to hash
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (hashed_password, salt) both as hex strings
    """
    if salt is None:
        salt = os.urandom(32)

    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000,  # Number of iterations
        dklen=128
    )

    return key.hex(), salt.hex()
```

### SQL Injection Protection

All database queries use parameterized statements:

```python
# GOOD: Parameterized query
cursor.execute(
    "SELECT * FROM users WHERE username = ? AND active = ?",
    (username, True)
)

# BAD: Never do this
# cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
```

### Transaction Safety

All database operations that modify data use transactions:

```python
with get_db_transaction() as (conn, cursor):
    try:
        # Multiple related operations
        cursor.execute("INSERT INTO ...", (data,))
        cursor.execute("UPDATE ...", (data,))
        # Automatically commits on success
    except Exception as e:
        # Automatically rolls back on error
        raise
```

## Reporting a Vulnerability

We take all security vulnerabilities seriously. If you discover a security issue, please report it responsibly:

### How to Report

1. **DO NOT** open a public GitHub issue
2. Email security reports to: `security@youruniversity.edu`
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

## Security Best Practices

### For Administrators

1. **Change Default Credentials Immediately**
   ```bash
   # Default admin credentials MUST be changed on first login
   Username: admin
   Password: admin123  # CHANGE THIS!
   ```

2. **Use Strong Passwords**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, and symbols
   - Avoid common patterns and dictionary words

3. **Enable Audit Logging**
   ```python
   # In config/app_config.json
   {
     "logging": {
       "audit_enabled": true,
       "audit_level": "INFO",
       "audit_file": "logs/audit.log"
     }
   }
   ```

4. **Regular Backups**
   ```bash
   # Automated daily backups
   0 2 * * * /path/to/university_system/utils/backup.sh
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
   - Use static analysis tools
   - Test security features thoroughly

## Authentication & Authorization

### Authentication Flow

```
1. User submits credentials
2. System retrieves user record by username
3. System extracts stored salt
4. System hashes submitted password with stored salt
5. System compares hashes
6. If match: create session, grant access
7. If no match: return generic error (prevent username enumeration)
```

### Role-Based Access Control (RBAC)

The system implements RBAC with the following roles:

| Role          | Permissions                                      |
|---------------|--------------------------------------------------|
| **Admin**     | Full system access, user management             |
| **Faculty**   | Course management, grading, student records     |
| **Student**   | Personal records, course enrollment, submissions|
| **Staff**     | Module-specific permissions                     |

### Permission Checking

```python
from infrastructure.auth.permissions import require_permission

@require_permission('courses.create')
def create_course(user_id: int, course_data: dict):
    """Only users with 'courses.create' permission can execute."""
    pass
```

### Session Management

- **Session Timeout**: 3600 seconds (1 hour) by default
- **Token Storage**: Secure, HTTP-only cookies for web interface
- **Invalidation**: Immediate logout on password change or account lockout

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
# infrastructure/database/db.py
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
from modules.shared.utils.validators import validate_email, validate_username

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
# infrastructure/auth/user_authentication.py
SESSION_TIMEOUT = 3600  # 1 hour
MAX_CONCURRENT_SESSIONS = 3  # Per user
SESSION_REFRESH_INTERVAL = 900  # 15 minutes
```

### Session Security

- Sessions are invalidated on:
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

### Exception Hierarchy

The system uses a structured exception hierarchy:

```python
# infrastructure/exceptions.py
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

### HTTPS Configuration

```python
# For Flask deployment
if __name__ == '__main__':
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain('cert.pem', 'key.pem')
    app.run(ssl_context=context, host='0.0.0.0', port=443)
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route("/api/login")
@limiter.limit("5 per minute")
def login():
    # Login attempts limited to 5 per minute per IP
    pass
```

## Security Contacts

- **Security Team**: security@youruniversity.edu
- **Emergency Contact**: +1-XXX-XXX-XXXX
- **Security Updates**: https://github.com/yourusername/university-system/security

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Python Security Best Practices](https://python.readthedocs.io/en/latest/library/security_warnings.html)

## Updates

This security policy is reviewed and updated quarterly. Last update: January 2025

---

**Remember**: Security is everyone's responsibility. When in doubt, ask before acting.
