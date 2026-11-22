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

**Cause**: The system locks an account after 3 consecutive failed login attempts (`MAX_LOGIN_ATTEMPTS = 3` in `src/education_system/platform/identity/auth/defaults.py`). The lockout lasts 15 minutes (`LOCKOUT_DURATION_MINUTES = 15`).

**Solution**:

1. Wait 15 minutes for the lockout to expire automatically, or
2. Have an administrator unlock the account through **System → User Accounts**, or
3. If no other admin account is available, reset the lock directly in the shared auth database:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('var/data/platform/db_files/auth.db')
conn.execute(\"UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE username = 'admin3'\")
conn.commit()
conn.close()
print('Account unlocked.')
"
```

### Forgotten Default Password

The default credentials, seeded only when `EDU_DEV_SEED=true`, are:

| Role | Username | Password |
|------|----------|----------|
| Super Admin | `superadmin` | `SuperAdmin@123` |
| Admin | `admin3` | `admin1234` |
| Staff | `staff3` | `staff1234` |
| Student | `student3` | `student1234` |
| Parent | `parent3` | `parent1234` |

If these have been changed and forgotten, an administrator must reset the password through **System → User Accounts** or directly in the shared auth database using the password hashing utility in `src/education_system/platform/identity/auth/`.

### MFA Issues

**Symptom**: MFA verification codes are rejected even when entered correctly.

**Solutions**:

- Ensure the device clock is accurate. TOTP codes are time-based and a drift of more than 30 seconds will cause failures.
- If MFA recovery is needed, use one of the recovery codes generated during MFA setup.
- An administrator can disable MFA for the account with `MFAService.disable_mfa` or by updating its `mfa_secrets` row in the shared auth database (`var/data/platform/db_files/auth.db`).
- Check the `mfa_secrets` and `mfa_recovery_codes` tables in the auth database for the account state.

### Session Timeout

**Symptom**: A session token is rejected as expired.

**Cause**: Sessions expire 30 minutes after they are created by default (`SESSION_TIMEOUT_MINUTES` in `src/education_system/platform/identity/auth/defaults.py`).

**Solution**: Set the `EDU_SESSION_TIMEOUT` environment variable to the number of minutes you want.

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
lsof var/data/primary/primary.db
```

3. If a stale lock exists (e.g., after a crash), remove any leftover WAL and SHM files:

```bash
rm -f var/data/primary/primary.db-wal
rm -f var/data/primary/primary.db-shm
```

4. Restart the application.

### Database Does Not Exist or Is Empty

**Symptom**: The application fails at startup with file-not-found errors or shows no data.

**Cause**: The database has not been initialized, or the data directory was deleted.

**Solution**: The system creates the database automatically on first run. Ensure the data directories exist:

```bash
# The application creates this automatically, but you can do it manually:
mkdir -p var/data/primary
```

Then restart the application. Each module recreates its tables when first used.

### Schema Migration Issues

**Symptom**: Errors referencing missing columns or tables after an update.

**Cause**: The database schema was created with an older version and the new code expects additional tables or columns.

**Solution**:

1. Back up the existing database:

```bash
mkdir -p var/backups/primary
cp var/data/primary/primary.db var/backups/primary/primary.db.backup
```

2. Primary modules add missing tables and some columns from their own `init_db()`; these tables are not managed by Alembic. If a schema still does not match, the simplest approach for development environments is to delete the database and let it be recreated:

```bash
rm var/data/primary/primary.db
# Restart the application -- the tables will be recreated
```

**Warning**: Deleting the database destroys all data. Only do this in development or after making a backup.

### Database Backup and Restore

To manually back up the database:

```bash
# Backup
mkdir -p var/backups/primary
cp var/data/primary/primary.db var/backups/primary/primary_$(date +%Y%m%d_%H%M%S).db

# Restore from backup
cp var/backups/primary/primary_20260310_120000.db var/data/primary/primary.db
```

Remember to also back up the shared auth database if needed:

```bash
mkdir -p var/backups/platform
cp var/data/platform/db_files/auth.db var/backups/platform/auth_$(date +%Y%m%d_%H%M%S).db
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
xvfb-run python -m education_system --primary --gui
```

### GUI Freezes or Becomes Unresponsive

**Symptom**: The GUI stops responding to clicks or keyboard input.

**Cause**: A long-running operation is blocking the main tkinter event loop.

**Solutions**:

- Wait for the operation to complete. Database operations on large datasets may take time.
- Check the console for errors that may indicate an infinite loop or deadlock.
- If the application is completely stuck, terminate the process and restart.

### Sidebar Modules Not Loading

**Symptom**: The sidebar appears but some or all modules are missing.

**Solutions**:

- Check the console for import errors. A syntax error or missing dependency in one module can prevent it from loading.
- Verify that the module has an entry in `NAV_CATEGORIES` in `src/education_system/systems/primary/gui_main.py`.
- Run a quick import check:

```bash
python -c "import education_system.systems.primary.gui_main"
```

Any import errors will be printed to the console.

---

## CLI Issues

### System Switching Returns to Wrong Menu

**Symptom**: After switching between systems via the universal login, the CLI returns to the wrong system's menu or shows an unexpected prompt.

**Solution**:

- Exit the CLI completely and re-launch with the explicit flag:

```bash
python -m education_system --primary --cli
```

- If using the universal login (`python -m education_system`), ensure you select "Primary School" when prompted for a system.

### CLI Logout Does Not Return to Login

**Symptom**: Logging out from the CLI exits the application entirely instead of returning to the login prompt.

**Solution**: This is expected behaviour when launching with `--primary --cli`. The system exits on logout. To return to the universal login, launch without a system flag:

```bash
python -m education_system
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
4. Return to **Assessment** to record grades (BLW, WTS, EXS, GDS).

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

The Primary School writes no log file of its own; the launcher logs to the console.

Log entries follow the format:

```
2026-03-10 10:15:32 - Message text
```

- **INFO**: Normal operations (hidden unless verbose).
- **WARNING**: Potential issues (shown on the console).
- **ERROR**: Failures that need attention.

To increase log verbosity, start with `--verbose`, or set `EDU_VERBOSE=1`:

```bash
python -m education_system --primary --gui --verbose
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
sqlite3 var/data/primary/primary.db

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
sqlite3 var/data/platform/db_files/auth.db

.tables
SELECT username, locked_until, failed_login_attempts FROM users;
.quit
```

### Check the Exceptions

The Primary School has no system-wide exception hierarchy. Domain modules raise `ValidationError` for invalid input, using their own class or the one in `src/education_system/systems/primary/domain/learners/pupils/pupils.py`. Screens and CLI handlers catch it and show its message. Anything else is logged with a traceback and shown as a general error.

When debugging, look for that traceback on the console.

### Reset to a Clean State

If all else fails and you are in a development environment, you can reset the system to its initial state:

```bash
# Remove the primary school database (destroys all data)
rm -f var/data/primary/primary.db

# Restart the application -- the tables will be recreated
python -m education_system --primary --gui
```

**Warning**: This destroys all primary school data. The shared auth database is not affected. Only do this in development or after making a backup.

---

**Last Updated**: October 2026
