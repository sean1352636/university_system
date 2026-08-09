# Secondary School Management System - Database Guide

> Last Updated: March 2026

## Overview

The Secondary School Management System uses SQLite as its database engine, storing all domain data in a single database file. Authentication data is stored separately in a shared auth database used across all four Education System platforms.

## Database Files

| Database | Path | Purpose |
|----------|------|---------|
| Secondary School DB | `secondary_school/data/db_files/secondary_school.db` | All domain data (students, academics, pastoral, etc.) |
| Shared Auth DB | `education_system/shared/data/db_files/auth.db` | Authentication, sessions, MFA (shared across all 4 systems) |

## Tables by Domain Category

### Academics

| Table | Description |
|-------|-------------|
| `students` | Student records (ID format: SEC0001) |
| `subjects` | Subject definitions and metadata |
| `enrollment` | Student-subject enrollment records |
| `grades` | GCSE grades (9-1 scale) |
| `attendance` | Daily and lesson-level attendance |
| `timetable` | Lesson schedules and room assignments |
| `homework` | Homework assignments and submissions |
| `exams` | Exam schedules and results |
| `progress` | Student progress tracking |
| `interventions` | Academic intervention records |
| `reports` | Student reports and report cards |

### Pastoral Care

| Table | Description |
|-------|-------------|
| `behaviour_incidents` | Behaviour incident records |
| `detentions` | Detention records and attendance |
| `exclusions` | Fixed-term and permanent exclusion records |
| `rewards` | Reward points and achievements |
| `safeguarding_concerns` | Safeguarding referrals (restricted access) |
| `send_records` | Special Educational Needs and Disabilities records |
| `pastoral_notes` | General pastoral notes per student |

### Staff

| Table | Description |
|-------|-------------|
| `staff` | Staff records (ID format: STF0001) |
| `hr` | HR records (contracts, absences) |
| `cpd` | Continuing Professional Development records |
| `cover` | Cover lesson arrangements |

### Administration

| Table | Description |
|-------|-------------|
| `users` | Local user preferences (auth handled by shared DB) |
| `settings` | System configuration key-value pairs |
| `admissions` | Admissions applications and decisions |
| `finance` | Financial records and transactions |
| `audit_log` | System audit trail |
| `policies` | School policy documents |
| `documents` | General document storage and metadata |
| `data_exports` | Data export history and records |

### Student Life

| Table | Description |
|-------|-------------|
| `clubs` | Extracurricular clubs and memberships |
| `meals` | Meal choices and dietary information |
| `transport` | Transport arrangements |
| `trips` | School trip records and consent |
| `careers` | Careers guidance records |
| `library` | Library catalogue and loans |
| `medical` | Medical records and conditions |
| `form_groups` | Form group assignments |
| `consent` | Parental consent records |

### Facilities

| Table | Description |
|-------|-------------|
| `room_bookings` | Room booking records |
| `assets` | Asset register and tracking |
| `seating_plans` | Classroom seating plan layouts |
| `visitors` | Visitor sign-in records |
| `incidents` | Facility incident reports |

### Communication

| Table | Description |
|-------|-------------|
| `email` | Email message records |
| `notifications` | System notification records |
| `announcements` | School-wide announcements |
| `calendar` | Calendar events |
| `parents_evening` | Parents evening bookings |
| `communication_log` | Communication audit trail |

## Connection Patterns

All database access follows a consistent connection pattern using `_conn()` helper functions.

### Standard Pattern

```python
from infrastructure.database import connect

DB_PATH = "data/db_files/secondary_school.db"

def _conn():
    """Create a new database connection."""
    return connect(DB_PATH)

def get_student(student_id):
    """Retrieve a student record by ID."""
    conn = _conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        return cursor.fetchone()
    except Exception as e:
        raise
    finally:
        conn.close()
```

### Write Operations with Commit

```python
def add_student(student_data):
    """Insert a new student record."""
    conn = _conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (student_id, first_name, last_name, year_group) VALUES (?, ?, ?, ?)",
            (student_data["id"], student_data["first_name"],
             student_data["last_name"], student_data["year_group"])
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### Key Rules

1. **Always use parameterised queries** -- never use string formatting or f-strings for SQL values.
2. **Always close connections** in a `finally` block.
3. **Always call `conn.rollback()`** in `except` blocks for write operations.
4. **One connection per operation** -- do not share connections across threads.

## Schema Initialisation

Database tables are created on first run via schema initialisation scripts. Each domain module registers its required tables during application startup.

```python
def init_schema(conn):
    """Create tables if they do not exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            year_group INTEGER NOT NULL CHECK(year_group BETWEEN 7 AND 11),
            key_stage TEXT NOT NULL CHECK(key_stage IN ('KS3', 'KS4')),
            form_group TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
```

Year groups map to key stages as follows:

| Year Group | Key Stage |
|------------|-----------|
| Year 7 | KS3 |
| Year 8 | KS3 |
| Year 9 | KS3 |
| Year 10 | KS4 |
| Year 11 | KS4 |

## WAL Mode

The database uses SQLite WAL (Write-Ahead Logging) mode for improved concurrent read performance:

```python
def connect(db_path):
    """Create a connection with WAL mode enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
```

WAL mode provides:

- **Concurrent reads** -- multiple readers do not block each other.
- **Non-blocking writes** -- readers are not blocked by a writer.
- **Better performance** for read-heavy workloads typical of school systems.

Note: WAL mode creates two additional files alongside the database (`-wal` and `-shm`). These are managed automatically by SQLite and should not be deleted while the database is in use.

## Backup and Restore

### Backup

```bash
# Stop the application before backing up
cp secondary_school/data/db_files/secondary_school.db \
   secondary_school/data/db_files/secondary_school_backup_$(date +%Y%m%d).db
```

Alternatively, use the SQLite online backup API for a consistent snapshot without stopping the application:

```python
import sqlite3

def backup_database(source_path, backup_path):
    """Create a consistent backup using SQLite backup API."""
    source = sqlite3.connect(source_path)
    backup = sqlite3.connect(backup_path)
    try:
        source.backup(backup)
    finally:
        backup.close()
        source.close()
```

### Restore

```bash
# Stop the application first
cp secondary_school/data/db_files/secondary_school_backup_20260310.db \
   secondary_school/data/db_files/secondary_school.db
```

### Backup Recommendations

- Schedule daily automated backups during off-hours.
- Retain at least 30 days of backups for GDPR compliance.
- Store backups in a separate location from the primary database.
- Test restore procedures regularly.
- Back up both `secondary_school.db` and `auth.db` together to maintain consistency.

## GDPR Considerations

Since the Secondary School system handles data for minors (students aged 11-16), additional care is required:

- **Data retention** -- implement automatic purging of student data after the retention period.
- **Right to erasure** -- support data deletion requests via the `data_exports` module.
- **Access logging** -- all data access is recorded in `audit_log`.
- **Encryption at rest** -- consider encrypting the database file in production environments.
- **Minimal data** -- only collect and store data that is necessary for the school's operations.
