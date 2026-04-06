# Troubleshooting Guide

Solutions to common issues with the Secondary School Management System.

---

## Table of Contents

1. [Login and Authentication Problems](#login-and-authentication-problems)
2. [Database Issues](#database-issues)
3. [GUI Issues](#gui-issues)
4. [CLI Issues](#cli-issues)
5. [Module-Specific Issues](#module-specific-issues)
6. [General Debugging Tips](#general-debugging-tips)

---

## Login and Authentication Problems

### Account Locked After Failed Login Attempts

**Symptom**: You see a message such as "Account locked" or "Too many failed login attempts" when trying to log in.

**Cause**: The system locks an account after 5 consecutive failed login attempts (`MAX_LOGIN_ATTEMPTS = 5` in `secondary_school/core/defaults.py`).

**Solution**:

1. Wait for the lockout period to expire (if a timed lockout is configured), or
2. Have an administrator unlock the account through the **Users** module, or
3. If no other admin account is available, reset the lock directly in the shared auth database:

```bash
source venv/bin/activate
python -c "
import sqlite3
conn = sqlite3.connect('education_system/shared/data/db_files/auth.db')
conn.execute(\"UPDATE users SET failed_attempts = 0, locked = 0 WHERE username = 'school_admin'\")
conn.commit()
conn.close()
print('Account unlocked.')
"
```

### Forgotten Default Password

The default credentials seeded on first run via shared authentication are:

| Role | Username | Password |
|------|----------|----------|
| Super Admin | `superadmin` | `SuperAdmin@123` |
| Admin | `admin2` | `admin1234` |
| Staff | `staff2` | `staff1234` |
| Student | `student2` | `student1234` |

If these have been changed and forgotten, an administrator must reset the password through the **Users** module or directly in the shared auth database using the password hashing utility in `shared/auth/`.

### MFA Issues

**Symptom**: MFA verification codes are rejected even when entered correctly.

**Solutions**:

- Ensure the device clock is accurate. TOTP codes are time-based and a drift of more than 30 seconds will cause failures.
- If MFA recovery is needed, use one of the stored recovery codes. Each recovery code is single-use.
- An administrator can disable MFA for the account through the MFA management interface or by updating the user record in the shared `auth.db` database.
- MFA secrets and recovery codes are stored in the `mfa_secrets` and `mfa_recovery_codes` tables in `shared/data/db_files/auth.db`.

### Session Timeout

**Symptom**: You are logged out unexpectedly.

**Cause**: Sessions expire after 30 minutes of inactivity by default (`SESSION_TIMEOUT = 30` in `secondary_school/core/defaults.py`).

**Solution**: The session timeout is configured in `secondary_school/core/defaults.py`. For development, you can increase the value. Sessions are stored in the `sessions` table of the shared `auth.db` database.

---

## Database Issues

### SQLite Database Locked

**Symptom**: Operations fail with `database is locked` errors.

**Cause**: SQLite uses file-level locking. This typically occurs when:

- Multiple processes are writing to the database simultaneously.
- A long-running transaction holds the lock.
- A crashed process left a stale lock file.

**Solutions**:

1. Ensure only one instance of the application writes to the database at a time.
2. Check for lingering processes:

```bash
# Find processes using the database file
lsof education_system/secondary_school/data/db_files/secondary_school.db
```

3. If a stale lock exists (e.g., after a crash), remove the WAL and SHM files if present:

```bash
rm -f education_system/secondary_school/data/db_files/secondary_school.db-wal
rm -f education_system/secondary_school/data/db_files/secondary_school.db-shm
```

4. Restart the application.

### Database Does Not Exist or Is Empty

**Symptom**: The application fails at startup with file-not-found errors or shows no data.

**Cause**: The database has not been initialized, or the data directory was deleted.

**Solution**: The system creates the database automatically on first run. Ensure the data directories exist:

```bash
# The application creates these automatically, but you can do it manually:
mkdir -p education_system/secondary_school/data/db_files
mkdir -p education_system/secondary_school/data/config
mkdir -p education_system/secondary_school/logs
```

Then restart the application. The database initialization and seeding functions will recreate the schema and seed default data.

### Schema Migration Issues

**Symptom**: Errors referencing missing columns or tables after an update.

**Cause**: The database schema was created with an older version and the new code expects additional tables or columns.

**Solution**:

1. Back up the existing database:

```bash
cp education_system/secondary_school/data/db_files/secondary_school.db \
   education_system/secondary_school/data/db_files/secondary_school.db.backup
```

2. If the application includes migration scripts, run them. Otherwise, the simplest approach for development environments is to delete the database and let it be recreated:

```bash
rm education_system/secondary_school/data/db_files/secondary_school.db
# Restart the application -- schema and seed data will be recreated
```

**Warning**: Deleting the database destroys all data. Only do this in development or after making a backup.

### Database Backup and Restore

To manually back up the database:

```bash
# Backup
cp education_system/secondary_school/data/db_files/secondary_school.db \
   education_system/secondary_school/data/db_files/secondary_school_$(date +%Y%m%d_%H%M%S).db

# Restore from backup
cp education_system/secondary_school/data/db_files/secondary_school_20260310_120000.db \
   education_system/secondary_school/data/db_files/secondary_school.db
```

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
xvfb-run python run.py --school --gui
```

3. **Check for import errors**: Run the system from a terminal to see any error output:

```bash
python run.py --school --gui 2>&1
```

### GUI Freezes or Becomes Unresponsive

**Symptom**: The GUI stops responding to clicks or keyboard input.

**Cause**: A long-running operation is blocking the main tkinter event loop.

**Solutions**:

- Wait for the operation to complete. Database operations on large datasets may take time.
- Check `secondary_school/logs/app.log` for errors that may indicate an infinite loop or deadlock.
- If the application is completely stuck, terminate the process and restart.

### Sidebar Modules Not Loading

**Symptom**: The sidebar appears but some or all modules are missing.

**Solutions**:

- Check the console and log file for import errors. A syntax error or missing dependency in one module can prevent it from loading.
- Verify that the module registration in `modules/domain/` is correct.
- Run a quick import check:

```bash
python -c "from education_system.secondary_school.modules.domain import *"
```

Any import errors will be printed to the console.

---

## CLI Issues

### System Switching

**Symptom**: The CLI launches the wrong system (e.g., college instead of secondary school).

**Solution**: Ensure you are using the correct launch flag:

```bash
# Secondary school specifically
python run.py --school --cli

# Not --college or --primary
```

### Unexpected Logout in CLI

**Symptom**: The CLI session ends unexpectedly.

**Cause**: The session has timed out (default 30 minutes) or an unhandled error occurred.

**Solutions**:

- Check `secondary_school/logs/app.log` for error messages.
- Re-run the CLI command to start a new session.
- If the issue persists, increase the session timeout in `secondary_school/core/defaults.py`.

---

## Module-Specific Issues

### Attendance Module Shows No Classes

**Symptom**: The attendance register is empty with no classes to mark.

**Cause**: Attendance registers are generated from the timetable. If no timetable entries exist, no registers appear.

**Solution**: Populate the timetable first via the **Timetable** module, then return to **Attendance**.

### Grades Module Shows Empty Grade Sheet

**Symptom**: The grade entry screen shows no students or no assessment columns.

**Cause**: No students are enrolled in the subject, or no assessment periods have been configured.

**Solution**:

1. Verify students are enrolled in the subject via the **Enrollment** module.
2. Check that assessment periods (e.g., Autumn Term, Spring Term) are configured in **Settings** or the **Grades** module.
3. Ensure the correct academic year and term are selected.

### Enrollment Fails with Prerequisite Error

**Symptom**: Enrolling a student in a subject fails with a prerequisite or option block validation error.

**Solution**: Check the subject prerequisites and option block configuration in the **Subjects** module. Ensure the student meets all requirements and that the selected subjects do not clash in the same option block.

### Reports Module Produces Empty Output

**Symptom**: Generating a report produces a blank document or no output.

**Solution**: Verify that the relevant data exists. Reports aggregate data from other modules (grades, attendance, enrollment). If those modules have no records, reports will be empty.

---

## General Debugging Tips

### Check the Log Files

The primary log file is located at:

```
secondary_school/logs/app.log
```

Log entries follow the format:

```
2026-03-10 10:15:32,123 - module.name - INFO - Message text
```

- **INFO**: Normal operations (logged to file only).
- **WARNING**: Potential issues (logged to file and console).
- **ERROR**: Failures that need attention.

To increase log verbosity, modify the logging level in `secondary_school/core/logs.py` or set it programmatically:

```python
from education_system.secondary_school.core.logs import configure_logging
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
sqlite3 education_system/secondary_school/data/db_files/secondary_school.db

# List all tables
.tables

# Check a specific table's schema
.schema students

# Count records
SELECT COUNT(*) FROM students;

# Exit
.quit
```

### Check the Exception Hierarchy

The system uses a structured exception hierarchy rooted at `SchoolSystemError`. Key exception classes defined in `secondary_school/core/exceptions.py`:

| Exception | Purpose |
|-----------|---------|
| `SchoolSystemError` | Base exception for all system errors |
| `DatabaseError` | Database operation failures |
| `AuthError` | Authentication and authorization failures |
| `ValidationError` | Input validation failures |
| `StudentError` | Student record errors |
| `SubjectError` | Subject management errors |
| `EnrollmentError` | Enrollment processing errors |
| `GradeError` | Grade management errors |
| `AttendanceError` | Attendance tracking errors |
| `TimetableError` | Timetable scheduling errors |
| `BehaviourError` | Behaviour incident errors |
| `StaffError` | Staff management errors |
| `EmailError` | Email delivery errors |
| `ExamError` | Exam management errors |
| `HRError` | HR operation errors |
| `FinanceError` | Financial operation errors |
| `ReportError` | Report generation errors |
| `SENDError` | SEND management errors |
| `SafeguardingError` | Safeguarding operation errors |

When debugging, catch `SchoolSystemError` to handle all application-level errors, or catch specific subclasses for targeted handling.

### Reset to a Clean State

If all else fails and you are in a development environment, you can reset the system to its initial state:

```bash
# Remove the database (destroys all data)
rm -f education_system/secondary_school/data/db_files/secondary_school.db

# Remove log files
rm -f education_system/secondary_school/logs/app.log

# Restart the application -- database and defaults will be recreated
python run.py --school --gui
```

**Note**: This does not affect the shared auth database (`shared/data/db_files/auth.db`). To reset authentication as well, an administrator must manage accounts through the shared auth system.

---

**Last Updated**: March 2026
