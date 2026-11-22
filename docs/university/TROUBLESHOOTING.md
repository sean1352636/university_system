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

Passwords live only in the shared `auth.db` (`var/data/platform/db_files/auth.db`), so a reset applies to every system that login can reach.

Sign in as the system admin and reset the password from the admin panel, or use the reset tool:

```bash
python tools/university/reset_password.py --user admin   # prompts for the new password
python tools/university/reset_password.py --list-users
```

The tool unlocks the account, ends its sessions and sets the new password as temporary. The password must meet the strength rules. It doesn't reactivate a deactivated account.

To put the University's demo accounts back to the passwords listed below on a development machine:

```bash
EDU_DEV_SEED=true python tools/university/reset_password.py --reset-defaults
```

**Default Credentials (seeded only when `EDU_DEV_SEED=true`):**
- **Super Admin:** `superadmin` / `SuperAdmin@123`
- **Admin:** `admin` / `admin123`
- **Staff:** `staff` / `staff123`
- **Student:** `S12345` / `student123`

### Account Locked Error

**Symptom:**
```
Account temporarily locked. Please try again in X minutes.
```

**Cause:**
- Too many failed login attempts (default: 3 attempts)
- Automatic lockout period (default: 15 minutes)

**Solution:**

**Option 1: Wait** for the lockout period to expire (15 minutes)

**Option 2: Clear failed login attempts** (SQL):

```sql
sqlite3 var/data/platform/db_files/auth.db "
  UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE username = 'admin';
"
```

### Account Deactivated Error

**Symptom:**
```
This account has been deactivated. Please contact an administrator.
```

**Solution:**

Reactivate the account in database:

```bash
sqlite3 var/data/platform/db_files/auth.db "
  UPDATE users SET is_active = 1 WHERE username = 'your_username';
"
```

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
   sqlite3 var/data/university/db_files/student_records.db "PRAGMA journal_mode=WAL;"
   ```

3. **Check for zombie processes:**
   ```bash
   ps aux | grep python
   # Kill any orphaned processes
   kill -9 <PID>
   ```

4. **Check connection pool limits** in `src/education_system/systems/university/infrastructure/database/db.py`:
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
python3 -c "
from education_system.systems.university.infrastructure.database.schemas import initialize_all_schemas
initialize_all_schemas()
print('✅ Database initialized')
"
```

Or run the setup script:

```bash
python3 tools/university/setup_unified_database.py
```

### Schema Mismatch

**Symptom:**
- SQL errors about missing columns
- "no such column" errors

**Solution:**

Check and update the schema:

```bash
# Backup first!
cp var/data/university/db_files/student_records.db var/backups/university/database/student_records.db.backup

# Run migrations (the launcher also applies these at startup)
python -m alembic -c src/education_system/alembic.ini upgrade head
```

---

## Import Errors

### Module Not Found

**Symptom:**
```
ModuleNotFoundError: No module named 'education_system'
```

**Solution:**

1. **Install the project:**
   ```bash
   make install-dev
   python -m education_system --university --cli
   ```

2. **Or use the run script from project root:**
   ```bash
   python run.py
   ```

3. **Check PYTHONPATH (never add `src/education_system/` itself):**
   ```bash
   export PYTHONPATH="src:$PYTHONPATH"
   ```

### After Refactoring Import Errors

**Symptom:**
```
ImportError: cannot import name 'SomeClass' from 'old.module.path'
```

**Solution:**

Use the current imports (see [Project Structure](../reference/PROJECT_STRUCTURE.md) for details):

```python
# Current
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking import GradeTrackingApp
```

---

## Permission Issues

### Permission Denied Errors

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: 'var/data/university/db_files/student_records.db'
```

**Solution:**

Fix file permissions:

```bash
chmod -R 755 var/data/ var/logs/ var/backups/
chmod 644 var/data/university/db_files/*.db var/data/platform/db_files/*.db
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
   sqlite3 var/data/platform/db_files/auth.db "
     SELECT u.username, s.system_key, s.role FROM users u
     JOIN user_systems s ON s.user_id = u.id WHERE u.username = 'your_username';
   "
   ```

2. **Grant admin privileges** (SQL):
   ```sql
   UPDATE user_systems SET role = 'admin'
   WHERE system_key = 'university'
     AND user_id = (SELECT id FROM users WHERE username = 'your_username');
   ```

3. **Check role permissions** in `src/education_system/systems/university/infrastructure/auth/core_utils/constants.py`

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
   python -m education_system --university --cli
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
   export API_PORT=5001
   python -m education_system --university --api
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
   sqlite3 var/data/university/db_files/student_records.db "VACUUM;"
   ```

### High Memory Usage

**Solution:**

1. **Reduce connection pool size** in `src/education_system/systems/university/infrastructure/database/db.py`
2. **Close unused connections**
3. **Use pagination** for large result sets

---

## Getting Help

If you're still experiencing issues:

1. **Check logs:**
   ```bash
   tail -f var/logs/app.log
   ```

2. **Enable debug mode:**
   ```bash
   export DEBUG=True
   python -m education_system
   ```

3. **Run tests:**
   ```bash
   make test
   # or
   python3 -m pytest tests/unit/systems/university/ -v --timeout=60
   ```

4. **Consult documentation:**
   - `CLAUDE.md` - Project guide
   - `docs/` - Full documentation
   - `SECURITY.md` - Security guide

---

## Quick Reference Commands

```bash
# List Users
sqlite3 var/data/platform/db_files/auth.db "SELECT username FROM users;"

# Database Backup
cp var/data/university/db_files/student_records.db var/backups/university/database/backup_$(date +%Y%m%d_%H%M%S).db

# Run Tests
make test

# Code Quality
make lint
make format

# Start Application
python -m education_system            # Interactive menu
python -m education_system --university --cli      # CLI mode
python -m education_system --university --gui      # GUI mode
```

---

**Last Updated:** 2025-10-31
