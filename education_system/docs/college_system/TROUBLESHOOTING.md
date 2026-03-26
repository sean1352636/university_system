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

**Cause**: The system locks an account after 5 consecutive failed login attempts (`MAX_LOGIN_ATTEMPTS = 5` in `core/defaults.py`).

**Solution**:

1. Wait for the lockout period to expire (if a timed lockout is configured), or
2. Have an administrator unlock the account through the **User Management** module, or
3. If no other admin account is available, reset the lock directly in the database:

```bash
source venv/bin/activate
python -c "
import sqlite3
conn = sqlite3.connect('education_system/college_system/data/db_files/sixthform.db')
conn.execute(\"UPDATE users SET failed_attempts = 0, locked = 0 WHERE username = 'admin'\")
conn.commit()
conn.close()
print('Account unlocked.')
"
```

### Forgotten Default Password

The default credentials seeded on first run are:

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `Admin@123` |
| Teacher | `teacher` | `Teacher@123` |
| Student | `student` | `Student@123` |

If these have been changed and forgotten, an administrator must reset the password through User Management or directly in the database using the password hashing utility in `infrastructure/auth/password_manager.py`.

### JWT Token Errors

**Symptom**: API requests return `401 Unauthorized` or "Token expired" errors.

**Cause**: JWT tokens expire after 24 hours by default (`JWT_EXPIRY_HOURS = 24`).

**Solutions**:

- Re-authenticate to obtain a fresh token.
- Check that the `COLLEGE_JWT_SECRET` environment variable matches between the server that issued the token and the server validating it. The default value is `change-me-in-production` -- this must be set to a strong secret in production.
- Verify that the system clocks are synchronized if running across multiple machines.

### MFA Issues

**Symptom**: MFA verification codes are rejected even when entered correctly.

**Solutions**:

- Ensure the device clock is accurate. TOTP codes are time-based and a drift of more than 30 seconds will cause failures.
- If MFA recovery is needed, an administrator can disable MFA for the account through the MFA management interface or by updating the user record in the database.
- Check the MFA service implementation in `infrastructure/auth/mfa_service.py` for the accepted time window.

### Session Timeout

**Symptom**: You are logged out unexpectedly.

**Cause**: Sessions expire after 30 minutes of inactivity by default (`SESSION_TIMEOUT_MINUTES = 30`).

**Solution**: Set the `COLLEGE_SESSION_TIMEOUT` environment variable to a longer value (in minutes) if needed:

```bash
export COLLEGE_SESSION_TIMEOUT=60
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
lsof education_system/college_system/data/db_files/sixthform.db
```

3. If a stale lock exists (e.g., after a crash), remove the WAL and SHM files if present:

```bash
rm -f education_system/college_system/data/db_files/sixthform.db-wal
rm -f education_system/college_system/data/db_files/sixthform.db-shm
```

4. Restart the application.

### Database Does Not Exist or Is Empty

**Symptom**: The application fails at startup with file-not-found errors or shows no data.

**Cause**: The database has not been initialized, or the data directory was deleted.

**Solution**: The system creates the database automatically on first run. Ensure the data directories exist:

```bash
# The application creates these automatically, but you can do it manually:
mkdir -p education_system/college_system/data/db_files
mkdir -p education_system/college_system/data/locales/en
mkdir -p education_system/college_system/data/config
mkdir -p education_system/college_system/logs
```

Then restart the application. The `init_db()` and `seed_default_data()` functions in `infrastructure/database/schema.py` will recreate the schema and seed default accounts.

### Schema Migration Issues

**Symptom**: Errors referencing missing columns or tables after an update.

**Cause**: The database schema was created with an older version and the new code expects additional tables or columns.

**Solution**:

1. Back up the existing database:

```bash
cp education_system/college_system/data/db_files/sixthform.db \
   education_system/college_system/data/db_files/sixthform.db.backup
```

2. If the application includes migration scripts, run them. Otherwise, the simplest approach for development environments is to delete the database and let it be recreated:

```bash
rm education_system/college_system/data/db_files/sixthform.db
# Restart the application -- schema and seed data will be recreated
```

**Warning**: Deleting the database destroys all data. Only do this in development or after making a backup.

### Database Backup and Restore

To manually back up the database:

```bash
# Backup
cp education_system/college_system/data/db_files/sixthform.db \
   education_system/college_system/data/db_files/sixthform_$(date +%Y%m%d_%H%M%S).db

# Restore from backup
cp education_system/college_system/data/db_files/sixthform_20260308_120000.db \
   education_system/college_system/data/db_files/sixthform.db
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
export COLLEGE_API_PORT=5001
python -m education_system.college_system.api.api_server
```

2. **Missing dependencies**: Flask or Flask-CORS is not installed.

```bash
pip install flask flask-cors
```

3. **Import errors**: The package is not on the Python path.

```bash
# Run from the project root directory
cd education_system
python -m education_system.college_system.api.api_server
```

### CORS Errors in Browser

**Symptom**: Browser console shows "Access-Control-Allow-Origin" errors when calling the API from a frontend.

**Cause**: The Flask-CORS configuration may not cover the requesting origin.

**Solution**: CORS is enabled globally in `api/api_server.py` via `CORS(app)`. If you need to restrict origins, configure it in `api/config.py`. For development, the default allows all origins.

### API Returns 500 Internal Server Error

**Symptom**: API calls return a 500 error with no useful message.

**Solutions**:

1. Check the application log at `college_system/logs/app.log` for the full traceback.
2. Enable Flask debug mode for more detailed error pages (development only):

```bash
export COLLEGE_API_DEBUG=true
python -m education_system.college_system.api.api_server
```

3. Verify the database exists and is accessible.

### API Authentication Failures

**Symptom**: All authenticated API endpoints return 401.

**Solutions**:

- Include the JWT token in the `Authorization` header as `Bearer <token>`.
- Verify the token has not expired (default: 24 hours).
- Ensure `COLLEGE_JWT_SECRET` is consistent across server restarts. If the secret changes, all existing tokens become invalid.

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
xvfb-run python -m education_system.college_system.run
```

### GUI Freezes or Becomes Unresponsive

**Symptom**: The GUI stops responding to clicks or keyboard input.

**Cause**: A long-running operation is blocking the main tkinter event loop.

**Solutions**:

- Wait for the operation to complete. Database operations on large datasets may take time.
- Check `college_system/logs/app.log` for errors that may indicate an infinite loop or deadlock.
- If the application is completely stuck, terminate the process and restart.

### Sidebar Modules Not Loading

**Symptom**: The sidebar appears but some or all modules are missing.

**Solutions**:

- Check the console and log file for import errors. A syntax error or missing dependency in one module can prevent it from loading.
- Verify that the `modules/domain/__init__.py` file correctly lists all module registrations.
- Run a quick import check:

```bash
python -c "from education_system.college_system.modules.domain import *"
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

The primary log file is located at:

```
college_system/logs/app.log
```

Log entries follow the format:

```
2026-03-08 10:15:32,123 - module.name - INFO - Message text
```

- **INFO**: Normal operations (logged to file only).
- **WARNING**: Potential issues (logged to file and console).
- **ERROR**: Failures that need attention.

To increase log verbosity, modify the logging level in `core/logs.py` or set it programmatically:

```python
from education_system.college_system.core.logs import configure_logging
import logging
configure_logging(level=logging.DEBUG)
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
sqlite3 education_system/college_system/data/db_files/sixthform.db

# List all tables
.tables

# Check a specific table's schema
.schema users

# Count records
SELECT COUNT(*) FROM users;

# Exit
.quit
```

### Check the Exception Hierarchy

The system uses a structured exception hierarchy rooted at `CollegeSystemError`. Key exception classes defined in `core/exceptions.py`:

| Exception | Purpose |
|-----------|---------|
| `CollegeSystemError` | Base exception for all system errors |
| `DatabaseError` | Database operation failures |
| `AuthError` | Authentication and authorization failures |
| `ValidationError` | Input validation failures |
| `StudentError` | Student record errors |
| `CourseError` | Course management errors |
| `EnrollmentError` | Enrollment processing errors |
| `GradeError` | Grade management errors |
| `AttendanceError` | Attendance tracking errors |
| `TimetableError` | Timetable scheduling errors |
| `AssignmentError` | Assignment management errors |
| `NotificationError` | Notification delivery errors |

When debugging, catch `CollegeSystemError` to handle all application-level errors, or catch specific subclasses for targeted handling.

### Reset to a Clean State

If all else fails and you are in a development environment, you can reset the system to its initial state:

```bash
# Remove the database (destroys all data)
rm -f education_system/college_system/data/db_files/sixthform.db

# Remove log files
rm -f education_system/college_system/logs/app.log

# Restart the application -- database and defaults will be recreated
```

---

**Last Updated**: March 2026
**Version**: 1.0.0
