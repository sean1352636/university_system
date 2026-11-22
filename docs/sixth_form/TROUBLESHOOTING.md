# Troubleshooting Guide

Solutions to common issues with the Sixth Form College Management System.

---

## Table of Contents

1. [Login and Authentication Problems](#login-and-authentication-problems)
2. [Database Issues](#database-issues)
3. [API Server Issues](#api-server-issues)
4. [GUI Issues](#gui-issues)
5. [Module-Specific Issues](#module-specific-issues)
6. [General Debugging Tips](#general-debugging-tips)

---

## Login and Authentication Problems

### Account Locked After Failed Login Attempts

**Symptom**: You see a message such as "Account locked" or "Too many failed login attempts" when trying to log in.

**Cause**: The system locks an account after 3 consecutive failed login attempts (`MAX_LOGIN_ATTEMPTS = 3` in `src/education_system/platform/identity/auth/defaults.py`). The lockout lasts 15 minutes (`LOCKOUT_DURATION_MINUTES`).

**Solution**:

1. Wait 15 minutes for the lockout to expire, or
2. Have an administrator unlock the account through the **User Management** module, or
3. If no other admin account is available, reset the lock directly in the central auth database:

```bash
source venv/bin/activate
python -c "
import sqlite3
conn = sqlite3.connect('var/data/platform/db_files/auth.db')
conn.execute(\"UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE username = 'admin1'\")
conn.commit()
conn.close()
print('Account unlocked.')
"
```

### Forgotten Default Password

The development credentials, seeded only when `EDU_DEV_SEED=true`, are:

| Role | Username | Password |
|------|----------|----------|
| Super Admin | `superadmin` | `SuperAdmin@123` |
| Admin | `admin1` | `admin1234` |
| Staff | `staff1` | `staff1234` |
| Student | `student1` | `student1234` |
| Parent | `parent1` | `parent1234` |

If these have been changed and forgotten, an administrator must reset the password through User Management or directly in the auth database using the password hashing utility in `src/education_system/platform/identity/auth/password_manager.py`.

### JWT Token Errors

**Symptom**: API requests return `401 Unauthorized` or "Token expired" errors.

**Cause**: JWT tokens expire after 24 hours by default (`JWT_EXPIRY_HOURS` environment variable).

**Solutions**:

- Re-authenticate to obtain a fresh token.
- Check that the `JWT_SECRET_KEY` environment variable matches between the server that issued the token and the server validating it. It must be set to a strong secret in production.
- Verify that the system clocks are synchronized if running across multiple machines.

### MFA Issues

**Symptom**: MFA verification codes are rejected even when entered correctly.

**Solutions**:

- Ensure the device clock is accurate. TOTP codes are time-based and a drift of more than 30 seconds will cause failures.
- If MFA recovery is needed, an administrator can disable MFA for the account through the MFA management interface or by updating the user record in the auth database.
- Check the MFA service implementation in `src/education_system/platform/identity/auth/mfa_service.py` for the accepted time window.

### Session Timeout

**Symptom**: You are logged out unexpectedly.

**Cause**: The GUI and CLI log out after 30 minutes of inactivity by default.

**Solution**: Set the `EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES` environment variable to a longer value (in minutes) if needed:

```bash
export EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES=60
```

---

## Database Issues

### SQLite Database Locked

**Symptom**: Operations fail with `database is locked` errors.

**Cause**: SQLite uses file-level locking. This typically occurs when:

- Multiple processes are writing to the database simultaneously.
- A long-running transaction holds the lock.
- A crashed process left a stale lock file.

**Solutions**:

1. Ensure only one instance of the application (GUI or API server) writes to the database at a time.
2. Check for lingering processes:

```bash
# Find processes using the database file
lsof var/data/sixth_form/sixthform.db
```

3. If a stale lock exists (e.g., after a crash), remove the WAL and SHM files if present:

```bash
rm -f var/data/sixth_form/sixthform.db-wal
rm -f var/data/sixth_form/sixthform.db-shm
```

4. Restart the application.

### Database Does Not Exist or Is Empty

**Symptom**: The application fails at startup with file-not-found errors or shows no data.

**Cause**: The database has not been initialized, or the data directory was deleted.

**Solution**: The system creates the database automatically on first run. Ensure the data directories exist:

```bash
# The application creates these automatically, but you can do it manually:
mkdir -p var/data/sixth_form
```

Then restart the application. Each module's `init_db()` will recreate its tables the next time it is used. Default accounts live in the central auth database, and are seeded when `EDU_DEV_SEED=true`.

### Schema Migration Issues

**Symptom**: Errors referencing missing columns or tables after an update.

**Cause**: The database schema was created with an older version and the new code expects additional tables or columns.

**Solution**:

1. Back up the existing database:

```bash
cp var/data/sixth_form/sixthform.db \
   var/backups/sixth_form/sixthform.db.backup
```

2. This database is not managed by Alembic; each module adds its own new tables and columns in `init_db()`. If that does not resolve it, the simplest approach for development environments is to delete the database and let it be recreated:

```bash
rm var/data/sixth_form/sixthform.db
# Restart the application -- the schema will be recreated
```

**Warning**: Deleting the database destroys all data. Only do this in development or after making a backup.

### Database Backup and Restore

To manually back up the database:

```bash
# Backup
cp var/data/sixth_form/sixthform.db \
   var/backups/sixth_form/sixthform_$(date +%Y%m%d_%H%M%S).db

# Restore from backup
cp var/backups/sixth_form/sixthform_20260308_120000.db \
   var/data/sixth_form/sixthform.db
```

---

## API Server Issues

### Flask Server Fails to Start

**Symptom**: Running the API server produces an error and exits immediately.

**Common causes and solutions**:

1. **Port already in use**: Another process is using port 5000.

```bash
# Check what is using the port
lsof -i :5000

# Use a different port
export API_PORT=5001
python -m education_system --college --api
```

2. **Missing dependencies**: Flask or Flask-CORS is not installed.

```bash
pip install flask flask-cors
```

3. **Import errors**: The package is not on the Python path.

```bash
# Install the project from the repository root
pip install -e .
python -m education_system --college --api
```

### CORS Errors in Browser

**Symptom**: Browser console shows "Access-Control-Allow-Origin" errors when calling the API from a frontend.

**Cause**: The requesting origin is not in the allowed list.

**Solution**: Add the origin to the comma-separated `API_CORS_ORIGINS` environment variable. The unified server (`src/education_system/platform/delivery/api/unified_server.py`) refuses a wildcard in production, and allows only localhost origins in development.

### API Returns 500 Internal Server Error

**Symptom**: API calls return a 500 error with no useful message.

**Solutions**:

1. Check the server's console output for the full traceback.
2. Restart with more detailed logging (development only):

```bash
export APP_ENV=development
export LOG_LEVEL=DEBUG
python -m education_system --college --api
```

3. Verify the database exists and is accessible.

### API Authentication Failures

**Symptom**: All authenticated API endpoints return 401.

**Solutions**:

- Include the JWT token in the `Authorization` header as `Bearer <token>`.
- Verify the token has not expired (default: 24 hours).
- Ensure `JWT_SECRET_KEY` is consistent across server restarts. If the secret changes, all existing tokens become invalid.

---

## GUI Issues

### GUI Window Does Not Appear

**Symptom**: Running the GUI command produces no visible window, or the process exits silently.

**Solutions**:

1. **tkinter not installed**: On some Linux distributions, tkinter is a separate package:

```bash
# Debian / Ubuntu
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter
```

2. **No display server**: If running over SSH or in a headless environment, tkinter requires a display. Use X11 forwarding:

```bash
ssh -X user@host
```

Or set up a virtual framebuffer for testing:

```bash
sudo apt-get install xvfb
xvfb-run python -m education_system --college --gui
```

### GUI Freezes or Becomes Unresponsive

**Symptom**: The GUI stops responding to clicks or keyboard input.

**Cause**: A long-running operation is blocking the main tkinter event loop.

**Solutions**:

- Wait for the operation to complete. Database operations on large datasets may take time.
- Check the console output, launching with `--verbose` if needed, for errors that may indicate an infinite loop or deadlock.
- If the application is completely stuck, terminate the process and restart.

### Sidebar Modules Not Loading

**Symptom**: The sidebar appears but some or all modules are missing.

**Solutions**:

- Check the console for import errors. A syntax error or missing dependency in one module can prevent it from loading.
- Verify that the module is listed in `NAV_CATEGORIES` in `src/education_system/systems/sixth_form/interfaces/gui/gui_main.py`, and that your role has the capability for its label in `MENU_CAPABILITIES`, in `domain/governance/user_management/access.py`. A label missing from that map is admin-only.
- Run a quick import check, naming the window that will not open:

```bash
python -c "from education_system.systems.sixth_form.interfaces.gui.academics.enrichment import enrichment_views"
```

Any import errors will be printed to the console.

---

## Module-Specific Issues

### Attendance Module Shows No Classes

**Symptom**: The attendance register is empty with no classes to mark.

**Cause**: Attendance registers are generated from the timetable. If no timetable entries exist, no registers appear.

**Solution**: Populate the timetable first via the **Timetable** module, then return to **Attendance**.

### Enrollment Fails with Prerequisite Error

**Symptom**: Enrolling a student in a course fails with a prerequisite validation error.

**Solution**: Check the course prerequisites in the **Courses** module. Ensure the student has completed (and passed) all required prerequisite courses before enrolling.

### Reports Module Produces Empty Output

**Symptom**: Generating a report produces a blank document or no output.

**Solution**: Verify that the relevant data exists. Reports aggregate data from other modules (grades, attendance, enrollment). If those modules have no records, reports will be empty.

---

## General Debugging Tips

### Check the Log Files

The launcher logs to the console. Log entries include a timestamp and the message, for example:

```
2026-03-08 10:15:32 - Message text
```

- **INFO**: Normal operations (hidden by default).
- **WARNING**: Potential issues (shown on the console).
- **ERROR**: Failures that need attention.

To increase log verbosity, launch with `--verbose` (or set `EDU_VERBOSE=1`):

```bash
python -m education_system --college --gui --verbose
```

### Verify the Python Environment

Ensure you are using the correct virtual environment:

```bash
which python
# Should point to: python (or your venv path)

python -c "import flask; print(flask.__version__)"
```

### Inspect the Database Directly

Use the SQLite command-line tool to inspect the database:

```bash
sqlite3 var/data/sixth_form/sixthform.db

# List all tables
.tables

# Check a specific table's schema
.schema students

# Count records
SELECT COUNT(*) FROM students;

# Exit
.quit
```

### Check the Exception Types

There is no system-wide exception hierarchy. Each domain module defines its own `ValidationError`, for example `education_system.systems.sixth_form.domain.academics.enrichment.enrichment.ValidationError`. Authentication failures raise `AuthError` and `MFAError` from `education_system.platform.identity.auth.exceptions`.

When debugging, catch the `ValidationError` of the module you are calling.

### Reset to a Clean State

If all else fails and you are in a development environment, you can reset the system to its initial state:

```bash
# Remove the database (destroys all data)
rm -f var/data/sixth_form/sixthform.db

# Restart the application -- the database will be recreated
python -m education_system --college --gui
```

---

**Last Updated**: October 2026
**Version**: 1.0.0
