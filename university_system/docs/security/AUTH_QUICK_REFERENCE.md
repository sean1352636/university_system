# University System Authentication - Quick Reference Guide

## File Structure

```
university_system/
├── infrastructure/
│   ├── auth/
│   │   ├── __init__.py
│   │   └── user_authentication.py    [CORE - 4900+ lines]
│   └── database/
│       ├── db.py                     [Database connection pooling]
│       ├── schemas.py                [Schema definitions]
│       └── constants.py              [DB configuration]
├── modules/shared/gui/
│   └── main_gui.py                   [GUI login screen (line 1522)]
└── cli_main.py                       [CLI login interface]
```

## Core Components at a Glance

### 1. UserAuth Class (Line 1661)

**Location**: `user_authentication.py:1661`

```python
class UserAuth:
    # Configuration
    session_timeout = 30              # minutes
    max_attempts = 5                  # login attempts
    lockout_time = 15                 # minutes
    
    # Methods
    login(username, password)         # Main auth method (Line 4012)
    enable_two_fa(user_id)           # Setup 2FA (Line 3240)
    verify_two_fa_code(user_id, code) # Verify OTP (Line 3339)
    logout()                          # End session
    _hash_password(password, salt)    # PBKDF2-SHA256 (Line 1989)
```

### 2. Database Tables

| Table | Purpose | Key Columns |
|-------|---------|------------|
| `users` | User profiles | id, username, email, role |
| `user_accounts` | Credentials | password_hash, salt, two_fa_secret |
| `two_fa_recovery_codes` | 2FA backup | code_hash, is_used |
| `roles` | Role definitions | role_name, description |
| `permissions` | Permission names | permission_name |
| `role_permissions` | Permission mapping | role_id, permission_id |
| `login_attempts` | Audit log | username, success, timestamp |
| `activity_log` | Comprehensive log | user_id, action, details |

### 3. Roles & Permissions Summary

| Role | Key Permissions | Count |
|------|-----------------|-------|
| admin | All operations | 100+ |
| staff | Manage students, grading, reports | 50+ |
| student | View own records, submit work | 40+ |
| instructor | Manage modules, grade students | 30+ |
| parent | View child records | 15+ |

## Authentication Flow (Quick Version)

```
1. User enters credentials → GUI/CLI
2. Check account lockout (5 attempts, 15 min)
3. Query user_accounts + users tables
4. Hash password with PBKDF2-SHA256 (1M iterations)
5. Compare hashes
6. If 2FA enabled: Return requires_2fa flag
7. Else: Set current_user, update last_login, log activity
8. Session established (30 min timeout)
```

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pyotp | >=2.6.0 | TOTP 2FA implementation |
| qrcode | >=7.3.0 | QR code generation |
| cryptography | >=3.4.8 | Crypto operations |
| sqlite3 | built-in | Database |
| hashlib | built-in | Hashing |
| secrets | built-in | Random generation |
| tkinter | included | GUI framework |

## Default Accounts

| Username | Role | Default Password | Set Via |
|----------|------|------------------|---------|
| admin | admin | Environment var | INITIAL_ADMIN_PASSWORD |
| staff | staff | Environment var | INITIAL_STAFF_PASSWORD |
| student | student | Environment var | INITIAL_STUDENT_PASSWORD |

If not set, random 16-char passwords generated on startup.

## Security Measures

- PBKDF2-SHA256 with 1,000,000 iterations
- Unique random salt per user (128-bit)
- TOTP 2FA with QR code setup
- 10 single-use recovery codes per user
- Account lockout: 5 attempts → 15 min lockout
- Session timeout: 30 minutes inactivity
- Full audit logging of all attempts
- Activity logging for all actions

## Configuration Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `pyproject.toml` | Project metadata & dependencies |
| `chatbot_config.json` | Chatbot settings (session_timeout: 3600) |
| `log_config.json` | Logging configuration |

## Entry Points

| Interface | File | Location |
|-----------|------|----------|
| Main Menu | run.py | Line 104 |
| GUI Login | main_gui.py | Line 1522 |
| GUI Process | main_gui.py | Line 1575 |
| CLI Login | cli_main.py | Various |
| Database Init | database_utils.py | Various |

## Key Methods

### Login (Line 4012)
```python
result = auth.login(username, password)
# Returns: True, dict{'requires_2fa': True}, False
```

### 2FA Setup (Line 3240)
```python
result = auth.enable_two_fa(user_id)
# Returns: {'success': True, 'secret': '...', 'qr_code': <img>, 'recovery_codes': [...]}
```

### Password Hashing (Line 1989)
```python
salt, hash = auth._hash_password(password)
# PBKDF2-SHA256, 1M iterations, 64-byte output
```

### Database Init (Line 2009)
```python
auth._init_db()
# Creates all tables, default roles, permissions
```

## Testing Credentials

```bash
# From environment
export INITIAL_ADMIN_PASSWORD="admin123"
export INITIAL_STAFF_PASSWORD="staff123"
export INITIAL_STUDENT_PASSWORD="student123"

# Or use GUI display (default demo values)
# Username: admin, password: admin123
# Username: staff, password: staff123
# Username: student, password: student123
```

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Account locked | 5 failed attempts | Wait 15 minutes or use recovery codes |
| 2FA not working | TOTP code expired | Current window is ±1 step (60 sec) |
| No default accounts | First run | Check environment variables or logs |
| Lost 2FA access | Disabled recovery | Use backup 10 recovery codes |
| Database locked | Multiple connections | Connection pool handles this |

## GUI Components

| Component | Location | Purpose |
|-----------|----------|---------|
| show_login_screen() | main_gui.py:1522 | Display login form |
| perform_login() | main_gui.py:1575 | Process login |
| logout_user() | main_gui.py:1634 | End session |
| set_auth() | main_gui.py:29 | Set auth instance |

## Permission Categories

1. **Academic**: modules, schedules, grades
2. **Administrative**: users, roles, system config
3. **Financial**: payments, budgets, reports
4. **Student Services**: accommodations, health, trips
5. **AI/Plagiarism**: detector, whitelist
6. **Library**: books, loans
7. **Parking**: permits, vehicles

## Database Location

```
University System DB:
  /home/seancatchpole989/university_system/data/db_files/university_system.db

Backup Location:
  /home/seancatchpole989/university_system/data/db_exports/

Logs:
  /home/seancatchpole989/university_system/logs/
```

## Quick Debug Commands

```bash
# Check database exists
ls -la /home/seancatchpole989/university_system/data/db_files/

# View SQLite schema
sqlite3 /path/to/database.db ".schema users"

# Check auth module imports
python3 -c "from university_system.infrastructure.auth.user_authentication import UserAuth; print('OK')"

# View login logs
tail -f /home/seancatchpole989/university_system/logs/activity_log_*.json
```

## Performance Notes

- Connection pooling: Min 2, Max 5 connections
- Password hashing: 1M iterations (takes ~100ms per login)
- 2FA verification: <10ms
- Database timeout: 5 seconds default
- SQLite WAL mode: Write-ahead logging enabled
- Foreign key constraints: Enabled

---

**Version**: 5.0.0
**Python**: 3.8+
**Last Updated**: October 21, 2025

