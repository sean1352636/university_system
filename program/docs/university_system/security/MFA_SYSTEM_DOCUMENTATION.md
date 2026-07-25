# Multi-Factor Authentication (MFA) System Documentation

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Quick Start](#quick-start)
6. [User Guide](#user-guide)
7. [Admin Guide](#admin-guide)
8. [Integration Guide](#integration-guide)
9. [API Reference](#api-reference)
10. [Configuration](#configuration)
11. [Security Considerations](#security-considerations)
12. [Troubleshooting](#troubleshooting)

---

## 🔒 Overview

The Multi-Factor Authentication (MFA) system provides comprehensive second-factor authentication for the University Management System. It adds an additional layer of security beyond passwords to protect sensitive academic data and user accounts.

### Key Benefits

- **Enhanced Security**: Protect accounts even if passwords are compromised
- **Multiple Methods**: Support for TOTP, SMS, and Email verification
- **Flexible Enforcement**: Role-based MFA requirements with grace periods
- **User Convenience**: Device trust/remember options
- **Compliance Ready**: Audit trails and comprehensive logging

---

## ✨ Features

### 1. **Authentication Methods**

#### 📱 TOTP (Authenticator App)
- Works with Google Authenticator, Microsoft Authenticator, Authy
- Offline verification capability
- QR code setup for easy configuration
- Most secure option

#### 📲 SMS OTP
- Send verification codes via text message
- Convenient for users with mobile phones
- Configurable provider support (Twilio, AWS SNS, Mock)

#### 📧 Email OTP
- Send verification codes via email
- Universal access (no phone needed)
- HTML email templates

### 2. **Backup & Recovery**

- **Recovery Codes**: 10 single-use backup codes generated during setup
- **Code Regeneration**: Admins can regenerate codes for users
- **Expiration**: Configurable code expiration (default: 1 year)

### 3. **Device Trust**

- **Remember Device**: Trust devices for up to 30 days (configurable)
- **Device Fingerprinting**: Unique device identification
- **Revocation**: Users and admins can revoke trusted devices
- **Security Tokens**: Secure token-based device verification

### 4. **Enforcement Policies**

- **Role-Based Requirements**: Different policies per role (admin, staff, student, etc.)
- **Grace Periods**: Configurable time to enable MFA (default: 3-30 days by role)
- **Flexible Enforcement**: Optional vs. required MFA per role
- **Minimum Methods**: Require users to set up multiple methods

### 5. **Security Features**

- **Lockout Protection**: Temporary account lockout after 5 failed MFA attempts
- **Attempt Tracking**: Monitor and log all verification attempts
- **Audit Trail**: Complete logging of all MFA events
- **Code Expiration**: OTP codes expire after 10 minutes
- **Max Attempts**: Limit verification attempts per code (default: 3)

### 6. **Administrative Tools**

- **Admin Dashboard**: Comprehensive MFA management panel
- **User Management**: View and manage user MFA status
- **Policy Configuration**: Configure enforcement policies per role
- **Audit Logs**: Export and review verification attempts
- **Statistics**: Real-time MFA usage statistics

---

## 🏗️ Architecture

### Database Schema

The MFA system uses 7 dedicated tables:

```
mfa_methods              → User's enabled MFA methods
mfa_otp_codes           → Active SMS/Email OTP codes
mfa_trusted_devices     → Trusted device records
mfa_enforcement_policies → Role-based enforcement rules
mfa_user_settings       → Per-user MFA configuration
mfa_verification_attempts → Audit trail
mfa_recovery_codes      → Backup recovery codes
```

### Component Structure

```
university_system/infrastructure/auth/
├── mfa_service.py           # Core MFA service logic
├── mfa_gui.py              # GUI components (setup/verification)
├── mfa_admin_gui.py        # Admin management panel
├── mfa_integration.py      # Integration helpers
├── sms_provider.py         # SMS OTP delivery
└── email_otp_service.py    # Email OTP delivery

university_system/infrastructure/database/migrations/
└── add_mfa_system.py       # Database migration script
```

---

## 📦 Installation

### 1. Install Dependencies

```bash
# Using pip
pip install pyotp qrcode[pil] pillow

# Or using requirements.txt
pip install -r requirements.txt
```

**Required packages:**
- `pyotp>=2.6.0` - TOTP implementation
- `qrcode>=7.3.0` - QR code generation
- `Pillow>=8.3.0` - Image processing for QR codes

**Optional packages (for production):**
- `twilio` - For Twilio SMS provider
- `boto3` - For AWS SNS/SES providers

### 2. Run Database Migration

```bash
python3 university_system/infrastructure/database/migrations/add_mfa_system.py
```

This creates all necessary MFA tables and populates default enforcement policies.

### 3. Verify Installation

```bash
python3 test_mfa_simple.py
```

You should see all checks passing with ✓ marks.

---

## 🚀 Quick Start

### For Users

#### Setting Up MFA

1. **Navigate to Security Settings** in your account
2. **Click "Enable MFA"** or follow the setup prompt after login
3. **Choose Your Methods**:
   - **Authenticator App** (recommended):
     - Scan QR code with your authenticator app
     - Enter the 6-digit code to verify
   - **SMS** (optional):
     - Enter your phone number
     - Verify with the code sent to your phone
   - **Email** (optional):
     - Verify your email address
     - Use email codes as backup

4. **Save Recovery Codes**:
   - Download and securely store your 10 recovery codes
   - Each code works only once
   - Use them if you lose access to your MFA device

5. **Complete Setup**:
   - MFA is now enabled on your account
   - You'll be prompted for verification on next login

#### Logging In with MFA

1. **Enter Username & Password** as usual
2. **MFA Verification**:
   - Enter code from your authenticator app, or
   - Request and enter SMS/Email code, or
   - Use a recovery code if needed

3. **Optional: Trust Device**
   - Check "Trust this device for 30 days"
   - Skip MFA on this device for the trust period

### For Administrators

#### Quick Admin Access

```python
# Show MFA admin panel
from university_system.infrastructure.auth.mfa_admin_gui import show_mfa_admin

show_mfa_admin(parent_window, admin_user_id=1)
```

---

## 👤 User Guide

### Managing Your MFA Methods

#### View Active Methods

```python
from university_system.infrastructure.auth.mfa_service import MFAService

service = MFAService()
methods = service.get_user_mfa_methods(user_id)

for method in methods['methods']:
    print(f"{method['type']}: {method['identifier']}")
```

#### Add New Method

1. Go to **Account Settings** → **Security**
2. Click **"Add MFA Method"**
3. Follow setup wizard for chosen method
4. Verify with a test code

#### Remove Method

⚠️ **Warning**: Always keep at least one MFA method active!

1. Go to **Account Settings** → **Security**
2. Click **"Manage MFA Methods"**
3. Select method to remove
4. Confirm removal

### Managing Trusted Devices

#### View Trusted Devices

```python
devices = service.get_trusted_devices(user_id)

for device in devices['devices']:
    print(f"{device['device_name']} - Last used: {device['last_used_at']}")
```

#### Revoke Device Trust

```python
service.revoke_trusted_device(user_id, device_id)
```

### Using Recovery Codes

1. **When to Use**:
   - Lost your phone/authenticator device
   - Can't receive SMS or email
   - Emergency access needed

2. **How to Use**:
   - On MFA verification screen, click "Use Recovery Code"
   - Enter one of your recovery codes (format: XXXX-XXXX)
   - Code will be marked as used

3. **After Using Recovery Codes**:
   - Set up new MFA methods immediately
   - Generate new recovery codes
   - Old codes become invalid after a few uses

---

## 🛡️ Admin Guide

### Accessing Admin Panel

```python
from university_system.infrastructure.auth.mfa_admin_gui import show_mfa_admin
import tkinter as tk

root = tk.Tk()
show_mfa_admin(root, admin_user_id=your_admin_id)
root.mainloop()
```

### Managing MFA Policies

#### Default Policies

| Role       | Required | Min Methods | Grace Period | Device Trust |
|------------|----------|-------------|--------------|--------------|
| Admin      | Yes      | 2           | 3 days       | 30 days      |
| Staff      | Yes      | 1           | 7 days       | 30 days      |
| Instructor | No       | 1           | 14 days      | 30 days      |
| Student    | No       | 1           | 30 days      | 90 days      |
| Parent     | No       | 1           | 30 days      | 90 days      |

#### Modifying Policies

```python
# Update enforcement policy (via database)
import sqlite3

conn = sqlite3.connect('path/to/university.db')
cursor = conn.cursor()

cursor.execute("""
    UPDATE mfa_enforcement_policies
    SET mfa_required = 1,
        minimum_methods = 2,
        grace_period_days = 7
    WHERE role_name = 'instructor'
""")

conn.commit()
conn.close()
```

### Managing Users

#### View User MFA Status

```python
service = MFAService()

# Check if user has MFA enabled
methods = service.get_user_mfa_methods(user_id)
is_enabled = len(methods.get('methods', [])) > 0
```

#### Reset User MFA

```python
# Disable all MFA methods for a user
service.disable_mfa(user_id)

# User will need to set up MFA again
```

#### Force MFA Setup

```python
# Set enforcement deadline
from datetime import datetime, timedelta

conn = sqlite3.connect('path/to/university.db')
cursor = conn.cursor()

deadline = datetime.now() + timedelta(days=3)

cursor.execute("""
    INSERT INTO mfa_user_settings (user_id, enforcement_deadline)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET enforcement_deadline = ?
""", (user_id, deadline, deadline))

conn.commit()
conn.close()
```

#### Grant Temporary MFA Bypass

```python
# Bypass MFA for 24 hours (emergency access)
from datetime import datetime, timedelta

bypass_until = datetime.now() + timedelta(hours=24)

cursor.execute("""
    UPDATE mfa_user_settings
    SET bypass_until = ?
    WHERE user_id = ?
""", (bypass_until, user_id))

conn.commit()
```

### Monitoring & Audit

#### View Recent Verification Attempts

```python
import sqlite3

conn = sqlite3.connect('path/to/university.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT u.username, v.method_type, v.success, v.attempted_at
    FROM mfa_verification_attempts v
    JOIN users u ON v.user_id = u.id
    WHERE v.attempted_at > datetime('now', '-24 hours')
    ORDER BY v.attempted_at DESC
    LIMIT 50
""")

for row in cursor.fetchall():
    print(row)
```

#### Export Audit Log

Use the Admin Panel's "Export Audit Log" feature, or:

```python
cursor.execute("""
    SELECT * FROM mfa_verification_attempts
    ORDER BY attempted_at DESC
""")

# Export to CSV...
```

#### Monitor Failed Attempts

```python
# Get users with multiple failed attempts
cursor.execute("""
    SELECT user_id, COUNT(*) as failed_count
    FROM mfa_verification_attempts
    WHERE success = 0
      AND attempted_at > datetime('now', '-1 hour')
    GROUP BY user_id
    HAVING failed_count >= 3
""")

for user_id, count in cursor.fetchall():
    print(f"User {user_id}: {count} failed attempts")
```

---

## 🔧 Integration Guide

### Integrating into Login Flow

#### Basic Integration

```python
from university_system.infrastructure.auth.mfa_integration import integrate_mfa_check

class UserAuth:
    def login(self, username, password):
        # Step 1: Verify password (existing code)
        if not self.verify_password(username, password):
            return {'success': False, 'error': 'Invalid credentials'}

        user_id = self.get_user_id(username)
        role = self.get_user_role(user_id)

        # Step 2: MFA check (NEW)
        mfa_result = integrate_mfa_check(user_id, role)

        # Step 3: Handle MFA actions
        if mfa_result['action'] == 'locked':
            return {
                'success': False,
                'locked': True,
                'message': mfa_result['message']
            }

        elif mfa_result['action'] == 'require_mfa':
            return {
                'success': False,
                'mfa_required': True,
                'user_id': user_id,
                'username': username
            }

        elif mfa_result['action'] == 'require_setup':
            return {
                'success': False,
                'mfa_setup_required': True,
                'user_id': user_id,
                'username': username
            }

        elif mfa_result['action'] == 'allow':
            # Proceed with login
            return {
                'success': True,
                'user_id': user_id,
                'session_id': self.create_session(user_id)
            }
```

#### GUI Integration

```python
from university_system.infrastructure.auth.mfa_integration import (
    show_mfa_for_login,
    show_mfa_setup_for_login
)

class LoginDialog:
    def on_login_button_clicked(self):
        result = self.auth.login(username, password)

        if result.get('mfa_required'):
            # Show MFA verification dialog
            verified, trust_token = show_mfa_for_login(
                self,
                result['user_id'],
                result['username']
            )

            if verified:
                # Complete login
                self.complete_login(result['user_id'])
            else:
                messagebox.showerror("Error", "MFA verification failed")

        elif result.get('mfa_setup_required'):
            # Show MFA setup wizard
            completed = show_mfa_setup_for_login(
                self,
                result['user_id'],
                result['username'],
                required=True
            )

            if completed:
                messagebox.showinfo("Success", "Please log in again")
            else:
                messagebox.showerror("Error", "MFA setup required")

        elif result['success']:
            self.complete_login(result['user_id'])
```

### Adding MFA to Sensitive Operations

```python
def perform_sensitive_operation(user_id):
    """Require MFA verification for sensitive operations"""

    # Check if MFA verification needed
    service = MFAService()

    # Get last verification time
    conn = sqlite3.connect(service.db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT last_successful_verification
        FROM mfa_user_settings
        WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()
    conn.close()

    if result:
        last_verified = datetime.fromisoformat(result[0])
        time_since_verification = datetime.now() - last_verified

        # Require re-verification if more than 30 minutes
        if time_since_verification > timedelta(minutes=30):
            # Show verification dialog
            verified = show_mfa_verification_dialog(user_id)

            if not verified:
                return {'success': False, 'error': 'MFA verification required'}

    # Proceed with sensitive operation
    return perform_operation()
```

---

## 📚 API Reference

### MFAService Class

#### TOTP Methods

```python
service = MFAService(db_path=None)

# Setup TOTP
result = service.setup_totp(user_id, username, issuer="University System")
# Returns: {'success': bool, 'secret': str, 'qr_code': bytes, 'recovery_codes': list}

# Verify TOTP
result = service.verify_totp(user_id, code, device_id=None)
# Returns: {'success': bool, 'method': str, 'trust_token': str}
```

#### SMS Methods

```python
# Generate SMS OTP
result = service.generate_sms_otp(user_id, phone_number)
# Returns: {'success': bool, 'code': str, 'expires_at': str}

# Verify SMS OTP
result = service.verify_sms_otp(user_id, code, device_id=None)
# Returns: {'success': bool, 'method': str, 'trust_token': str}
```

#### Email Methods

```python
# Generate Email OTP
result = service.generate_email_otp(user_id, email)
# Returns: {'success': bool, 'code': str, 'expires_at': str}

# Verify Email OTP
result = service.verify_email_otp(user_id, code, device_id=None)
# Returns: {'success': bool, 'method': str, 'trust_token': str}
```

#### Recovery Code Methods

```python
# Generate recovery codes
result = service.generate_recovery_codes(user_id)
# Returns: {'success': bool, 'codes': list}

# Verify recovery code
result = service.verify_recovery_code(user_id, code, device_id=None)
# Returns: {'success': bool, 'method': str, 'remaining_codes': int}
```

#### Device Trust Methods

```python
# Verify trusted device
result = service.verify_trusted_device(user_id, device_id, trust_token)
# Returns: {'success': bool, 'trusted': bool}

# Revoke device trust
result = service.revoke_trusted_device(user_id, device_id)
# Returns: {'success': bool}

# Get trusted devices
result = service.get_trusted_devices(user_id)
# Returns: {'success': bool, 'devices': list}
```

#### User Management Methods

```python
# Get user's MFA methods
result = service.get_user_mfa_methods(user_id)
# Returns: {'success': bool, 'methods': list}

# Enable MFA
result = service.enable_mfa(user_id)
# Returns: {'success': bool}

# Disable MFA
result = service.disable_mfa(user_id)
# Returns: {'success': bool}

# Check if locked
is_locked = service.is_mfa_locked(user_id)
# Returns: bool
```

#### Policy Methods

```python
# Check MFA requirement
result = service.check_mfa_required(user_id, role)
# Returns: {'success': bool, 'required': bool, 'allowed_methods': list, ...}
```

---

## ⚙️ Configuration

### SMS Provider Configuration

Create `university_system/config/sms_config.json`:

```json
{
  "primary_provider": "twilio",
  "fallback_provider": "mock",
  "twilio": {
    "account_sid": "your_account_sid",
    "auth_token": "your_auth_token",
    "from_number": "+1234567890"
  }
}
```

Or use environment variables:

```bash
export SMS_PRIMARY_PROVIDER="twilio"
export TWILIO_ACCOUNT_SID="your_sid"
export TWILIO_AUTH_TOKEN="your_token"
export TWILIO_PHONE_NUMBER="+1234567890"
```

### Email Provider Configuration

Create `university_system/config/email_config.json`:

```json
{
  "primary_provider": "smtp",
  "smtp": {
    "server": "smtp.gmail.com",
    "port": 587,
    "username": "your_email@gmail.com",
    "password": "your_app_password",
    "from_email": "noreply@university.edu",
    "from_name": "University System"
  }
}
```

Or use environment variables:

```bash
export EMAIL_PRIMARY_PROVIDER="smtp"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your_email@gmail.com"
export SMTP_PASSWORD="your_app_password"
```

### MFA Service Configuration

Modify `mfa_service.py` constants:

```python
self.otp_expiry_minutes = 10      # OTP code expiration
self.max_otp_attempts = 3         # Max attempts per code
self.device_trust_days = 30       # Device trust duration
```

---

## 🔐 Security Considerations

### Best Practices

1. **Password Hashing**:
   - All OTP codes and recovery codes are hashed before storage
   - Uses SHA-256 for code hashing
   - TOTP secrets encrypted in database

2. **Rate Limiting**:
   - Max 3 attempts per OTP code
   - 15-minute lockout after 5 failed MFA attempts
   - Automatic code invalidation after max attempts

3. **Code Expiration**:
   - OTP codes expire after 10 minutes
   - Recovery codes expire after 1 year
   - Device trust expires after 30 days (configurable)

4. **Audit Trail**:
   - All verification attempts logged
   - Includes timestamp, IP address, device ID
   - Failed attempts tracked separately

5. **Device Fingerprinting**:
   - Unique device identification
   - Secure token-based verification
   - Revocable device trust

### Recommendations

#### For Administrators

- ✅ Require MFA for all admin and staff roles
- ✅ Set minimum 2 methods for admins
- ✅ Regularly review audit logs
- ✅ Monitor failed verification attempts
- ✅ Use short grace periods (3-7 days)
- ✅ Enable device trust expiration
- ✅ Regular security audits

#### For Users

- ✅ Use TOTP (authenticator app) as primary method
- ✅ Set up at least 2 MFA methods
- ✅ Save recovery codes in secure location
- ✅ Don't share codes with anyone
- ✅ Use device trust on personal devices only
- ✅ Revoke trust when selling/losing devices
- ✅ Generate new recovery codes after using several

#### For Developers

- ✅ Always hash sensitive codes before storage
- ✅ Use parameterized queries (prevent SQL injection)
- ✅ Log all security events
- ✅ Implement rate limiting
- ✅ Validate input thoroughly
- ✅ Use HTTPS in production
- ✅ Keep dependencies updated

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "Module 'pyotp' not found"

**Solution**:
```bash
pip install pyotp qrcode[pil] pillow
# or
pip install -r requirements.txt
```

#### 2. "QR Code not displaying"

**Solution**:
- Ensure Pillow is installed: `pip install Pillow`
- Check tkinter image support
- Try regenerating the QR code

#### 3. "SMS/Email not sending"

**Solution**:
- Check provider configuration
- Verify environment variables
- Test provider connectivity
- Check logs for errors
- Use mock provider for testing

#### 4. "Invalid TOTP code (always fails)"

**Solution**:
- Check device clock synchronization
- TOTP requires accurate time
- Try with valid_window=2 for more tolerance
- Verify secret is correctly stored

#### 5. "User locked out of account"

**Solution (Admin)**:
```python
# Reset lockout
conn = sqlite3.connect('path/to/university.db')
cursor = conn.cursor()
cursor.execute("""
    UPDATE mfa_user_settings
    SET locked_until = NULL, failed_attempts = 0
    WHERE user_id = ?
""", (user_id,))
conn.commit()
```

#### 6. "Lost MFA device - can't login"

**Solution**:
1. Use recovery code
2. Contact admin for MFA reset
3. Set up new MFA methods
4. Generate new recovery codes

#### 7. "Database migration failed"

**Solution**:
```bash
# Check database path
# Run migration manually
python3 university_system/infrastructure/database/migrations/add_mfa_system.py /path/to/database.db

# Check for errors in output
```

### Debug Mode

Enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('mfa_system')

# Service will now log detailed information
```

### Getting Help

1. Check this documentation
2. Review error messages in logs
3. Test with mock providers
4. Check database tables for data
5. Verify all dependencies installed
6. Contact system administrator

---

## 📝 Change Log

### Version 1.0 (Current)

**Features**:
- ✅ TOTP authentication
- ✅ SMS OTP
- ✅ Email OTP
- ✅ Recovery codes
- ✅ Device trust
- ✅ Role-based enforcement
- ✅ Admin panel
- ✅ Comprehensive audit logging

**Coming Soon** (Future Versions):
- 🔜 WebAuthn/FIDO2 support
- 🔜 Biometric authentication
- 🔜 Push notifications
- 🔜 Risk-based authentication
- 🔜 Geolocation tracking
- 🔜 Advanced analytics dashboard

---

## 📜 License

Part of the University Management System.
See main project license for details.

---

## 👥 Credits

Developed for the University Management System MFA enhancement project.

**Technologies Used**:
- PyOTP - TOTP implementation
- QRCode - QR code generation
- SQLite - Data storage
- Tkinter - GUI framework
- Python 3.8+ - Core platform

---

## 📞 Support

For issues, questions, or feature requests:
- Check the Troubleshooting section
- Review the Integration Guide
- Contact your system administrator
- Refer to the API Reference

---

**Last Updated**: 2025-10-21
**Documentation Version**: 1.0
