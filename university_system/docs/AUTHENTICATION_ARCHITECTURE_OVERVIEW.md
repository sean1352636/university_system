# University System Authentication Architecture Overview

## Executive Summary

The University Management System implements a comprehensive, multi-layered authentication architecture with support for role-based access control (RBAC), two-factor authentication (2FA), session management, and detailed audit logging. The system uses SQLite3 as its primary database with secure password hashing and supports both CLI and GUI interfaces.

---

## 1. AUTHENTICATION SYSTEM IMPLEMENTATION

### 1.1 Core Authentication Module

**Location**: `/home/seancatchpole989/university_system/infrastructure/auth/`

**Main Component**: `user_authentication.py` (4900+ lines)

#### Key Classes

**UserAuth Class** (Line 1661+)
- Core authentication service managing all login/logout operations
- Implements session management with configurable timeout (30 minutes default)
- Handles account lockout after failed attempts (5 attempts, 15 minutes lockout)
- Manages login attempt tracking and logging
- Provides 2FA setup, verification, and recovery code management

#### Key Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `login(username, password)` | Authenticates user, checks 2FA requirement | `bool`, `dict`, or `False` |
| `complete_two_fa_login(user_id, code)` | Verifies 2FA code | `bool` or `None` |
| `enable_two_fa(user_id)` | Sets up 2FA with QR code | `dict` with secret and QR |
| `disable_two_fa(user_id)` | Disables 2FA for user | `bool` |
| `verify_two_fa_code(user_id, code)` | Validates TOTP code | `bool` |
| `logout()` | Ends user session | `None` |
| `_hash_password(password, salt)` | Hashes password using PBKDF2 | `(salt, hash)` tuple |
| `_log_login_attempt(username, success)` | Records login attempt | `None` |
| `_init_db()` | Initializes database schema | `None` |

#### Session Management

```python
# Session Configuration
session_timeout = 30          # minutes
max_login_attempts = 5
lockout_time = 15             # minutes
current_user = None           # Tracks logged-in user
last_activity = None          # Tracks session activity
```

---

## 2. USER/ROLE MANAGEMENT STRUCTURE

### 2.1 Role Definitions

**Location**: Lines 562-568 in `user_authentication.py`

```python
ROLES = {
    'admin': 'Administrator with full system access',
    'staff': 'Staff with access to student records and reports',
    'student': 'Student with access to own records only',
    'instructor': 'Instructor with access to assigned modules and student grades',
    'parent': 'Parent with access to their children\'s records'
}
```

### 2.2 Permission Model

**Location**: Lines 571-662+ in `user_authentication.py`

The system uses a role-based permission system with granular permissions for each role:

#### Admin Permissions (100+ permissions)
- Full CRUD operations on students, users, modules
- System configuration and backup/restore
- Financial management
- Academic calendar management
- AI detector and plagiarism system management
- Trip management
- Full access to all subsystems

#### Staff Permissions (50+ permissions)
- Create/view/update students
- Manage assignments and grading
- Generate reports and analytics
- Manage events and accommodations
- Limited financial records
- AI detector and plagiarism access (limited)

#### Student Permissions (40+ permissions)
- View own records
- Access own grades and attendance
- Manage own profile
- Submit assignments
- Register for trips
- Health appointments
- Financial records (own only)

#### Instructor Permissions
- Manage assigned modules
- Grade student assignments
- View student records for assigned courses
- Access academic calendar

#### Parent Permissions
- View children's records
- View children's grades and attendance
- Manage communication preferences

### 2.3 Permission Categories

1. **Academic**: `view_own_record`, `view_assigned_modules`, `manage_modules`, etc.
2. **Administrative**: `manage_users`, `manage_roles`, `system_config`, `backup_restore`
3. **Financial**: `manage_finances`, `record_payments`, `view_financial_reports`
4. **Grading**: `manage_grades`, `view_own_grades`, `manage_module_grades`
5. **Attendance**: `manage_attendance`, `view_own_attendance`
6. **AI/Plagiarism**: `access_ai_detector`, `check_plagiarism`, `analyze_submissions`
7. **Parking**: `manage_parking`, `create_permit`, `register_vehicle`
8. **Health**: `manage_health_records`, `schedule_health_appointment`
9. **Library**: `manage_books`, `checkout_books`, `manage_loans`
10. **Trips**: `manage_trips`, `register_for_trips`, `approve_trip_registrations`

---

## 3. DATABASE SCHEMA FOR USERS

### 3.1 Database Location
**Path**: `university_system/data/db_files/university_system.db` (SQLite3)

### 3.2 Core User Tables

#### Table: `users`
Stores user profile information:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,
    student_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students (student_id)
)
```

**Purpose**: Central user profile storage linking to students table

#### Table: `user_accounts`
Stores authentication credentials:

```sql
CREATE TABLE user_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    last_login TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    password_reset_required INTEGER DEFAULT 0,
    two_fa_enabled INTEGER DEFAULT 0,
    two_fa_secret TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
```

**Purpose**: Secure authentication data with 2FA support

**Key Fields**:
- `password_hash`: PBKDF2-SHA256 hash
- `salt`: Unique salt per user (hex format)
- `two_fa_enabled`: Boolean flag for 2FA activation
- `two_fa_secret`: Base32-encoded TOTP secret
- `password_reset_required`: Forces password change at next login

#### Table: `two_fa_recovery_codes`
Stores recovery codes for 2FA:

```sql
CREATE TABLE two_fa_recovery_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code_hash TEXT NOT NULL,
    is_used INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    used_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
```

**Purpose**: Backup codes for account recovery

#### Table: `roles`
Defines available roles:

```sql
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

#### Table: `permissions`
Defines granular permissions:

```sql
CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL
)
```

#### Table: `role_permissions`
Maps permissions to roles (many-to-many):

```sql
CREATE TABLE role_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    FOREIGN KEY (role_id) REFERENCES roles (id),
    FOREIGN KEY (permission_id) REFERENCES permissions (id),
    UNIQUE(role_id, permission_id)
)
```

#### Table: `user_permissions`
Allows individual user-level permission overrides:

```sql
CREATE TABLE user_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    granted INTEGER NOT NULL,
    UNIQUE(user_id, permission_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
)
```

#### Table: `login_attempts`
Audit trail for login attempts:

```sql
CREATE TABLE login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    attempt_time TEXT NOT NULL,
    ip_address TEXT,
    success INTEGER NOT NULL
)
```

#### Table: `activity_log`
Comprehensive activity logging:

```sql
CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TEXT NOT NULL,
    ip_address TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
)
```

### 3.3 Related Tables

#### Table: `students`
Linked from users via foreign key:

```sql
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    email_address TEXT,
    title TEXT,
    first_name TEXT,
    middle_name TEXT,
    last_name TEXT,
    gender TEXT,
    dob TEXT,
    age INTEGER,
    course TEXT,
    year TEXT,
    registration_datetime TEXT,
    status TEXT DEFAULT 'Active',
    enrollment_date TEXT
)
```

---

## 4. LOGIN/AUTHENTICATION LOGIC HANDLING

### 4.1 Login Flow

**Entry Point**: `UserAuth.login(username, password)` - Line 4012

#### Step-by-Step Process

1. **Check Account Lockout** (Lines 4028-4045)
   - Verify if user has exceeded max login attempts
   - Check if lockout period has expired
   - Return `InvalidCredentialsError` if locked out

2. **Fetch User Credentials** (Lines 4047-4149)
   - Query user_accounts and users tables with JOIN
   - Handle case where user profile is missing
   - Auto-create missing user profile if needed

3. **Verify Password** (Lines 4160-4180)
   - Retrieve stored hash and salt
   - Hash provided password with stored salt using PBKDF2
   - Compare hashes using secure comparison

4. **Check Account Status** (Lines 4180-4195)
   - Verify account is active (`is_active = 1`)
   - Log successful login attempt
   - Check if password reset is required

5. **2FA Check** (Lines 4195-4196)
   - If `two_fa_enabled = 1`, return 2FA requirement flag
   - Return user info without granting access

6. **Complete Login** (Lines 4197+)
   - Call `_complete_login()` to establish session
   - Set `current_user` with user details
   - Update `last_login` timestamp
   - Log activity

### 4.2 Password Hashing Implementation

**Method**: `_hash_password(password, salt=None)` - Line 1989

```python
def _hash_password(self, password, salt=None):
    """
    Uses PBKDF2-SHA256 with 1,000,000 iterations (OWASP recommendation)
    """
    if salt is None:
        salt = secrets.token_hex(16)  # Generate random 32-char hex salt
    
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        1_000_000,  # High iteration count for security
        dklen=64    # 64-byte output
    )
    
    return salt, key.hex()
```

**Security Features**:
- Uses PBKDF2 with SHA256
- 1,000,000 iterations (OWASP standard as of 2021)
- Cryptographically secure random salt (32-char hex = 128 bits)
- Constant-time comparison

### 4.3 Failed Login Handling

**Method**: `_increment_login_attempts(username)` - Line 3994

```python
# Tracks in memory:
self.login_attempts[username] = (attempt_count, timestamp)

# Max attempts: 5
# Lockout duration: 15 minutes
# Resets after lockout period expires
```

**Logging**: `_log_login_attempt(username, success)` - Line 3975
- Records to `login_attempts` table
- Stores timestamp, username, success flag
- Used for security auditing

### 4.4 Two-Factor Authentication Flow

**2FA Setup**: `enable_two_fa(user_id)` - Line 3240

1. Generate random base32 secret using `pyotp.random_base32()` (Line 3156)
2. Create TOTP provisioning URI
3. Generate QR code using `qrcode` library
4. Generate 10 recovery codes
5. Store secret and recovery codes in database
6. Return QR code image and recovery codes

**2FA Verification**: `verify_two_fa_code(user_id, code)` - Line 3339

1. Fetch 2FA secret from user_accounts
2. Create TOTP instance with secret
3. Verify code against current time window (±1 step)
4. If verification fails, check recovery codes
5. Mark used recovery code in database
6. Return success/failure

**Recovery Code Usage**: Lines 3375-3396
- Check recovery code hash against stored hash
- Mark code as used with timestamp
- Allow single use per code
- Regenerate all codes on use (security practice)

### 4.5 Default Credentials

**Generated on First Run**:
- Admin account: `admin`
- Staff account: `staff`
- Student account: `student`

**Password Source**:
```python
admin_password = os.getenv('INITIAL_ADMIN_PASSWORD')
if not admin_password:
    admin_password = generate_secure_password()  # 16-char random
```

**Location in Code**: Lines 1798-1815

---

## 5. EXISTING DEPENDENCIES

### 5.1 Authentication-Related Dependencies

**From `requirements.txt` and `pyproject.toml`**:

```
pyotp>=2.6.0              # Two-factor authentication (TOTP/HOTP)
qrcode>=7.3.0             # QR code generation for 2FA setup
cryptography>=3.4.8       # Cryptographic functions
bcrypt>=3.2.0             # Password hashing (available but PBKDF2 used instead)
```

### 5.2 Core Dependencies

```
sqlite3                   # Database (built-in with Python)
hashlib                   # Secure hashing (built-in)
secrets                   # Cryptographically secure randomness (built-in)
json                      # Configuration/data serialization (built-in)
logging                   # Audit logging (built-in)
datetime                  # Timestamp management (built-in)
```

### 5.3 GUI Framework Dependencies

```
tkinter                   # GUI framework (usually included)
```

### 5.4 Other Key Dependencies

```
flask>=2.0.0             # Optional web API framework
requests>=2.27.0         # HTTP client
PyYAML>=6.0              # Configuration file parsing
```

### 5.5 Optional AI/ML Dependencies (Not in Core Auth)

```
tensorflow>=2.7.0        # AI detector
transformers>=4.15.0     # NLP models
opencv-python>=4.5.0     # Computer vision
torch>=1.10.0            # Deep learning
```

---

## 6. LOGIN GUI COMPONENTS

### 6.1 GUI Entry Point

**Location**: `/home/seancatchpole989/university_system/modules/shared/gui/main_gui.py`

**Main Function**: `run_gui_interface()` (referenced from run.py)

### 6.2 Login Screen Implementation

**Method**: `show_login_screen()` - Line 1522

```python
def show_login_screen(self):
    """Show login interface when not authenticated"""
    # Creates login form with:
    # - Username entry field
    # - Password entry field (masked with *)
    # - Login button
    # - Default credentials display
```

**UI Components**:
- `LabelFrame`: Login form container
- `ttk.Entry`: Username and password fields
- `ttk.Button`: Login action button
- `ttk.Label`: Informational labels and credentials display

### 6.3 Login Processing

**Method**: `perform_login()` - Line 1575

```python
def perform_login(self):
    """Handle login process"""
    # 1. Get username and password from entry widgets
    # 2. Call self.auth.login(username, password)
    # 3. Handle 3 outcomes:
    #    - Success: Show main interface
    #    - 2FA Required: Show 2FA dialog
    #    - Failure: Show error message
```

**Return Value Handling**:
- `True`: Successful login → show main interface
- `dict` with `requires_2fa`: 2FA needed
- `'password_reset_required'`: Force password change
- `False` or other: Show error

### 6.4 Authentication Integration

**Code**: Lines 12-34 in main_gui.py

```python
try:
    from university_system.infrastructure.auth.user_authentication import UserAuth
except ImportError:
    UserAuth = None

try:
    from university_system.infrastructure.auth.user_authentication import (
        get_current_user, set_auth_instance
    )
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False

# Global auth instance
auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
```

### 6.5 Authentication State

**Attributes**:
- `self.auth`: UserAuth instance
- `self.auth.current_user`: Current logged-in user info
- `self.auth.last_activity`: Last user activity timestamp
- `self.username_entry`: tkinter Entry widget for username
- `self.password_entry`: tkinter Entry widget for password

### 6.6 Logout Functionality

**Method**: `logout_user()` - Line 1634

```python
def logout_user(self):
    """Logout current user"""
    if self.auth.current_user:
        username = self.auth.current_user['username']
        self.auth.logout()  # Ends session
        self.update_status()  # Updates UI
        self.show_login_screen()  # Returns to login
```

---

## 7. CONFIGURATION FILES

### 7.1 Database Configuration

**Database Path**: `university_system/data/db_files/university_system.db`

**Connection Settings**:
```python
DEFAULT_DB_TIMEOUT = 5.0      # Connection timeout (seconds)
SQLITE_BUSY_TIMEOUT = 30000   # Busy timeout (milliseconds)
PRAGMA_FOREIGN_KEYS = "ON"    # Enable foreign key constraints
PRAGMA_JOURNAL_MODE = "WAL"   # Write-ahead logging
PRAGMA_SYNCHRONOUS = "NORMAL" # Balanced sync mode
```

**Location**: `/home/seancatchpole989/university_system/infrastructure/database/constants.py`

### 7.2 Chatbot Configuration

**Location**: `/home/seancatchpole989/university_system/data/chatbot/chatbot_config.json`

```json
{
    "security": {
        "jwt_secret": "[32-char hex]",
        "session_timeout": 3600,
        "max_login_attempts": 3
    }
}
```

### 7.3 Activity Logging Configuration

**Location**: `/home/seancatchpole989/university_system/modules/shared/config/log_config.json`

### 7.4 Path Constants

**Location**: `/home/seancatchpole989/university_system/modules/shared/constants/paths.py`

Defines:
- `DEFAULT_DB_PATH`: Main database file
- `LOG_DIR`: Activity log directory
- `CHATBOT_CONFIG_PATH`: Chatbot configuration
- `UPLOADS_DIR`: File upload directory

---

## 8. AUTHENTICATION FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                    User Login Request                        │
│                (GUI or CLI Interface)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  Get Username & Password    │
         │  from Entry Fields          │
         └──────────┬──────────────────┘
                    │
                    ▼
         ┌─────────────────────────────┐
         │  Check Account Lockout      │
         │  (5 attempts, 15 min)       │
         └──────────┬──────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼ (Locked)            ▼ (Not Locked)
     Return Error         Query Database
                         (users + user_accounts)
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │  Verify Password         │
                    │  (PBKDF2-SHA256)         │
                    └──────────┬───────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼ (Invalid)           ▼ (Valid)
              Increment Attempts    Check 2FA Enabled
              Record Failed Login           │
              Return Error          ┌───────┴───────┐
                                    │               │
                                    ▼ (2FA ON)      ▼ (2FA OFF)
                            Return 2FA Required  Complete Login:
                            (User Enters Code)   - Set current_user
                                    │             - Update last_login
                                    ▼             - Log activity
                        ┌──────────────────────┐
                        │ Verify TOTP Code     │
                        │ (pyotp library)      │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼ (Valid)                     ▼ (Invalid)
              Complete Login            Check Recovery Code
              Return Success            (10 codes available)
                                               │
                                ┌──────────────┴──────────────┐
                                │                             │
                                ▼ (Valid)                     ▼ (Invalid)
                          Complete Login              Return 2FA Failed
                          Mark Code Used
                          Return Success
```

---

## 9. SECURITY FEATURES

### 9.1 Password Security

- **Algorithm**: PBKDF2-SHA256
- **Iterations**: 1,000,000 (OWASP 2021 recommendation)
- **Salt**: 16 random bytes (32-char hex), unique per user
- **Output**: 64 bytes, hexadecimal encoded
- **Never Stored**: Plaintext passwords never stored

### 9.2 Account Security

- **Lockout**: 5 failed attempts → 15-minute lockout
- **Password Reset**: Can be forced on next login
- **Account Status**: Active/inactive flag for disabling accounts
- **Session Timeout**: 30 minutes of inactivity (default)

### 9.3 Two-Factor Authentication

- **Algorithm**: TOTP (Time-based One-Time Password) via pyotp
- **Code Duration**: 30-second windows
- **Time Skew**: ±1 window tolerance for clock drift
- **QR Code**: Generated for easy 2FA app setup
- **Recovery Codes**: 10 single-use codes per user
- **Regeneration**: Codes regenerated on use for security

### 9.4 Audit & Logging

- **Login Attempts**: All attempts logged (success/failure)
- **Activity Log**: Comprehensive action logging
- **Timestamps**: All activities timestamped
- **IP Address**: Recorded where available

### 9.5 Role-Based Access Control

- **Granular Permissions**: 100+ distinct permissions
- **Role Hierarchy**: 5 main roles with specific permission sets
- **Permission Override**: Individual user permissions possible
- **Role Isolation**: Permissions enforced per role

---

## 10. SUMMARY TABLE: KEY COMPONENTS

| Component | Location | Type | Purpose |
|-----------|----------|------|---------|
| UserAuth Class | `/infrastructure/auth/user_authentication.py:1661` | Python Class | Core auth service |
| Login Method | `/infrastructure/auth/user_authentication.py:4012` | Method | Authentication logic |
| Password Hash | `/infrastructure/auth/user_authentication.py:1989` | Method | PBKDF2-SHA256 hashing |
| 2FA Setup | `/infrastructure/auth/user_authentication.py:3240` | Method | Enable TOTP+QR |
| 2FA Verify | `/infrastructure/auth/user_authentication.py:3339` | Method | Validate OTP codes |
| GUI Login | `/modules/shared/gui/main_gui.py:1522` | Method | Login UI form |
| Users Table | SQLite3 DB | Table | User profiles |
| User Accounts Table | SQLite3 DB | Table | Auth credentials |
| 2FA Secrets Table | SQLite3 DB | Table | TOTP secrets |
| Recovery Codes Table | SQLite3 DB | Table | 2FA backup codes |
| Activity Log Table | SQLite3 DB | Table | Audit trail |

---

## 11. DEPENDENCIES SUMMARY

### Core Authentication Libraries
- **pyotp** (2.6.0+): TOTP/HOTP implementation
- **qrcode** (7.3.0+): QR code generation
- **cryptography** (3.4.8+): Cryptographic operations
- **bcrypt** (3.2.0+): Available but not used (PBKDF2 preferred)

### Database & Storage
- **sqlite3**: Built-in Python module
- **Path handling**: `pathlib` and `os` (built-in)

### Logging & Audit
- **logging**: Built-in module
- **datetime**: Built-in module
- **json**: Built-in module for serialization

### GUI Framework
- **tkinter**: GUI library (usually included with Python)
- **ttk**: Themed tkinter widgets

### Session Management
- **threading**: Built-in concurrency
- **secrets**: Cryptographic randomness
- **hashlib**: Secure hashing

---

## 12. ENTRY POINTS

### Command Line Entry
**File**: `/home/seancatchpole989/run.py`
- Line 67: Import CLI main
- Line 68: Call CLI login flow

### GUI Entry
**File**: `/home/seancatchpole989/run.py`
- Line 88: Import GUI interface
- Line 89: Call `run_gui_interface()`

**GUI File**: `/home/seancatchpole989/university_system/modules/shared/gui/main_gui.py`
- Line 1522: Login screen display
- Line 1575: Login processing

### CLI Entry
**File**: `/home/seancatchpole989/university_system/cli_main.py`
- Implements command-line login interface

---

## 13. USAGE EXAMPLES

### Default Test Credentials
```
Admin:
  Username: admin
  Password: (environment variable or random if not set)

Staff:
  Username: staff
  Password: (environment variable or random if not set)

Student:
  Username: student
  Password: (environment variable or random if not set)
```

### Environment Variables for Password Configuration
```bash
export INITIAL_ADMIN_PASSWORD="your_secure_password"
export INITIAL_STAFF_PASSWORD="your_secure_password"
export INITIAL_STUDENT_PASSWORD="your_secure_password"
```

### Enabling 2FA for a User
```python
auth = UserAuth()
user_id = 1  # Get from database
setup_result = auth.enable_two_fa(user_id)
# Returns: {
#     'success': True,
#     'secret': 'JBSWY3DPEBLW64TMMQ...',
#     'qr_code': <image_data>,
#     'recovery_codes': [code1, code2, ...]
# }
```

### Verifying 2FA Code
```python
is_valid = auth.verify_two_fa_code(user_id, '123456')
# Returns: True or False
```

---

## 14. CONCLUSION

The University Management System implements a robust, production-grade authentication system with:

✓ Secure password hashing (PBKDF2-SHA256 with 1M iterations)
✓ Multi-factor authentication support (TOTP via pyotp)
✓ Comprehensive role-based access control (5 roles, 100+ permissions)
✓ Session management with timeouts and activity tracking
✓ Account lockout protection against brute force
✓ Full audit logging of all authentication events
✓ Recovery mechanisms (password reset, 2FA recovery codes)
✓ Support for both CLI and GUI interfaces

The architecture is designed to be maintainable, secure, and extensible for future authentication enhancements.

---

**Generated**: October 21, 2025
**System Version**: 5.0.0
**Python Requirement**: 3.8+

