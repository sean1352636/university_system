# Troubleshooting Guide

This document contains solutions to common issues encountered in the University Management System.

## Table of Contents

1. [Authentication Issues](#authentication-issues)
2. [Database Issues](#database-issues)
3. [Import Errors](#import-errors)
4. [Permission Issues](#permission-issues)

---

## Authentication Issues

### Invalid Credentials Error

**Symptom:**
```
[AUTH_INVALID_CREDENTIALS] Invalid username or password.
```

**Cause:**
- Password hash mismatch in database
- Password may have been changed or corrupted
- Database migration may have changed hashing parameters

**Solution:**

Use the password reset utility to reset user passwords:

```bash
# From project root
cd .

# Reset all default development accounts
python3 university_system/utils/reset_password.py --reset-defaults

# Reset specific user (interactive)
python3 university_system/utils/reset_password.py --user admin

# List all users
python3 university_system/utils/reset_password.py --list-users
```

**Default Credentials After Reset:**
- **Super Admin:** `superadmin` / `SuperAdmin@123`
- **Admin:** `admin` / `admin123`
- **Staff:** `staff` / `staff123`
- **Student:** `S12345` / `student123`

**Manual Password Reset (SQL):**

If the utility doesn't work, you can reset passwords directly in SQLite:

```python
#!/usr/bin/env python3
import hashlib
import secrets
import sqlite3

def hash_password(password):
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 1_000_000, dklen=64)
    return salt, key.hex()

# Connect to database
conn = sqlite3.connect('university_system/data/db_files/student_records.db')
cursor = conn.cursor()

# Generate hash for 'admin123'
salt, hash_value = hash_password('admin123')

# Update admin password
cursor.execute('''
    UPDATE user_accounts
    SET password_hash = ?, salt = ?, is_active = 1
    WHERE username = 'admin'
''', (hash_value, salt))

conn.commit()
conn.close()

print("✅ Admin password reset to: admin123")
```

### Account Locked Error

**Symptom:**
```
Account temporarily locked. Please try again in X minutes.
```

**Cause:**
- Too many failed login attempts (default: 5 attempts)
- Automatic lockout period (default: 15 minutes)

**Solution:**

**Option 1: Wait** for the lockout period to expire (15 minutes)

**Option 2: Clear failed login attempts** (SQL):

```sql
-- This clears in-memory attempts, but you may need to restart the application
sqlite3 university_system/data/db_files/student_records.db "
  UPDATE user_accounts SET is_active = 1 WHERE username = 'admin';
"
```

**Option 3: Restart the application** to clear in-memory lockout state

### Account Deactivated Error

**Symptom:**
```
This account has been deactivated. Please contact an administrator.
```

**Solution:**

Reactivate the account in database:

```bash
sqlite3 university_system/data/db_files/student_records.db "
  UPDATE user_accounts SET is_active = 1 WHERE username = 'your_username';
"
```

Or use the password reset utility:

```bash
python3 university_system/utils/reset_password.py --user your_username
```

---

## Database Issues

### Database Locked Error

**Symptom:**
```
sqlite3.OperationalError: database is locked
```

**Cause:**
- Multiple processes accessing the database
- Write-Ahead Logging (WAL) mode not enabled
- Long-running transaction

**Solution:**

1. **Close all other instances** of the application

2. **Enable WAL mode** (should be automatic, but can be set manually):
   ```bash
   sqlite3 university_system/data/db_files/student_records.db "PRAGMA journal_mode=WAL;"
   ```

3. **Check for zombie processes:**
   ```bash
   ps aux | grep python
   # Kill any orphaned processes
   kill -9 <PID>
   ```

4. **Check connection pool limits** in `infrastructure/database/db.py`:
   - Default min: 2, max: 10 connections
   - Increase if needed for high concurrency

### Missing Database File

**Symptom:**
```
unable to open database file
```

**Solution:**

Initialize the database:

```bash
cd .
python3 -c "
from university_system.infrastructure.database.schemas import initialize_all_schemas
initialize_all_schemas()
print('✅ Database initialized')
"
```

Or run the setup script:

```bash
python3 university_system/modules/setup_unified_database.py
```

### Schema Mismatch

**Symptom:**
- SQL errors about missing columns
- "no such column" errors

**Solution:**

Check and update the schema:

```bash
# Backup first!
cp university_system/data/db_files/student_records.db university_system/data/db_files/student_records.db.backup

# Run migrations
python3 university_system/infrastructure/database/migrations/add_security_features.py
python3 university_system/infrastructure/database/migrations/add_mfa_system.py
```

---

## Import Errors

### Module Not Found

**Symptom:**
```
ModuleNotFoundError: No module named 'university_system'
```

**Solution:**

1. **Always run from project root:**
   ```bash
   cd .
   python3 -m university_system.modules.shared.cli.cli_main
   ```

2. **Or use the run script:**
   ```bash
   cd .
   python3 run.py
   ```

3. **Check PYTHONPATH:**
   ```bash
   export PYTHONPATH=".:$PYTHONPATH"
   ```

### After Refactoring Import Errors

**Symptom:**
```
ImportError: cannot import name 'SomeClass' from 'old.module.path'
```

**Solution:**

Use the new modular imports (see `CLAUDE.md` for details):

```python
# Old (deprecated but works via __init__.py)
from university_system.modules.interfaces.gui.grade_tracking_gui import GradeTrackingApp

# New (recommended)
from university_system.modules.interfaces.gui.grade_tracking import GradeTrackingApp
```

---

## Permission Issues

### Permission Denied Errors

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: 'data/db_files/student_records.db'
```

**Solution:**

Fix file permissions:

```bash
cd university_system
chmod -R 755 data/ logs/ backups/
chmod 644 data/db_files/*.db
```

### Access Denied in Application

**Symptom:**
```
[PERMISSION_DENIED] You do not have permission to perform this action.
```

**Cause:**
- User role doesn't have required permission
- RBAC (Role-Based Access Control) restrictions

**Solution:**

1. **Check user role:**
   ```bash
   python3 university_system/utils/reset_password.py --list-users
   ```

2. **Grant admin privileges** (SQL):
   ```sql
   UPDATE users SET role = 'admin' WHERE username = 'your_username';
   ```

3. **Check role permissions** in `infrastructure/auth/authorization.py`

---

## Running the Application

### Cannot Start GUI

**Symptom:**
- GUI window doesn't appear
- Tkinter errors

**Solution:**

1. **Check Tkinter installation:**
   ```bash
   python3 -m tkinter
   ```

2. **Install Tkinter** (if missing):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-tk

   # Fedora
   sudo dnf install python3-tkinter

   # macOS
   brew install python-tk
   ```

3. **Use CLI instead:**
   ```bash
   python3 run.py --cli
   ```

### Cannot Start Web Interface

**Symptom:**
- Flask errors
- Port already in use

**Solution:**

1. **Check if port is in use:**
   ```bash
   lsof -i :5000
   # Kill the process if needed
   ```

2. **Use different port:**
   ```bash
   export FLASK_PORT=5001
   python3 university_system/modules/web/app.py
   ```

3. **Install Flask** (if missing):
   ```bash
   pip install flask
   ```

---

## Performance Issues

### Slow Database Queries

**Solution:**

1. **Enable WAL mode** (better concurrency)
2. **Add indexes** for frequently queried columns
3. **Use connection pooling** (enabled by default)
4. **Run VACUUM** periodically:
   ```bash
   sqlite3 university_system/data/db_files/student_records.db "VACUUM;"
   ```

### High Memory Usage

**Solution:**

1. **Reduce connection pool size** in `infrastructure/database/db.py`
2. **Close unused connections**
3. **Use pagination** for large result sets

---

## Getting Help

If you're still experiencing issues:

1. **Check logs:**
   ```bash
   tail -f university_system/logs/application.log
   ```

2. **Enable debug mode:**
   ```bash
   export DEBUG=True
   python3 run.py
   ```

3. **Run tests:**
   ```bash
   make test
   # or
   python3 -m pytest university_system/tests/ -v
   ```

4. **Consult documentation:**
   - `university_system/CLAUDE.md` - Project guide
   - `university_system/docs/` - Full documentation
   - `university_system/docs/SECURITY.md` - Security guide

---

## Quick Reference Commands

```bash
# Password Reset
python3 university_system/utils/reset_password.py --reset-defaults

# List Users
python3 university_system/utils/reset_password.py --list-users

# Database Backup
make db-backup
# or
cp university_system/data/db_files/student_records.db backups/backup_$(date +%Y%m%d_%H%M%S).db

# Run Tests
make test

# Code Quality
make lint
make format

# Start Application
python3 run.py            # Interactive menu
python3 run.py --cli      # CLI mode
python3 run.py --gui      # GUI mode
```

---

**Last Updated:** 2025-10-31
