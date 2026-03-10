# Primary School Database Guide

> Last Updated: March 2026

## Overview

The Primary School Management System uses SQLite as its database engine, storing all domain data in a single file at:

```
education_system/primary_school/data/db_files/primary_school.db
```

Authentication data is stored separately in the shared auth database:

```
education_system/shared/data/db_files/auth.db
```

This separation ensures that authentication concerns are decoupled from domain data and shared consistently across all four Education System subsystems (University, College, Secondary School, Primary School).

---

## Table Listing by Domain Category

### Academics

| Table | Description |
|---|---|
| `pupils` | Core pupil records (PRI0001 format IDs). Name, DOB, year group, key stage, class, status. |
| `subjects` | Subjects offered (English, Maths, Science, etc.) across EYFS, KS1, KS2. |
| `classes` | Class/form groups with assigned teacher and year group. |
| `assessment_records` | Per-pupil assessment entries. Levels: Emerging, Developing, Expected, Greater Depth. |
| `attendance` | Daily and session-level attendance marks per pupil. |
| `timetable` | Lesson scheduling: subject, class, room, teacher, day, period. |
| `homework` | Homework assignments with set/due dates, subject, class. |
| `sats_results` | Key Stage 1 and Key Stage 2 SATs results. |
| `phonics_screening` | Year 1 (and Year 2 retake) phonics screening check results. |
| `reading_records` | Reading log entries: book, level, date, notes. |
| `progress_records` | Longitudinal progress tracking across terms and year groups. |

### Pastoral Care

| Table | Description |
|---|---|
| `behaviour_incidents` | Behaviour incident records with type, severity, action taken. |
| `rewards` | Positive recognition: house points, stickers, certificates. |
| `safeguarding_concerns` | Safeguarding referrals and concern logs. Access-restricted. |
| `send_records` | Special Educational Needs and Disabilities records, support plans. |
| `pastoral_notes` | General pastoral care notes per pupil. |

### Staff

| Table | Description |
|---|---|
| `staff` | Staff directory records (STF0001 format IDs). Includes HR data. |
| `cpd` | Continuing Professional Development records and training logs. |
| `cover` | Cover arrangements for absent staff. |

### Admin

| Table | Description |
|---|---|
| `users` | Local user records (references shared auth for login). |
| `settings` | Application settings and preferences. |
| `admissions` | Pupil admission applications and status tracking. |
| `finance` | Financial records: fees, payments, budgets. |
| `data_exports` | Log of data export operations for audit purposes. |
| `audit_log` | System-wide audit trail of user actions. |
| `policies` | School policy documents and metadata. |
| `documents` | Document storage metadata and references. |

### Pupil Life

| Table | Description |
|---|---|
| `clubs` | Extra-curricular clubs and pupil memberships. |
| `meals` | Meal preferences, free school meals (FSM) status, dietary needs. |
| `transport` | Transport arrangements (bus routes, walking, parent pickup). |
| `trips` | School trip records with consent tracking. |
| `library` | Library catalogue and loan records. |
| `medical` | Medical conditions, medications, care plans. |
| `class_groups` | Class group assignments and history. |
| `consent` | Parental consent records (photos, trips, data sharing). |

### Facilities

| Table | Description |
|---|---|
| `room_bookings` | Room and resource booking records. |
| `assets` | School asset inventory and tracking. |
| `visitors` | Visitor sign-in/out log. |
| `incidents` | Health & safety incident reports. |

### Communication

| Table | Description |
|---|---|
| `announcements` | School announcements and bulletins. |
| `calendar_events` | School calendar events (term dates, INSET days, assemblies). |
| `parents_evening` | Parents' evening scheduling and appointment slots. |
| `communication_log` | Record of communications sent (letters, emails, SMS). |
| `notifications` | In-app notification queue per user. |
| `email_queue` | Outbound email queue with status tracking. |

---

## Connection Patterns

All database access follows the service layer pattern used across the Education System platform.

### Standard Connection Pattern

```python
from infrastructure.database import connect
from core.paths import DB_PATH

class PupilService:
    def _conn(self):
        """Create a new database connection."""
        return connect(DB_PATH)

    def get_pupil(self, pupil_id: str) -> dict | None:
        conn = self._conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM pupils WHERE pupil_id = ?",
                (pupil_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            raise
        finally:
            conn.close()
```

### Key Rules

1. **Always use `_conn()`** to obtain connections -- never construct them directly in business logic.
2. **Always close connections** in a `finally` block to prevent resource leaks.
3. **Always use parameterized queries** (`?` placeholders) -- never interpolate user input into SQL strings.
4. **Use `try/except/finally`** for every database operation to ensure cleanup on error.

### Write Operations

```python
def add_pupil(self, data: dict) -> str:
    conn = self._conn()
    try:
        conn.execute(
            """INSERT INTO pupils (pupil_id, first_name, last_name, dob, year_group, key_stage)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["pupil_id"], data["first_name"], data["last_name"],
             data["dob"], data["year_group"], data["key_stage"])
        )
        conn.commit()
        return data["pupil_id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

---

## Schema Initialization

The database schema is **auto-created on first run**. When the application starts, it checks for the existence of `primary_school.db` and creates all required tables if the file does not exist or is empty.

Initialization is handled by the database infrastructure module:

```
education_system/primary_school/infrastructure/database/
```

Each domain module may also register its own tables during initialization, ensuring the schema is always up to date.

### Manual Re-initialization

To reset the database (destroys all data):

```bash
rm education_system/primary_school/data/db_files/primary_school.db
/home/seancatchpole989/venv/bin/python run.py
```

The schema will be recreated automatically on the next launch.

---

## Backup and Restore

### Creating a Backup

SQLite databases can be backed up by copying the file while no writes are in progress:

```bash
# Stop the application first, or use SQLite's backup API
cp education_system/primary_school/data/db_files/primary_school.db \
   education_system/primary_school/data/db_files/primary_school_backup_$(date +%Y%m%d_%H%M%S).db
```

For a live backup without stopping the application (using SQLite's `.backup` command):

```bash
sqlite3 education_system/primary_school/data/db_files/primary_school.db \
  ".backup 'education_system/primary_school/data/db_files/primary_school_backup.db'"
```

### Restoring from Backup

```bash
# Stop the application
cp education_system/primary_school/data/db_files/primary_school_backup.db \
   education_system/primary_school/data/db_files/primary_school.db
```

### Backup Recommendations

- Schedule daily automated backups of both `primary_school.db` and `auth.db`.
- Retain at least 30 days of rolling backups.
- Store backups in a separate location from the application server.
- Test restore procedures termly.
- Encrypt backups at rest (the database contains data about minors).

---

## WAL Mode and Concurrency

SQLite is configured to use **Write-Ahead Logging (WAL)** mode for improved concurrent read performance.

### What WAL Mode Provides

- **Multiple concurrent readers** can access the database simultaneously without blocking.
- **A single writer** can write while readers continue to read from a consistent snapshot.
- Improved performance for read-heavy workloads typical of school management systems.

### WAL Mode Files

When WAL mode is active, two additional files appear alongside the database:

```
primary_school.db          # Main database file
primary_school.db-wal      # Write-ahead log
primary_school.db-shm      # Shared memory index
```

These files are managed automatically by SQLite. Do not delete them while the application is running.

### Concurrency Limitations

- SQLite allows only **one writer at a time**. Concurrent writes will queue (with a configurable busy timeout).
- For the Primary School system's expected load (single school, tens of concurrent users), SQLite provides adequate performance.
- If the application is deployed behind a multi-process web server, ensure the busy timeout is set appropriately to avoid `database is locked` errors.

### Configuration

WAL mode is typically enabled during database initialization:

```python
conn.execute("PRAGMA journal_mode=WAL")
```

The busy timeout is set to prevent immediate failures on write contention:

```python
conn.execute("PRAGMA busy_timeout=5000")  # 5 seconds
```
