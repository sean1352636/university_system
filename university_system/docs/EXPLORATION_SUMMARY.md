# University System Codebase - Authentication Architecture Exploration Summary

**Date**: October 21, 2025  
**System Version**: 5.0.0  
**Python Requirements**: 3.8+

---

## Overview

A comprehensive exploration of the University Management System's authentication architecture has been completed. The system implements a production-grade, multi-layered authentication system with support for role-based access control (RBAC), two-factor authentication (2FA), session management, and comprehensive audit logging.

---

## Key Findings

### 1. Authentication System Implementation

#### Core Module
- **Location**: `/home/seancatchpole989/university_system/infrastructure/auth/user_authentication.py`
- **Size**: 4,900+ lines of Python code
- **Main Class**: `UserAuth` (defined at line 1661)

#### Key Authentication Methods
| Method | Line | Purpose |
|--------|------|---------|
| `login()` | 4012 | Primary authentication method |
| `_hash_password()` | 1989 | PBKDF2-SHA256 password hashing |
| `enable_two_fa()` | 3240 | Setup TOTP 2FA with QR codes |
| `verify_two_fa_code()` | 3339 | Validate OTP codes |
| `_log_login_attempt()` | 3975 | Audit trail for login attempts |
| `_init_db()` | 2009 | Database schema initialization |

#### Session Management Configuration
```
session_timeout = 30 minutes (default)
max_login_attempts = 5
lockout_time = 15 minutes
current_user = None (tracks logged-in user)
last_activity = None (tracks session activity)
```

---

### 2. User/Role Management Structure

#### Five Primary Roles
1. **Admin** - Full system access (100+ permissions)
2. **Staff** - Student records, reports, grading (50+ permissions)
3. **Student** - Own records, assignments, grades (40+ permissions)
4. **Instructor** - Module management, grading (30+ permissions)
5. **Parent** - Child records access (15+ permissions)

#### Role Definition Location
**File**: `/home/seancatchpole989/university_system/infrastructure/auth/user_authentication.py`
**Lines**: 562-568

```python
ROLES = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records'
}
```

#### Permission System
**Location**: Lines 571-662+
- **100+ distinct permissions** organized by category
- Granular permission assignment per role
- Individual user-level permission overrides supported
- Permission categories: Academic, Administrative, Financial, Grading, Attendance, AI/Plagiarism, Parking, Health, Library, Trips

---

### 3. Database Schema for Users

#### Core Tables (8 main authentication tables)

| Table Name | Purpose | Key Fields |
|------------|---------|-----------|
| `users` | User profiles | id, username, email, role, student_id |
| `user_accounts` | Auth credentials | password_hash, salt, two_fa_secret, is_active |
| `two_fa_recovery_codes` | 2FA backup codes | code_hash, is_used, created_at |
| `roles` | Role definitions | role_name, description |
| `permissions` | Permission catalog | permission_name, description |
| `role_permissions` | Role-permission mapping | role_id, permission_id |
| `login_attempts` | Login audit log | username, success, ip_address, attempt_time |
| `activity_log` | Action audit trail | user_id, action, details, timestamp |

#### Database Location
**Path**: `/home/seancatchpole989/university_system/data/db_files/university_system.db`

#### Database Configuration
**File**: `/home/seancatchpole989/university_system/infrastructure/database/constants.py`
- Timeout: 5.0 seconds
- SQLite Busy Timeout: 30,000 milliseconds
- Journal Mode: WAL (Write-Ahead Logging)
- Foreign Keys: Enabled
- Synchronous: NORMAL

---

### 4. Login/Authentication Logic

#### Authentication Flow (6 Steps)

1. **Account Lockout Check** (Lines 4028-4045)
   - Verify max attempts not exceeded
   - Check lockout period expiration
   - Return error if locked

2. **Credential Query** (Lines 4047-4149)
   - Query user_accounts + users tables
   - Handle missing user profiles
   - Auto-create missing profiles if needed

3. **Password Verification** (Lines 4160-4180)
   - Fetch stored hash and salt
   - Hash provided password with PBKDF2-SHA256
   - Compare hashes

4. **Account Status Check** (Lines 4180-4195)
   - Verify is_active flag
   - Check password_reset_required flag
   - Log successful attempt

5. **2FA Check** (Lines 4195-4196)
   - If two_fa_enabled, return 2FA requirement
   - Otherwise proceed to complete login

6. **Session Establishment** (Lines 4197+)
   - Set current_user with user info
   - Update last_login timestamp
   - Log activity

#### Password Hashing Details

**Algorithm**: PBKDF2-SHA256
**Iterations**: 1,000,000 (OWASP 2021+ standard)
**Salt**: 16 random bytes (32-char hex = 128 bits)
**Output**: 64 bytes, hexadecimal encoded
**Location**: Line 1989

```python
def _hash_password(self, password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        1_000_000,  # HIGH iteration count
        dklen=64
    )
    return salt, key.hex()
```

#### Two-Factor Authentication Implementation

**Library**: `pyotp` (version 2.6.0+)

**2FA Setup Process** (Method at line 3240):
1. Generate base32 secret using `pyotp.random_base32()`
2. Create TOTP provisioning URI
3. Generate QR code using `qrcode` library
4. Generate 10 single-use recovery codes
5. Store secret and recovery codes in database
6. Return QR code and recovery codes

**2FA Verification** (Method at line 3339):
1. Fetch 2FA secret from database
2. Create TOTP instance
3. Verify code against current time window (±1 step = 60 seconds)
4. If code invalid, check recovery codes
5. Mark used recovery code, regenerate all codes

---

### 5. Dependencies - Complete List

#### Authentication-Specific
- **pyotp** (>=2.6.0) - TOTP/HOTP implementation
- **qrcode** (>=7.3.0) - QR code generation
- **cryptography** (>=3.4.8) - Cryptographic operations
- **bcrypt** (>=3.2.0) - Available but not used (PBKDF2 preferred)

#### Core/Built-In
- **sqlite3** - Database (built-in)
- **hashlib** - Secure hashing (built-in)
- **secrets** - Cryptographic randomness (built-in)
- **json** - Configuration/serialization (built-in)
- **logging** - Audit logging (built-in)
- **datetime** - Timestamp management (built-in)
- **threading** - Session management (built-in)

#### GUI Framework
- **tkinter** - GUI toolkit (usually included)
- **ttk** - Themed widgets (tkinter extension)

#### Optional/Additional
- **flask** (>=2.0.0) - Web API framework (optional)
- **requests** (>=2.27.0) - HTTP client
- **PyYAML** (>=6.0) - Configuration parsing

#### Project Configuration
**File**: `/home/seancatchpole989/requirements.txt` (5,964 bytes)
**File**: `/home/seancatchpole989/pyproject.toml` (6,840 bytes)

---

### 6. Login GUI Components

#### GUI Login Screen

**Location**: `/home/seancatchpole989/university_system/modules/shared/gui/main_gui.py`

**Method**: `show_login_screen()` - Line 1522
- Creates login form with username/password fields
- Displays default credentials information
- Provides login button with keyboard bindings

**Method**: `perform_login()` - Line 1575
- Retrieves credentials from entry widgets
- Calls `self.auth.login(username, password)`
- Handles 3 outcomes: Success, 2FA Required, Failure
- Updates UI with error/success messages

**Method**: `logout_user()` - Line 1634
- Ends user session
- Updates UI
- Returns to login screen

#### GUI Components Used
- `ttk.LabelFrame` - Form container
- `ttk.Entry` - Username/password fields
- `ttk.Button` - Login button
- `ttk.Label` - Labels and info display

#### Authentication Integration
**Global auth instance**: `auth = None`
**Set method**: `set_auth(auth_instance)`
**Current user**: `self.auth.current_user`
**Last activity**: `self.auth.last_activity`

---

### 7. Configuration Files

#### Database Configuration
**File**: `/home/seancatchpole989/university_system/infrastructure/database/constants.py`
- DEFAULT_DB_TIMEOUT: 5.0 seconds
- SQLITE_BUSY_TIMEOUT: 30000 milliseconds
- PRAGMA_FOREIGN_KEYS: "ON"
- PRAGMA_JOURNAL_MODE: "WAL"
- PRAGMA_SYNCHRONOUS: "NORMAL"
- MAX_POOL_CONNECTIONS: 5
- MIN_POOL_CONNECTIONS: 2

#### Chatbot Configuration
**File**: `/home/seancatchpole989/university_system/data/chatbot/chatbot_config.json`
```json
{
    "security": {
        "jwt_secret": "[32-char hex]",
        "session_timeout": 3600,
        "max_login_attempts": 3
    }
}
```

#### Path Constants
**File**: `/home/seancatchpole989/university_system/modules/shared/constants/paths.py`
- DEFAULT_DB_PATH: Main database
- LOG_DIR: Activity logs
- CHATBOT_CONFIG_PATH: Chatbot config
- UPLOADS_DIR: File uploads

---

## Security Features Analysis

### Strengths Identified

1. **Strong Password Security**
   - PBKDF2-SHA256 with 1,000,000 iterations
   - Unique 128-bit salt per user
   - Never plaintext storage

2. **Account Protection**
   - Lockout: 5 attempts → 15-minute lockout
   - Force password reset capability
   - Active/inactive account flags

3. **Multi-Factor Authentication**
   - TOTP implementation via pyotp
   - QR code generation for setup
   - 10 single-use recovery codes
   - Code window tolerance (±1 step = 60 sec)

4. **Comprehensive Auditing**
   - All login attempts logged
   - Activity logging for all actions
   - IP address recording
   - Timestamp on all records

5. **Role-Based Access Control**
   - 5 distinct roles
   - 100+ granular permissions
   - Per-user permission overrides
   - Role isolation enforcement

### Session Management
- Timeout: 30 minutes of inactivity (default)
- Configurable per role if needed
- Last activity tracking
- Current user tracking

---

## File Locations Summary

### Critical Files
| File | Location | Size |
|------|----------|------|
| User Authentication | `/infrastructure/auth/user_authentication.py` | 4,900+ lines |
| GUI Login | `/modules/shared/gui/main_gui.py` | Line 1522+ |
| Database Manager | `/infrastructure/database/db.py` | Connection pooling |
| Schemas | `/infrastructure/database/schemas.py` | Schema definitions |
| CLI Main | `/cli_main.py` | CLI interface |
| Application Entry | `/run.py` | Main launcher |

### Configuration Files
| File | Location | Purpose |
|------|----------|---------|
| requirements.txt | `/requirements.txt` | Python dependencies |
| pyproject.toml | `/pyproject.toml` | Project config |
| Chatbot Config | `/data/chatbot/chatbot_config.json` | Chatbot settings |
| Log Config | `/modules/shared/config/log_config.json` | Logging setup |
| Paths | `/modules/shared/constants/paths.py` | Path definitions |

### Database Files
| File | Location | Purpose |
|------|----------|---------|
| Main Database | `/data/db_files/university_system.db` | SQLite3 database |
| Exports | `/data/db_exports/` | Database backups |
| Logs | `/logs/` | Activity logs |

---

## Default Accounts

| Username | Role | Password | Set Via |
|----------|------|----------|---------|
| admin | admin | Environment var or random | INITIAL_ADMIN_PASSWORD |
| staff | staff | Environment var or random | INITIAL_STAFF_PASSWORD |
| student | student | Environment var or random | INITIAL_STUDENT_PASSWORD |

**Note**: If environment variables not set, 16-character cryptographically secure random passwords are generated on first run.

---

## Entry Points

### Main Application
**File**: `/home/seancatchpole989/run.py`
- Line 104: main() function
- Line 149: Interface selection menu

### GUI Mode
**File**: `/home/seancatchpole989/run.py`
- Line 88: run_gui_mode()

**GUI Implementation**: `/home/seancatchpole989/university_system/modules/shared/gui/main_gui.py`
- Line 1522: show_login_screen()
- Line 1575: perform_login()

### CLI Mode
**File**: `/home/seancatchpole989/run.py`
- Line 67: run_cli_mode()

**CLI Implementation**: `/home/seancatchpole989/university_system/cli_main.py`

---

## Documentation Generated

Two comprehensive documentation files have been created in the project root:

### 1. AUTHENTICATION_ARCHITECTURE_OVERVIEW.md (27 KB)
Complete technical documentation including:
- Authentication system implementation
- User/role management structure
- Complete database schema
- Login logic flow with diagrams
- Dependency analysis
- GUI components
- Configuration files
- Security features
- Usage examples
- Conclusion

### 2. AUTH_QUICK_REFERENCE.md (7.2 KB)
Quick reference guide including:
- File structure overview
- Core components at a glance
- Database tables summary
- Roles and permissions summary
- Authentication flow
- Key dependencies
- Entry points
- Testing credentials
- Common issues and solutions
- Performance notes

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Authentication module lines | 4,900+ |
| Core class | UserAuth (line 1661) |
| Total roles | 5 |
| Total permissions | 100+ |
| Database tables (auth-related) | 8 |
| Failed login attempts before lockout | 5 |
| Lockout duration | 15 minutes |
| Session timeout (default) | 30 minutes |
| Password iterations (PBKDF2) | 1,000,000 |
| Salt size (bits) | 128 |
| 2FA recovery codes | 10 per user |
| 2FA time window | ±1 step (60 seconds) |

---

## Recommendations for Future Enhancement

1. **Session Management**
   - Add distributed session storage for multi-server deployment
   - Implement session binding to IP addresses
   - Add session revocation capability

2. **2FA Enhancement**
   - Add SMS/Email based OTP option
   - Implement WebAuthn/FIDO2 support
   - Add trusted device management

3. **Audit & Compliance**
   - Implement SIEM integration
   - Add compliance reporting (GDPR, HIPAA)
   - Implement log retention policies
   - Add real-time alerting for suspicious activity

4. **Scalability**
   - Consider moving from SQLite to PostgreSQL for production
   - Implement Redis-based session storage
   - Add rate limiting on authentication endpoints

5. **Security Hardening**
   - Add IP-based access control lists
   - Implement zero-trust authentication
   - Add adaptive authentication based on risk
   - Implement passwordless authentication options

---

## Conclusion

The University Management System implements a robust, production-grade authentication architecture with:

✓ Secure password hashing (PBKDF2-SHA256, 1M iterations)
✓ Multi-factor authentication (TOTP via pyotp with QR codes)
✓ Comprehensive role-based access control (5 roles, 100+ permissions)
✓ Session management with timeouts
✓ Account lockout protection
✓ Full audit logging
✓ Recovery mechanisms (2FA backup codes)
✓ Support for both CLI and GUI interfaces
✓ Extensible permission system

The system is well-architected, maintainable, and ready for production deployment with proper environment configuration.

---

**Exploration Date**: October 21, 2025
**System Version**: 5.0.0
**Python Requirements**: 3.8+
**Status**: Complete

