# Security

> This document was extracted from the main [README.md](./README.md). See the README for the full project documentation.
>
> **Reporting Vulnerabilities**: If you discover a security vulnerability, please report it responsibly. Do not open a public issue. Instead, contact the project maintainers directly. See the [Security Documentation](education_system/docs/university_system/security/SECURITY.md) for detailed security guidelines.

---

The system implements comprehensive security measures following industry best practices:

### Password Security
- **bcrypt hashing** as the standard password hash (with transparent migration from legacy PBKDF2-SHA256)
- Legacy PBKDF2-SHA256 passwords (1,000,000 iterations) are automatically re-hashed to bcrypt on first successful login
- Never stores plaintext passwords
- Automatic salt generation and secure random number generation
- Password complexity requirements enforced at registration

### Multi-Factor Authentication
- **TOTP (Time-based One-Time Password)**: Google Authenticator compatible
- **Email OTP**: One-time codes via email (sends to user's configured email)
- **SMS OTP**: Text message verification (optional, via Twilio or free Email-to-SMS gateway)
- **PIN Verification**: 4-digit on-screen PIN for users without MFA setup
- **WebAuthn/FIDO2** (v5.40.0): Passwordless authentication with security keys and platform authenticators
- **Biometric Authentication** (v5.40.0): Face and fingerprint enrollment with 128-D encoding
- **SSO Integration** (v5.40.0): SAML 2.0 and OpenID Connect provider support
- **Account Linking** (v5.40.0): Multi-account support with role switching and audit trails
- **Delegated Access** (v5.40.0): Scoped, time-bound access delegation for parents/guardians
- QR code generation for easy 2FA setup
- Unified login dispatcher routing across all authentication methods

### Login Verification Options

The system offers flexible login security levels to balance security and convenience:

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
from education_system.university_system.infrastructure.auth.mfa_service import MFAService
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
- **Parameterized queries** enforced throughout codebase
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

### Access Control
- **Role-Based Access Control (RBAC)**: Admin, Instructor, Student, Staff, Parent roles
- **Fine-grained permissions**: Over 330 distinct permissions across all modules
- **Permission decorators**: `@require_permission('permission_name')`
- **Global auth context**: Shared authentication state across modules
- **UI-Level Access Control**: Dynamic interface filtering based on user roles

#### Role-Based UI Access Control

All GUI modules implement comprehensive role-based navigation and menu filtering, ensuring users only see features appropriate for their role:

**Admin Users** - Full system access:
- All GUI features unlocked across all modules
- System management and configuration tools
- Export/import data capabilities
- View all records system-wide
- Analytics, reports, and admin panels
- User management and permissions control

**Staff Users** - Operational access:
- Domain-specific management features (teaching, support, health services, etc.)
- Create and edit content within their domain
- View records relevant to their role
- Generate reports and analytics
- Limited to operational tasks (no system-wide administration)

**Student Users** - Self-service access:
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

### Audit Logging
- **Comprehensive activity logs** for all data modifications
- **User attribution** for accountability
- **Timestamp tracking** for compliance
- **Immutable audit trail** for forensic analysis

```python
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Log all data modifications
log_activity('create', 'student', student_id='12345', details={'name': 'John Doe'})
log_activity('update', 'grade', grade_id='456', changes={'old': 'B', 'new': 'A'})
log_activity('delete', 'course', course_id='CS101')
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

**Security Warning**: Change the emergency unlock password in production by setting the `EMERGENCY_UNLOCK_PASSWORD` environment variable.

### Session Management
- **Token-based sessions** with configurable timeouts
- **Concurrent session limits** per user
- **Automatic session cleanup**
- **Session hijacking prevention**

### Error Handling
- **Structured exception hierarchy** preventing information leakage
- **Generic error messages** to users
- **Detailed logging** for administrators
- **No stack traces** in production

### Security Resources

| Document | Description |
|----------|-------------|
| [Security Best Practices](education_system/docs/university_system/security/SECURITY.md) | Comprehensive security features and implementation guidelines |
| [Security Guide](education_system/docs/university_system/security/SECURITY.md) | Security features and implementation guidelines |
| [Authentication Guide](education_system/docs/university_system/security/AUTHENTICATION.md) | Authentication system documentation |
| [MFA Documentation](education_system/docs/university_system/security/MFA_SYSTEM_DOCUMENTATION.md) | Multi-factor authentication setup and configuration |
| [MFA Quick Start](education_system/docs/university_system/security/MFA_QUICK_START.md) | Get MFA running quickly |
