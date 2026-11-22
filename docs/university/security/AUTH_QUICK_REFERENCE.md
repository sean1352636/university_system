# University System Authentication - Quick Reference Guide

## File Structure

```
src/education_system/
├── platform/identity/auth/
│   ├── core.py                       [Shared UserAuth - sign-in against auth.db]
│   ├── password_manager.py           [bcrypt hashing, legacy PBKDF2 verification]
│   ├── session_manager.py            [Session tokens]
│   ├── schema.py                     [auth.db schema and default accounts]
│   └── defaults.py                   [Timeouts and lockout limits]
├── launcher/auth.py                  [Universal CLI and GUI login]
├── platform/delivery/
│   ├── cli/login_cli.py              [CLI login interface]
│   └── gui/login_gui.py              [GUI login window]
└── systems/university/
    ├── infrastructure/auth/
    │   ├── facade.py                 [University UserAuth facade]
    │   └── core_utils/constants.py   [Roles and permissions]
    ├── infrastructure/database/
    │   ├── db.py                     [Database connection pooling]
    │   ├── schemas/                  [Schema definitions]
    │   └── constants.py              [DB configuration]
    └── shell/gui/main/
        ├── main_gui.py               [Main window]
        └── auth_gui.py               [Logout, password change, MFA setup]
```

## Core Components at a Glance

### 1. UserAuth Class

**Location**: `src/education_system/systems/university/infrastructure/auth/facade.py`

```python
class UserAuth:
    # Configuration
    session_timeout = 30              # minutes
    lockout_time = 15                 # minutes

    # Methods
    login(username, password)         # Main auth method
    enable_two_fa(user_id)           # Setup 2FA
    verify_two_fa_code(user_id, code) # Verify OTP
    logout()                          # End session
```

### 2. Database Tables

| Table | Database | Purpose |
|-------|----------|---------|
| `users` | `auth.db` | Logins, password hashes, lockout state |
| `sessions` | `auth.db` | Session tokens |
| `mfa_secrets` | `auth.db` | TOTP secrets |
| `mfa_recovery_codes` | `auth.db` | 2FA backup codes |
| `user_systems` | `auth.db` | Per-system access and role |
| `security_audit_log` | `auth.db` | Security events |
| `users` | `student_records.db` | University user profiles |
| `roles` | `student_records.db` | Role definitions |

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
2. Check account lockout (3 attempts, 15 min)
3. Query users table in auth.db
4. Verify password with bcrypt (legacy PBKDF2-SHA256 hashes still verify)
5. Reject if verification fails
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
| bcrypt | see pyproject.toml | Password hashing |
| secrets | built-in | Random generation |
| tkinter | included | GUI framework |

## Default Accounts

Demo accounts are seeded only when `EDU_DEV_SEED=true`; see [Default Accounts](../../reference/DEFAULT_ACCOUNTS.md).

| Username | Role | Default Password |
|----------|------|------------------|
| admin | admin | admin123 |
| staff | staff | staff123 |
| S12345 | student | student123 |
| parent | parent | parent123 |

For a fresh production database, set `EDU_INITIAL_ADMIN_USER` and `EDU_INITIAL_ADMIN_PASSWORD` (12 or more characters) to create a single admin.

## Security Measures

- bcrypt password hashes
- Unique random salt per user (bcrypt)
- TOTP 2FA with QR code setup
- 10 single-use recovery codes per user
- Account lockout: 3 attempts → 15 min lockout
- Session timeout: 30 minutes inactivity
- Full audit logging of all attempts
- Activity logging for all actions

## Configuration Files

| File | Purpose |
|------|---------|
| `requirements.lock` | Python dependencies |
| `pyproject.toml` | Project metadata & dependencies |
| `var/data/university/config/chatbot_config.json` | Chatbot settings (session_timeout: 3600) |
| `src/education_system/systems/university/infrastructure/config/log_config.json` | Logging configuration |

## Entry Points

| Interface | File |
|-----------|------|
| Launcher | `src/education_system/launcher/main.py` |
| GUI Login | `src/education_system/platform/delivery/gui/login_gui.py` |
| CLI Login | `src/education_system/platform/delivery/cli/login_cli.py` |
| GUI Logout | `src/education_system/systems/university/shell/gui/main/auth_gui.py` |
| Database Init | `src/education_system/systems/university/infrastructure/database/database_utils.py` |

## Key Methods

### Login
```python
result = auth.login(username, password)
# Returns: True, or dict{'success': True, 'requires_2fa': True, 'user_id': ..., 'username': ...}
# Raises: InvalidCredentialsError / AuthenticationError on failure
```

### 2FA Setup
```python
result = auth.enable_two_fa(user_id)
# Returns: {'success': True, 'secret': '...', 'qr_code': <img>, 'recovery_codes': [...]}
```

### Password Hashing
```python
from education_system.platform.identity.auth.password_manager import hash_password

password_hash = hash_password(password)
# bcrypt, with a generated salt
```

### Database Init
```python
auth._init_db()
# Creates all tables, default roles, permissions
```

## Testing Credentials

```bash
# Seed the demo accounts
export EDU_DEV_SEED=true

# Username: admin, password: admin123
# Username: staff, password: staff123
# Username: S12345, password: student123
```

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Account locked | 3 failed attempts | Wait 15 minutes, or sign in as the system admin and clear the lockout |
| 2FA not working | TOTP code expired | Current window is ±1 step (60 sec) |
| No default accounts | First run | Set `EDU_DEV_SEED=true` |
| Lost 2FA access | Disabled recovery | Use backup 10 recovery codes |
| Database locked | Multiple connections | Connection pool handles this |

## GUI Components

| Component | Location | Purpose |
|-----------|----------|---------|
| UniversalLoginWindow | `platform/delivery/gui/login_gui.py` | Display login form and process login |
| logout_user() | `shell/gui/main/auth_gui.py` | End session |
| set_auth() | `shell/gui/main/main_gui.py` | Set auth instance |

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
  var/data/university/db_files/student_records.db

Auth DB:
  var/data/platform/db_files/auth.db

Backup Location:
  var/backups/

Logs:
  var/logs/university/
```

## Quick Debug Commands

```bash
# Check database exists
ls -la var/data/university/db_files/ var/data/platform/db_files/

# View SQLite schema
sqlite3 /path/to/database.db ".schema users"

# Check auth module imports
python3 -c "from education_system.systems.university.infrastructure.auth import UserAuth; print('OK')"

# View login logs
tail -f var/logs/university/activity_log_*.json
```

## Performance Notes

- Connection pooling: Min 2, Max 10 connections (`DB_MIN_CONNECTIONS`, `DB_MAX_CONNECTIONS`)
- Password hashing: bcrypt
- 2FA verification: <10ms
- Database timeout: 5 seconds default
- SQLite WAL mode: Write-ahead logging enabled
- Foreign key constraints: Enabled

---

**Version**: 5.0.0
**Python**: 3.11+
**Last Updated**: October 21, 2025

