# Database Infrastructure

This document covers the SQLite database layer for the Sixth Form College Management System, including connection management, schema design, migrations, and best practices.

Source files:

- `infrastructure/database/db.py` -- connection management and pooling
- `infrastructure/database/schema.py` -- table definitions and initialization
- `infrastructure/database/migrations.py` -- schema versioning framework
- `infrastructure/database/constants.py` -- configuration constants

---

## SQLite Setup

The system uses a single SQLite database file located at:

```
college_system/data/db_files/sixthform.db
```

Path resolution is handled by `core/paths.py`, which derives all paths from the project root. The `ensure_directories()` function creates the required directory tree on first run.

The database path can be overridden at runtime (primarily for testing) via `set_db_path(path)`.


## Connection Management

### The `connect()` Function

All database access flows through `connect()` in `db.py`. Each call:

1. Resolves the database path (override or default).
2. Opens a new `sqlite3.Connection` with a 30-second timeout.
3. Sets `row_factory = sqlite3.Row` so query results are accessible by column name.
4. Applies the configured PRAGMAs (see below).
5. Returns the connection or raises `DatabaseError` on failure.

```python
from education_system.college_system.infrastructure.database.db import connect

conn = connect()
row = conn.execute("SELECT * FROM students WHERE id = ?", (1,)).fetchone()
print(row["first_name"])
conn.close()
```

`get_connection()` is a convenience alias for `connect()`.

### PRAGMAs

Every connection applies the following SQLite PRAGMAs (defined in `constants.py`):

| PRAGMA | Value | Purpose |
|---|---|---|
| `journal_mode` | `WAL` | Write-Ahead Logging for concurrent read/write access |
| `foreign_keys` | `ON` | Enforce foreign key constraints |
| `busy_timeout` | `5000` | Wait up to 5 seconds when the database is locked |
| `cache_size` | `-8000` | 8 MB page cache (negative = kibibytes) |
| `synchronous` | `NORMAL` | Balance between safety and write performance |


### Transaction Context Manager

The `transaction()` context manager provides automatic commit/rollback semantics:

```python
from education_system.college_system.infrastructure.database.db import transaction

with transaction() as conn:
    conn.execute("INSERT INTO students (...) VALUES (...)", params)
    conn.execute("INSERT INTO enrollments (...) VALUES (...)", params)
# Commits automatically. Rolls back on any exception.
```

If a connection is passed in, `transaction()` uses it and leaves it open. If no connection is passed, it creates and closes its own.


### Connection Pool

`ConnectionPool` provides a thread-safe pool of reusable connections. Default pool size is configured in `constants.py`:

- **Minimum connections:** 1 (pre-created on init)
- **Maximum connections:** 5
- **Connection timeout:** 30 seconds

The pool expands on demand up to `POOL_MAX_SIZE`. If the pool is exhausted, `get()` blocks until a connection is returned or the timeout expires. When a connection is returned via `put()` and the pool is full, the connection is closed instead.

```python
pool = ConnectionPool()
conn = pool.get()
try:
    cursor = conn.execute("SELECT ...")
finally:
    pool.put(conn)

# Or using the context manager:
with pool.connection() as conn:
    conn.execute("SELECT ...")
```


### DatabaseManager

`DatabaseManager` is a high-level class that combines the connection pool with convenience methods:

| Method | Description |
|---|---|
| `execute(sql, params)` | Run a query, return all rows. Auto-commits. |
| `execute_one(sql, params)` | Run a query, return the first row or `None`. |
| `execute_write(sql, params)` | Run INSERT/UPDATE/DELETE, return `lastrowid` or `rowcount`. |
| `transaction()` | Context manager yielding a connection with commit/rollback. |
| `close()` | Shut down the pool and close all connections. |


---

## Schema Overview

The schema is defined in `schema.py` as a `TABLES` dictionary mapping table names to `CREATE TABLE IF NOT EXISTS` SQL statements. On startup, `init_db()` iterates over all entries and creates any missing tables. `seed_default_data()` populates initial roles, permissions, and default user accounts.

The database contains approximately 180 tables organized into the following domains.


### Authentication and Access Control

| Table | Key Columns | Purpose |
|---|---|---|
| `users` | `id`, `username`, `password_hash`, `role`, `email`, `is_active`, `failed_login_attempts`, `locked_until` | User accounts with lockout support |
| `sessions` | `id`, `user_id` (FK users), `token`, `expires_at`, `is_active` | Session tokens |
| `roles` | `id`, `name`, `description`, `level` | Role definitions with hierarchy level |
| `permissions` | `id`, `role_id` (FK roles), `resource`, `action` | Resource-action permission grants |
| `mfa_secrets` | `id`, `user_id`, `totp_secret`, `is_enabled` | TOTP secrets for MFA |
| `mfa_recovery_codes` | `id`, `user_id`, `code_hash`, `is_used` | Hashed one-time recovery codes |
| `audit_log` | `id`, `user_id`, `username`, `action`, `resource`, `details`, `ip_address`, `timestamp` | Audit trail |


### Students and Enrollment

| Table | Key Columns | Purpose |
|---|---|---|
| `students` | `id`, `student_id` (e.g. SFC0001), `user_id` (FK users), `first_name`, `last_name`, `year_group`, `form_group`, `form_tutor`, `status` | Student records |
| `courses` | `id`, `course_code`, `title`, `credits`, `capacity`, `qualification_type`, `subject_area`, `teacher`, `term`, `status` | Course catalogue |
| `prerequisites` | `course_id` (FK courses), `prerequisite_id` (FK courses) | Course prerequisite links |
| `enrollments` | `student_id` (FK students), `course_id` (FK courses), `status`, `enrolled_at`, `dropped_at` | Enrollment records |
| `waitlist` | `student_id` (FK students), `course_id` (FK courses), `position` | Waitlist queue |


### Grades and Assessment

| Table | Key Columns | Purpose |
|---|---|---|
| `grades` | `student_id` (FK), `course_id` (FK), `score`, `letter_grade`, `grade_type`, `predicted_grade`, `term`, `recorded_by` | Grade records (actual and predicted) |
| `assignments` | `id`, `course_id` (FK), `title`, `due_date`, `max_score` | Assignment definitions |
| `submissions` | `id`, `assignment_id` (FK), `student_id` (FK), `score`, `feedback`, `submitted_at` | Student submissions |
| `markbook_columns` | `id`, `course_id` (FK), `column_name`, `max_marks`, `weight` | Markbook column definitions |
| `markbook_entries` | `id`, `column_id` (FK), `student_id` (FK), `marks`, `grade` | Individual markbook entries |


### Attendance and Timetabling

| Table | Key Columns | Purpose |
|---|---|---|
| `attendance_sessions` | `id`, `course_id` (FK), `session_date`, `topic`, `timetable_slot_id` | Attendance session records |
| `attendance_records` | `session_id` (FK), `student_id` (FK), `status`, `notes` | Per-student attendance marks |
| `timetable_slots` | `id`, `course_id` (FK), `day_of_week` (Mon-Fri), `start_time`, `end_time`, `room`, `instructor_name` | Weekly timetable slots |
| `rooms` | `id`, `room_code`, `building`, `capacity`, `room_type` | Physical rooms |


### Pastoral and Safeguarding

| Table | Key Columns | Purpose |
|---|---|---|
| `safeguarding_concerns` | `id`, `student_id`, `concern_type`, `severity`, `reported_by`, `status` | Safeguarding reports |
| `behaviour_records` | `id`, `student_id`, `incident_type`, `severity`, `reported_by` | Behaviour incidents |
| `pastoral_notes` | `id`, `student_id`, `note_type`, `content`, `created_by` | Pastoral care notes |
| `wellbeing_records` | `id`, `student_id`, `wellbeing_type`, `score`, `notes` | Wellbeing tracking |
| `send_records` | `id`, `student_id`, `send_type`, `status`, `support_plan` | SEND provision records |
| `lac_records` | `id`, `student_id`, `lac_status`, `social_worker`, `pip_targets` | Looked-After Children |


### Exams

| Table | Key Columns | Purpose |
|---|---|---|
| `exam_entries` | `id`, `student_id`, `course_id`, `exam_board`, `entry_code`, `status` | Exam board entries |
| `exam_timetable` | `id`, `course_id`, `exam_date`, `start_time`, `duration`, `venue` | Exam scheduling |
| `exam_access` | `id`, `student_id`, `access_type`, `details` | Access arrangements |
| `exam_results` | `id`, `student_id`, `course_id`, `grade`, `ums_score` | Final exam results |


### Finance and Funding

| Table | Key Columns | Purpose |
|---|---|---|
| `funding_records` | `id`, `student_id`, `funding_type`, `amount`, `status` | Student funding (16-19 bursary, etc.) |
| `bursary_records` | `id`, `student_id`, `bursary_type`, `amount`, `status` | Bursary allocations |
| `fee_items` | `id`, `description`, `amount`, `category` | Fee catalogue |
| `invoices` | `id`, `student_id`, `total`, `status`, `due_date` | Invoices |
| `payments` | `id`, `invoice_id`, `amount`, `method`, `paid_at` | Payment records |
| `payroll_records` | `id`, `staff_id`, `month`, `gross`, `net` | Staff payroll |


### Staff and HR

| Table | Key Columns | Purpose |
|---|---|---|
| `staff` | `id`, `staff_id`, `user_id`, `first_name`, `last_name`, `department`, `role`, `contract_type` | Staff records |
| `staff_hr` | `id`, `staff_id`, `contract_start`, `salary`, `fte` | HR details |
| `cover_arrangements` | `id`, `absent_staff_id`, `cover_staff_id`, `date`, `period` | Cover planning |
| `cpd_records` | `id`, `staff_id`, `title`, `provider`, `hours` | CPD activities |
| `teaching_observations` | `id`, `staff_id`, `observer`, `grade`, `feedback` | Lesson observations |
| `appraisals` | `id`, `staff_id`, `appraiser`, `period`, `overall_grade` | Staff appraisals |
| `dbs_checks` | `id`, `staff_id`, `check_type`, `certificate_number`, `issue_date`, `expiry_date`, `status` | DBS verification |


### Student Life and Support

| Table | Key Columns | Purpose |
|---|---|---|
| `first_aid_incidents` | `id`, `student_id`, `incident_type`, `treatment`, `reported_by` | First aid log |
| `helpdesk_tickets` | `id`, `user_id`, `category`, `subject`, `status`, `priority` | IT/general helpdesk |
| `parent_links` | `id`, `student_id`, `parent_user_id`, `relationship` | Parent-student links |
| `careers_activities` | `id`, `student_id`, `activity_type`, `provider`, `notes` | Careers guidance |
| `ucas_records` | `id`, `student_id`, `personal_id`, `status` | UCAS tracking |
| `destinations` | `id`, `student_id`, `destination_type`, `institution`, `status` | Post-college destinations |
| `transport_records` | `id`, `student_id`, `transport_type`, `route`, `pass_number` | Transport arrangements |
| `library_items` | `id`, `title`, `isbn`, `category`, `status` | Library catalogue |
| `library_loans` | `id`, `item_id`, `borrower_id`, `due_date`, `returned_at` | Library borrowing |


### Communication

| Table | Key Columns | Purpose |
|---|---|---|
| `messages` | `id`, `sender_id`, `recipient_id`, `subject`, `body`, `is_read` | Internal messaging |
| `notifications` | `id`, `user_id`, `title`, `message`, `is_read`, `notification_type` | Push/in-app notifications |
| `announcements` | `id`, `title`, `content`, `author_id`, `target_audience`, `publish_date` | System announcements |
| `calendar_events` | `id`, `title`, `start_datetime`, `end_datetime`, `event_type`, `created_by` | Calendar |


### Quality and Compliance

| Table | Key Columns | Purpose |
|---|---|---|
| `quality_reviews` | `id`, `review_type`, `area`, `grade`, `reviewer` | Quality reviews |
| `compliance_checks` | `id`, `check_type`, `area`, `status`, `checked_by` | Compliance tracking |
| `sef_sections` | `id`, `section_name`, `grade`, `evidence`, `priorities` | Self-evaluation form |
| `ofsted_prep_checklist` | `id`, `item`, `status`, `evidence_location` | Ofsted preparation |
| `policies` | `id`, `title`, `category`, `version`, `review_date`, `status` | Policy management |
| `equality_impact_assessments` | `id`, `title`, `policy_area`, `outcome`, `assessor` | EIA records |

Additional domains include: enrichment activities, peer mentoring, surveys, skills passports, student portfolios, study planning, forums, internal verification, T-Level placements, apprenticeship tracking, value-added analysis, governance/board management, health and safety, lettings, disciplinary cases, and data export.


### Foreign Key Handling

Foreign key enforcement is enabled on every connection via `PRAGMA foreign_keys = ON`. This means:

- INSERT or UPDATE operations that reference a non-existent parent row will fail with a constraint error.
- DELETE operations on parent rows will fail if child rows exist (default `RESTRICT` behaviour), unless the schema specifies `ON DELETE CASCADE`.
- All foreign key relationships use `FOREIGN KEY (column) REFERENCES parent_table(id)` syntax.

Common foreign key chains:

```
users.id  <--  students.user_id
users.id  <--  sessions.user_id
students.id  <--  enrollments.student_id  -->  courses.id
students.id  <--  grades.student_id  -->  courses.id
students.id  <--  attendance_records.student_id  -->  attendance_sessions.id  -->  courses.id
roles.id  <--  permissions.role_id
```


---

## Migrations

The migration framework lives in `migrations.py` and provides a lightweight versioned migration system.

### How It Works

1. A `schema_migrations` table tracks which migrations have been applied:
   ```sql
   CREATE TABLE IF NOT EXISTS schema_migrations (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       version TEXT UNIQUE NOT NULL,
       description TEXT,
       applied_at TEXT NOT NULL DEFAULT (datetime('now'))
   );
   ```

2. Each migration is a tuple of `(version, description, sql_statements)` registered in the `MIGRATIONS` list.

3. `run_all_migrations()` iterates over the list and applies any migration whose version is not yet recorded.

4. Each migration runs its SQL statements in sequence, then records the version. The entire migration is committed atomically.

### Adding a New Migration

Append a new entry to the `MIGRATIONS` list in `migrations.py`:

```python
MIGRATIONS = [
    ("001", "Add phone_verified column to users", [
        "ALTER TABLE users ADD COLUMN phone_verified INTEGER DEFAULT 0",
    ]),
]
```

Run `run_all_migrations()` at application startup or via a management command.

### Inline Migrations

For simple column additions, `init_db()` in `schema.py` also contains inline migration logic (e.g., adding `timetable_slot_id` to `attendance_sessions` if missing). This approach uses `PRAGMA table_info()` to check for column existence before issuing `ALTER TABLE`.


---

## Backup and Restore

SQLite databases can be backed up by copying the database file while respecting WAL mode:

```bash
# Safe copy using sqlite3 .backup command
sqlite3 college_system/data/db_files/sixthform.db ".backup '/path/to/backup.db'"
```

With WAL mode enabled, there may be `-wal` and `-shm` files alongside the main database. For a complete backup, either:

- Use the `.backup` command (recommended), which produces a self-contained copy.
- Copy all three files (`sixthform.db`, `sixthform.db-wal`, `sixthform.db-shm`) together.

To restore, replace the database file (and remove any stale `-wal`/`-shm` files), then restart the application.


---

## Best Practices

### Parameterized Queries

Always use parameterized queries with `?` placeholders. Never interpolate user input into SQL strings.

```python
# Correct
conn.execute("SELECT * FROM students WHERE student_id = ?", (sid,))

# WRONG -- SQL injection risk
conn.execute(f"SELECT * FROM students WHERE student_id = '{sid}'")
```

### Transaction Usage

Wrap related writes in a transaction to maintain consistency:

```python
with transaction() as conn:
    conn.execute("INSERT INTO enrollments (...) VALUES (...)", ...)
    conn.execute("UPDATE courses SET ... WHERE ...", ...)
```

### Connection Lifecycle

Service layer code follows the pattern:

```python
def some_operation(self):
    conn = self._conn()
    try:
        # ... database operations ...
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

Always close connections in a `finally` block to prevent resource leaks. When using `ConnectionPool` or `DatabaseManager`, prefer the context manager forms which handle cleanup automatically.

### Row Factory

All connections use `sqlite3.Row` as the row factory. Access columns by name rather than index:

```python
row = conn.execute("SELECT first_name, last_name FROM students WHERE id = ?", (1,)).fetchone()
name = f"{row['first_name']} {row['last_name']}"
```

### Constants

Use the constants defined in `constants.py` for grade scales, qualification types, year groups, terms, and attendance statuses rather than hardcoding values:

```python
from education_system.college_system.infrastructure.database.constants import (
    GRADE_SCALE, BTEC_GRADE_SCALE, QUALIFICATION_TYPES, YEAR_GROUPS, TERMS, ATTENDANCE_STATUSES
)
```
