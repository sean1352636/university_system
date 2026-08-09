# Authentication & MFA Guide (Admin)

This guide covers multi-factor authentication setup, user authentication, session management, and security features within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Authentication System](#authentication-system)
- [Password Security](#password-security)
- [Multi-Factor Authentication](#multi-factor-authentication)
- [MFA Methods](#mfa-methods)
- [MFA Enforcement](#mfa-enforcement)
- [Session Management](#session-management)
- [Role-Based Access Control](#role-based-access-control)
- [MFA Admin GUI](#mfa-admin-gui)
- [MFA User GUI](#mfa-user-gui)
- [Security Features](#security-features)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The Authentication & MFA module provides secure user authentication with PBKDF2 password hashing, multi-factor authentication (TOTP, Email OTP, SMS OTP), role-based access control, and advanced session management with suspicious activity detection.

**Key files:**
- Auth: `infrastructure/auth/`
- MFA Service: `infrastructure/auth/mfa_service.py`
- MFA Integration: `infrastructure/auth/mfa_integration.py`
- MFA Enforcement: `infrastructure/auth/mfa_enforcement.py`
- MFA Admin GUI: `infrastructure/auth/mfa_admin_gui.py`
- MFA User GUI: `infrastructure/auth/mfa_gui.py`
- Session Management: `infrastructure/security/session_management.py`
- Shared Context: `infrastructure/shared_context.py`

## Authentication System

### Login Flow

1. User enters username and password
2. System retrieves the user record from the `users` table
3. Password is verified against the stored PBKDF2 hash
4. If password matches, MFA check is performed:
   - If MFA not required: Login succeeds
   - If MFA required and enabled: User must verify with second factor
   - If MFA required but not set up: User enters grace period or must set up
5. On successful authentication, a session is created
6. The global auth context is updated via `shared_context.py`

### Accessing the Auth Instance

```python
from university_system.infrastructure.shared_context import get_auth

auth = get_auth()
if auth.is_logged_in():
    user = auth.get_current_user()
    print(f"Logged in as: {user['username']} ({user['role']})")
```

### Default User Accounts

The system creates default accounts on first initialization:

| Role | Username | Default Password |
|------|----------|-----------------|
| Admin | admin | admin123 |
| Staff | staff | staff123 |
| Student | student | student123 |

Passwords can be configured via environment variables: `DEFAULT_ADMIN_PASSWORD`, `DEFAULT_STAFF_PASSWORD`, `DEFAULT_STUDENT_PASSWORD`.

## Password Security

### Hashing

- **Algorithm**: PBKDF2-SHA256
- **Iterations**: 1,000,000 (OWASP recommended)
- **Salt**: Unique random salt per user
- **Storage**: Hash and salt stored together in the database

### Password Requirements

Enforce strong passwords:
- Minimum length (configurable)
- Complexity requirements (uppercase, lowercase, numbers, special characters)
- Password history (prevent reuse)

### Password Changes

Users can change their password through:
1. CLI: Security settings menu
2. GUI: Account settings dialog
3. Admin: Can reset any user's password

## Multi-Factor Authentication

### MFA Methods

The system supports three MFA methods:

#### TOTP (Time-based One-Time Password)

- Compatible with Google Authenticator, Authy, Microsoft Authenticator
- Generates 6-digit codes that change every 30 seconds
- Uses HMAC-SHA1 algorithm
- Requires `pyotp` library

**Setup Flow:**
1. User selects TOTP method
2. System generates a secret key
3. A QR code is displayed for scanning with an authenticator app
4. User enters the current code to verify setup
5. Backup codes are generated and displayed

#### Email OTP

- Sends a one-time code to the user's registered email
- Code validity: configurable (default: 5-10 minutes)
- Rate limiting to prevent abuse

**Setup Flow:**
1. User selects Email OTP method
2. System verifies the user has a valid email on file
3. A test code is sent
4. User enters the code to verify email delivery works
5. Method is activated

#### SMS OTP

- Sends a one-time code via SMS
- Requires a configured SMS provider
- Code validity: configurable

**Setup Flow:**
1. User selects SMS OTP method
2. System verifies the user has a valid phone number
3. A test code is sent via the SMS provider
4. User enters the code to verify delivery
5. Method is activated

### Backup Codes

When TOTP is set up, the system generates backup codes:
- 8-10 single-use recovery codes
- Used when the primary method is unavailable
- Each code can only be used once
- Store securely offline

### Trusted Devices

After successful MFA verification, users can mark a device as trusted:
- Trusted devices skip MFA for a configurable period
- Device identified by fingerprint (browser, OS, etc.)
- Trust can be revoked by the user or admin

## MFA Enforcement

### Enforcement Policy

MFA can be enforced per role via the `MFAEnforcement` class:

| Setting | Default | Description |
|---------|---------|-------------|
| Required Roles | admin, staff, instructor | Roles that must enable MFA |
| Grace Period | 7 days | Time for new users to set up MFA |
| Enforcement Enabled | true | Master switch for enforcement |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MFA_REQUIRED_ROLES` | admin,staff,instructor | Comma-separated roles |
| `MFA_GRACE_PERIOD_DAYS` | 7 | Grace period in days |
| `MFA_ENFORCEMENT_ENABLED` | true | Enable/disable enforcement |

### Compliance Check Flow

When a user logs in:
1. System checks if their role requires MFA
2. If MFA is already enabled and verified: **Login succeeds**
3. If MFA is required but not enabled:
   - Check grace period (based on account creation date)
   - If in grace period: **Login succeeds with warning**
   - If grace period expired: **Login blocked, must set up MFA**
4. Non-compliant users are logged for audit purposes

### Non-Compliance Reporting

Administrators can view non-compliant users:
- Users who haven't set up MFA past their grace period
- Compliance statistics by role
- Send reminder notifications to non-compliant users

## Session Management

### Session Security

The `SessionManager` class provides advanced session management:

- **Session ID**: Cryptographically secure random token (32 bytes, URL-safe)
- **Storage**: Session ID hash stored in database (never plaintext)
- **Expiration**: Role-based timeout policies

### Session Timeout Policies

| Role | Timeout | Description |
|------|---------|-------------|
| Admin | 30 minutes | Shortest timeout for highest privilege |
| Staff | 60 minutes | Standard staff timeout |
| Instructor | 120 minutes | Extended for teaching sessions |
| Student | 240 minutes | Longest timeout for study sessions |
| Parent | 240 minutes | Same as student |

### Concurrent Session Limits

| Role | Max Sessions | Description |
|------|-------------|-------------|
| Admin | 2 | Strict limit for security |
| Staff | 3 | Standard limit |
| Instructor | 5 | Allows multiple classrooms |
| Student | 3 | Standard limit |
| Parent | 2 | Strict limit |

When a user exceeds their session limit, the oldest session is automatically terminated.

### Suspicious Activity Detection

The system detects suspicious login patterns:

- **Impossible Travel**: Login from a distant location within an unrealistic timeframe (threshold: 800 km/h)
- **Unusual Hours**: Logins during configured off-hours (default: 12am-5am, 11pm-12am)
- **New Device**: First login from an unrecognized device
- **IP Geolocation Changes**: Significant location changes between sessions

When suspicious activity is detected:
1. The login is allowed but flagged
2. Warnings are added to the session record
3. Security alerts are sent (if configured)
4. Events are logged to the immutable audit log

## Role-Based Access Control

### Available Roles

| Role | Description |
|------|-------------|
| Admin | Full system access |
| Staff | Administrative operations |
| Instructor | Academic management |
| Student | Student-facing features |
| Parent | Parent portal access |

### Permission Checking

Use decorators or inline checks:

```python
# Decorator approach
from university_system.infrastructure.auth.authorization import require_permission

@require_permission('manage_students')
def edit_student_record(student_id):
    pass

# Inline approach
auth = get_auth()
if auth.check_permission('edit_grades'):
    # Proceed with operation
    pass
else:
    raise PermissionError("Access denied")
```

### Common Permissions

| Permission | Admin | Staff | Instructor | Student |
|-----------|-------|-------|------------|---------|
| `manage_students` | Yes | Yes | No | No |
| `view_students` | Yes | Yes | Yes | No |
| `edit_grades` | Yes | No | Yes | No |
| `view_own_record` | Yes | Yes | Yes | Yes |
| `manage_schedules` | Yes | Yes | Yes | No |
| `manage_finances` | Yes | Limited | No | No |
| `system_config` | Yes | No | No | No |

## MFA Admin GUI

The MFA Admin GUI provides a management interface for administrators:

### Features

- **User MFA Status Dashboard**: View MFA status for all users
- **Enable/Disable MFA**: Toggle MFA for specific users
- **Reset MFA**: Reset a user's MFA configuration
- **View Backup Codes**: Generate new backup codes for users
- **Compliance Report**: See enforcement compliance statistics
- **Bulk Operations**: Enable or reset MFA for multiple users
- **Audit Log**: View MFA-related security events

### Accessing the Admin GUI

The MFA Admin GUI is accessible from the main administration panel under Security settings.

## MFA User GUI

The MFA User GUI allows individual users to manage their own MFA:

### Features

- **Setup MFA**: Choose and configure an MFA method
- **QR Code Display**: Scan to add TOTP to authenticator app
- **Verify Setup**: Enter a code to confirm method works
- **View Backup Codes**: Display one-time recovery codes
- **Change Method**: Switch between TOTP, Email, or SMS
- **Disable MFA**: Turn off MFA (if not enforced for role)
- **Manage Trusted Devices**: View and revoke trusted devices

### Setup Wizard

The setup wizard guides users through MFA configuration:
1. Choose method (TOTP recommended)
2. Follow method-specific setup steps
3. Verify with a test code
4. Save backup codes
5. Confirmation

## Security Features

### Rate Limiting

The system includes rate limiting for security:

- **Login Attempts**: Configurable limit (default: 5 attempts)
- **Lockout Duration**: Temporary account lockout after failed attempts
- **MFA Attempts**: Separate limit for MFA verification failures
- **MFA Lockout**: 15-minute lockout after multiple failed MFA attempts

### Data Encryption

The security module (`infrastructure/security/data_encryption.py`) provides:
- Field-level encryption for sensitive data
- Encryption key management
- Secure storage patterns

### Immutable Audit Log

Critical security events are logged to an immutable audit log:
- Login attempts (success and failure)
- MFA setup and verification
- Permission changes
- Session creation and termination
- Suspicious activity detections

### Security Dashboard

The security dashboard CLI (`infrastructure/security/security_dashboard_cli.py`) provides:
- Active session monitoring
- Failed login attempt tracking
- Security event timeline
- Compliance status overview

## Configuration

### Authentication Settings

| Setting | Location | Description |
|---------|----------|-------------|
| Password hashing iterations | Auth module | PBKDF2 iteration count |
| Session timeout | SessionManager | Per-role timeout values |
| Concurrent session limit | SessionManager | Per-role session limits |
| MFA required roles | Environment/MFAEnforcement | Roles requiring MFA |
| Grace period | Environment/MFAEnforcement | Days before MFA enforced |
| Rate limit threshold | Rate limiter | Max failed attempts |
| Lockout duration | Rate limiter | Account lockout time |

### Email OTP Settings

Configure the email OTP service in `infrastructure/auth/email_otp_service.py`:
- SMTP server details
- OTP validity period
- Email template
- Rate limiting

### SMS Provider Settings

Configure the SMS provider in `infrastructure/auth/sms_provider.py`:
- Provider API credentials
- Phone number validation
- Message templates
- Delivery retry settings

## Troubleshooting

### User Locked Out of MFA

**Problem**: User cannot access their authenticator app or backup codes.

**Solution**:
1. Admin navigates to MFA Admin GUI
2. Selects the user
3. Clicks **Reset MFA**
4. User's MFA is disabled
5. User can log in with password only
6. User sets up MFA again from their account settings

### MFA Code Not Working

**Problem**: TOTP codes are rejected.

**Possible Causes**:
1. **Time sync**: Ensure the authenticator app's device has accurate time
2. **Wrong account**: Verify the correct account is selected in the app
3. **Clock drift**: TOTP allows a small window (typically +/- 30 seconds)

**Solution**: If codes consistently fail, reset MFA and re-enroll.

### Email OTP Not Received

**Problem**: Email verification codes not arriving.

**Solutions**:
1. Check spam/junk folders
2. Verify the email address on file is correct
3. Check SMTP configuration
4. Verify email service is running
5. Check email service logs for delivery errors

### Session Expired Unexpectedly

**Problem**: User gets logged out before expected timeout.

**Possible Causes**:
1. Concurrent session limit reached (oldest session terminated)
2. Admin manually terminated the session
3. Server restart cleared sessions
4. Session timeout configured shorter than expected

**Solution**: Check session limits for the user's role and verify no other sessions are active.

### Cannot Login After Password Change

**Problem**: Login fails after password change.

**Solutions**:
1. Ensure the new password was saved (check for error messages during change)
2. Clear browser cache and cookies
3. Try the new password, not the old one
4. If using a password manager, update the stored password
5. Admin can reset the password if needed
