# Troubleshooting Guide

Solutions to common issues with the Primary School Management System.

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

**Cause**: The system locks an account after 5 consecutive failed login attempts (`MAX_LOGIN_ATTEMPTS = 5` in `core/defaults.py`). The lockout lasts 15 minutes (`LOCKOUT_DURATION = 15`).

**Solution**:

1. Wait 15 minutes for the lockout to expire automatically, or
2. Have an administrator unlock the account through the **Users** module, or
3. If no other admin account is available, reset the lock directly in the shared auth database:

```bash
source venv/bin/activate
python -c "
import sqlite3
conn = sqlite3.connect('education_system/shared/data/db_files/auth.db')
conn.execute(\"UPDATE users SET failed_attempts = 0, locked = 0 WHERE username = 'primary_admin'\")
conn.commit()
conn.close()
print('Account unlocked.')
"
```

### Forgotten Default Password

The default credentials seeded on first run are:

| Role | Username | Password |
|------|----------|----------|
| Super Admin | `superadmin` | `SuperAdmin@123` |
| Admin | `admin3` | `admin1234` |
| Staff | `staff3` | `staff1234` |
| Student | `student3` | `student1234` |
| Parent | `parent3` | `parent1234` |

If these have been changed and forgotten, an administrator must reset the password through the Users module or directly in the shared auth database using the password hashing utility in `shared/auth/`.

### MFA Issues

**Symptom**: MFA verification codes are rejected even when entered correctly.

**Solutions**:

- Ensure the device clock is accurate. TOTP codes are time-based and a drift of more than 30 seconds will cause failures.
- If MFA recovery is needed, use one of the recovery codes generated during MFA setup.
- An administrator can disable MFA for the account through the user management interface or by updating the user record in the shared auth database (`education_system/shared/data/db_files/auth.db`).
- Check the `mfa_secrets` and `mfa_recovery_codes` tables in the auth database for the account state.

### Session Timeout

**Symptom**: You are logged out unexpectedly.

**Cause**: Sessions expire after 30 minutes of inactivity by default (`SESSION_TIMEOUT = 30` in `core/defaults.py`).

**Solution**: The session timeout is configured in `primary_school/core/defaults.py`. To adjust:

1. Modify the `SESSION_TIMEOUT` value in `core/defaults.py`, or
2. Set the appropriate environment variable if one is supported by your deployment.

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
lsof education_system/primary_school/data/db_files/primary_school.db
```

3. If a stale lock exists (e.g., after a crash), remove the WAL and SHM files if present:

```bash
rm -f education_system/primary_school/data/db_files/primary_school.db-wal
rm -f education_system/primary_school/data/db_files/primary_school.db-shm
```

4. Restart the application.

### Database Does Not Exist or Is Empty

**Symptom**: The application fails at startup with file-not-found errors or shows no data.

**Cause**: The database has not been initialized, or the data directory was deleted.

**Solution**: The system creates the database automatically on first run. Ensure the data directories exist:

```bash
# The application creates these automatically, but you can do it manually:
mkdir -p education_system/primary_school/data/db_files
mkdir -p education_system/primary_school/data/config
mkdir -p education_system/primary_school/logs
```

Then restart the application. The schema initialization and default data seeding will recreate the database.

### Schema Migration Issues

**Symptom**: Errors referencing missing columns or tables after an update.

**Cause**: The database schema was created with an older version and the new code expects additional tables or columns.

**Solution**:

1. Back up the existing database:

```bash
cp education_system/primary_school/data/db_files/primary_school.db \
   education_system/primary_school/data/db_files/primary_school.db.backup
```

2. If the application includes migration scripts, run them. Otherwise, the simplest approach for development environments is to delete the database and let it be recreated:

```bash
rm education_system/primary_school/data/db_files/primary_school.db
# Restart the application -- schema and seed data will be recreated
```

**Warning**: Deleting the database destroys all data. Only do this in development or after making a backup.

### Database Backup and Restore

To manually back up the database:

```bash
# Backup
cp education_system/primary_school/data/db_files/primary_school.db \
   education_system/primary_school/data/db_files/primary_school_$(date +%Y%m%d_%H%M%S).db

# Restore from backup
cp education_system/primary_school/data/db_files/primary_school_20260310_120000.db \
   education_system/primary_school/data/db_files/primary_school.db
```

Remember to also back up the shared auth database if needed:

```bash
cp education_system/shared/data/db_files/auth.db \
   education_system/shared/data/db_files/auth_$(date +%Y%m%d_%H%M%S).db
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
xvfb-run python run.py --primary --gui
```

### GUI Freezes or Becomes Unresponsive

**Symptom**: The GUI stops responding to clicks or keyboard input.

**Cause**: A long-running operation is blocking the main tkinter event loop.

**Solutions**:

- Wait for the operation to complete. Database operations on large datasets may take time.
- Check `primary_school/logs/app.log` for errors that may indicate an infinite loop or deadlock.
- If the application is completely stuck, terminate the process and restart.

### Sidebar Modules Not Loading

**Symptom**: The sidebar appears but some or all modules are missing.

**Solutions**:

- Check the console and log file for import errors. A syntax error or missing dependency in one module can prevent it from loading.
- Verify that the `modules/domain/__init__.py` files correctly list all module registrations.
- Run a quick import check:

```bash
python -c "from education_system.primary_school.modules.domain import *"
```

Any import errors will be printed to the console.

---

## CLI Issues

### System Switching Returns to Wrong Menu

**Symptom**: After switching between systems via the universal login, the CLI returns to the wrong system's menu or shows an unexpected prompt.

**Solution**:

- Exit the CLI completely and re-launch with the explicit flag:

```bash
python run.py --primary --cli
```

- If using the universal login (`python run.py`), ensure you select "Primary School" when prompted for a system.

### CLI Logout Does Not Return to Login

**Symptom**: Logging out from the CLI exits the application entirely instead of returning to the login prompt.

**Solution**: This is expected behaviour when launching with `--primary --cli`. The system exits on logout. To return to the universal login, launch without a system flag:

```bash
python run.py
```

### CLI Menu Displays Incorrectly

**Symptom**: Menu options are garbled or misaligned in the terminal.

**Solution**: Ensure your terminal supports UTF-8 encoding and has a width of at least 80 characters. Set the locale if needed:

```bash
export LANG=en_GB.UTF-8
```

---

## Module-Specific Issues

### Attendance Module Shows No Classes

**Symptom**: The attendance register is empty with no classes to mark.

**Cause**: Attendance registers are linked to classes and the timetable. If no classes or timetable entries exist, no registers appear.

**Solution**: Populate the **Classes** module with class groups and pupils first, then set up the **Timetable**. Return to **Attendance** to see available registers.

### Assessment Module Shows Empty Records

**Symptom**: The assessment module shows no pupils or no assessment data.

**Cause**: Assessment records depend on pupils being assigned to classes and subjects being configured.

**Solution**:

1. Add pupils via the **Pupils** module.
2. Create subjects via the **Subjects** module.
3. Assign pupils to classes via the **Classes** module.
4. Return to **Assessment** to record levels (Emerging, Developing, Expected, Greater Depth).

### SATs Module Has No Data

**Symptom**: The SATs module appears empty or shows no eligible pupils.

**Cause**: SATs are relevant to Year 2 (KS1) and Year 6 (KS2) pupils only.

**Solution**: Ensure pupils are assigned to Year 2 or Year 6 year groups. Only pupils in these year groups will appear in SATs tracking.

### Phonics Module Has No Data

**Symptom**: The phonics screening module shows no pupils.

**Cause**: The Year 1 phonics screening check applies to Year 1 pupils (and Year 2 retakes).

**Solution**: Ensure pupils are assigned to Year 1 (or Year 2 for retakes) to see them in the phonics module.

---

## General Debugging Tips

### Check the Log Files

The primary log file is located at:

```
primary_school/logs/app.log
```

Log entries follow the format:

```
2026-03-10 10:15:32,123 - module.name - INFO - Message text
```

- **INFO**: Normal operations (logged to file only).
- **WARNING**: Potential issues (logged to file and console).
- **ERROR**: Failures that need attention.

To increase log verbosity, modify the logging level in `core/logs.py` or set it programmatically:

```python
from education_system.primary_school.core.logs import configure_logging
import logging
configure_logging(level=logging.DEBUG)
```

### Verify the Python Environment

Ensure you are using the correct virtual environment:

```bash
which python
# Should point to: python (or your venv path)

python -c "import tkinter; print('tkinter OK')"
python -c "import sqlite3; print('sqlite3 OK')"
```

### Inspect the Database Directly

Use the SQLite command-line tool to inspect the database:

```bash
sqlite3 education_system/primary_school/data/db_files/primary_school.db

# List all tables
.tables

# Check a specific table's schema
.schema pupils

# Count records
SELECT COUNT(*) FROM pupils;

# Exit
.quit
```

For the shared auth database:

```bash
sqlite3 education_system/shared/data/db_files/auth.db

.tables
SELECT username, locked, failed_attempts FROM users;
.quit
```

### Check the Exception Hierarchy

The system uses a structured exception hierarchy rooted at `SchoolSystemError`. Key exception classes defined in `primary_school/core/exceptions.py`:

| Exception | Category | Purpose |
|-----------|----------|---------|
| `SchoolSystemError` | Base | Base exception for all system errors |
| `ValidationError` | Base | Input validation failures |
| `PupilError` | Academics | Pupil record errors |
| `SubjectError` | Academics | Subject management errors |
| `ClassError` | Academics | Class group errors |
| `AssessmentError` | Academics | Assessment recording errors |
| `AttendanceError` | Academics | Attendance tracking errors |
| `TimetableError` | Academics | Timetable scheduling errors |
| `HomeworkError` | Academics | Homework management errors |
| `SATsError` | Academics | SATs tracking errors |
| `PhonicsError` | Academics | Phonics screening errors |
| `ReadingRecordError` | Academics | Reading record errors |
| `ProgressError` | Academics | Progress tracking errors |
| `BehaviourError` | Pastoral | Behaviour incident errors |
| `RewardsError` | Pastoral | Rewards management errors |
| `SafeguardingError` | Pastoral | Safeguarding concern errors |
| `SENDError` | Pastoral | SEND tracking errors |
| `PastoralError` | Pastoral | Pastoral care errors |
| `StaffError` | Staff | Staff record errors |
| `HRError` | Staff | HR management errors |
| `CPDError` | Staff | CPD record errors |
| `CoverError` | Staff | Cover allocation errors |
| `UserManagementError` | Admin | User account errors |
| `SettingsError` | Admin | Settings configuration errors |
| `AdmissionsError` | Admin | Admissions processing errors |
| `FinanceError` | Admin | Financial management errors |
| `AuditError` | Admin | Audit log errors |
| `PolicyError` | Admin | Policy management errors |
| `DocumentError` | Admin | Document management errors |
| `ClubsError` | Pupil Life | Club management errors |
| `MealsError` | Pupil Life | Meal management errors |
| `TransportError` | Pupil Life | Transport arrangement errors |
| `TripsError` | Pupil Life | Trip management errors |
| `LibraryError` | Pupil Life | Library management errors |
| `MedicalError` | Pupil Life | Medical record errors |
| `ClassGroupError` | Pupil Life | Class group errors |
| `ConsentError` | Pupil Life | Consent tracking errors |
| `EmailError` | Communication | Email delivery errors |
| `NotificationError` | Communication | Notification errors |
| `AnnouncementError` | Communication | Announcement errors |
| `CalendarError` | Communication | Calendar management errors |
| `ParentsEveningError` | Communication | Parents evening errors |
| `CommunicationLogError` | Communication | Communication log errors |
| `RoomBookingError` | Facilities | Room booking errors |
| `AssetError` | Facilities | Asset tracking errors |
| `VisitorError` | Facilities | Visitor management errors |
| `IncidentError` | Facilities | Incident reporting errors |

When debugging, catch `SchoolSystemError` to handle all application-level errors, or catch specific subclasses for targeted handling.

### Reset to a Clean State

If all else fails and you are in a development environment, you can reset the system to its initial state:

```bash
# Remove the primary school database (destroys all data)
rm -f education_system/primary_school/data/db_files/primary_school.db

# Remove log files
rm -f education_system/primary_school/logs/app.log

# Restart the application -- database and defaults will be recreated
python run.py --primary --gui
```

**Warning**: This destroys all primary school data. The shared auth database is not affected. Only do this in development or after making a backup.

---

**Last Updated**: March 2026
**Version**: 1.0.0
