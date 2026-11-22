# Database Infrastructure

This document covers the SQLite database layer for the Sixth Form College Management System, including connection management, schema design, migrations, and best practices.

Source files:

- `src/education_system/paths.py` -- database location
- `src/education_system/systems/sixth_form/infrastructure/database.py` -- `sqlite3` names for the domain layer
- `src/education_system/systems/sixth_form/domain/**` and `domains/**` -- each module's own schema and connection helper
- `src/education_system/platform/identity/auth/schema.py` -- the central authentication database

---

## SQLite Setup

The system uses a single SQLite database file located at:

```
var/data/sixth_form/sixthform.db
```

Path resolution is handled by `src/education_system/paths.py` (`SIXTH_FORM_STUDENTS_DB`, with per-module aliases such as `SIXTH_FORM_ENRICHMENTS_DB`). The `ensure_sixth_form_directories()` function creates the required directories.

The data directory can be overridden with the `EDU_SIXTHFORM_DATA_DIR` environment variable. Tests redirect a module's `DB_PATH` attribute instead.

Users, sessions, MFA and roles are not stored here. They live in the central `var/data/platform/db_files/auth.db`, shared by all seven systems.


## Connection Management

### The `_connect()` Helper

There is no shared connection function. Each domain module has its own `_connect()`, and `infrastructure/database.py` re-exports the `sqlite3` names (`connect`, `Row`, `IntegrityError`, ...) for domain code, which may not import the driver itself. Each call:

1. Ensures the data directory exists.
2. Opens a new connection to the module's `DB_PATH`.
3. Sets `row_factory = sqlite3.Row` so query results are accessible by column name.
4. Turns on foreign keys.
5. Returns the connection.

```python
from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

### PRAGMAs

Connections apply the following SQLite PRAGMA. Individual modules may set others.

| PRAGMA | Value | Purpose |
|---|---|---|
| `foreign_keys` | `ON` | Enforce foreign key constraints |


### Transactions

Using a connection as a context manager provides automatic commit/rollback semantics:

```python
with _connect() as conn:
    conn.execute("INSERT INTO students (...) VALUES (...)", params)
    conn.execute("INSERT INTO enrolments (...) VALUES (...)", params)
# Commits automatically. Rolls back on any exception.
```

The context manager does not close the connection.


---

## Schema Overview

Each module defines its tables in a `_SCHEMA` string of `CREATE TABLE IF NOT EXISTS` statements, sometimes split into its own `schema.py`. Its `init_db()` runs the schema the first time the module is used, and first initialises any module whose tables it references. There is no central table list and no seeding of default accounts here.

The code defines about 630 tables, organized into the following areas. Paths are relative to `src/education_system/systems/sixth_form/`.

| Area | Tables | Examples |
|---|---|---|
| `domain/academics/` | 149 | `courses`, `subjects`, `class_groups`, `timetable_slots`, `attendance_records`, `coursework_assignments`, `library_loans`, `calendar_events`, `academic_years`, `enrichment_activities` |
| `domain/admissions/` | 63 | `admissions_applicants`, `admissions_programme_choices`, `enrolments`, `enrolment_ilr`, `onboarding_checklists` |
| `domain/assessment/` | 47 | `predicted_grades`, `targets`, `exam_entries`, `exam_results`, `exams_timetable`, `exams_access_evidence`, `report_cards`, `value_added_records`, `sef_sections` |
| `domain/governance/` | 46 | `policies`, `risks`, `gdpr_requests`, `compliance_items`, `governors`, `role_permissions`, `user_audit_log` |
| `domain/learners/` | 95 | `students`, `student_record_history`, `alumni`, `bulk_jobs`, `saved_searches`, `exit_interviews` |
| `domain/operations/` | 7 | `parent_accounts`, `parent_student_links`, `data_export_jobs`, `progress_reviews` |
| `domain/pastoral/` | 61 | `behaviour_entries`, `send_register`, `first_aid_incidents`, `med_profiles`, `complaints`, `surveys`, `tutor_groups`, `wellbeing_checkins` |
| `domain/progression/` | 34 | `ucas_applications`, `ucas_choices`, `dest_records`, `academic_references`, `we_placements` |
| `domain/safeguarding/` | 7 | `safeguarding_plans`, `safeguarding_referrals`, `lado_allegations` |
| `domain/staff/` | 22 | `staff`, `appraisals`, `cpd_records`, `departments`, `scr_checks`, `vacancies` |
| `domains/communications/` | 16 | `messages`, `notifications`, `announcements`, `letter_templates`, `parents_evenings` |
| `domains/finance/` | 31 | `fee_items`, `fee_invoices`, `fee_payments`, `bursary_applications`, `funding_allocations`, `expense_claims`, `trips` |
| `domains/operations/` | 35 | `assets`, `visitors`, `helpdesk_tickets`, `transport_routes`, `hs_incidents`, `catering_menus`, `lockers` |
| `infrastructure/` | 15 | `system_logs`, `sf_scheduler_jobs`, `ctf_imports`, `integration_settings` |

To find a table's owner, search for its name:

```bash
grep -rl "CREATE TABLE IF NOT EXISTS students\b" src/education_system/systems/sixth_form/
```


### Foreign Key Handling

Foreign key enforcement is enabled by each connection via `PRAGMA foreign_keys=ON`. This means:

- INSERT or UPDATE operations that reference a non-existent parent row will fail with a constraint error.
- DELETE operations on parent rows will fail if child rows exist (default `RESTRICT` behaviour), unless the schema specifies `ON DELETE CASCADE`.
- A foreign key to a table that does not exist yet also fails, which is why `init_db()` initialises its dependencies first.

`students` is keyed on the text `student_id`, in the form `C1470977`. A typical reference is:

```sql
FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
```


---

## Migrations

Alembic does not manage this database: its chain in `src/education_system/migrations/` covers the University's `student_records.db`. Sixth form schema changes are made in the module's own code.

### Adding a Table

Add a `CREATE TABLE IF NOT EXISTS` statement to the module's `_SCHEMA`. It is created the next time `init_db()` runs.

### Adding a Column

`CREATE TABLE IF NOT EXISTS` does nothing to an existing table, so a module's `init_db()` adds new columns itself. It uses `PRAGMA table_info()` to check for the column before issuing `ALTER TABLE`:

```python
existing = {r["name"] for r in conn.execute("PRAGMA table_info(awards)")}
if "phone_verified" not in existing:
    conn.execute("ALTER TABLE awards ADD COLUMN phone_verified INTEGER DEFAULT 0")
```


---

## Backup and Restore

SQLite databases can be backed up by copying the database file while respecting WAL mode:

```bash
# Safe copy using sqlite3 .backup command
sqlite3 var/data/sixth_form/sixthform.db ".backup 'var/backups/sixth_form/sixthform.db'"
```

All backups belong under `var/backups/sixth_form/` (`SIXTH_FORM_BACKUP_DIR`). `infrastructure/integrations/db_backup.py` writes its own there, using `paths.system_backup_dir("sixth_form", "database")`.

If the database is in WAL mode, there may be `-wal` and `-shm` files alongside the main database. For a complete backup, either:

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
with _connect() as conn:
    conn.execute("INSERT INTO enrolments (...) VALUES (...)", ...)
    conn.execute("UPDATE courses SET ... WHERE ...", ...)
```

### Row Factory

Connections use `sqlite3.Row` as the row factory. Access columns by name rather than index:

```python
row = conn.execute(
    "SELECT first_name, last_name FROM students WHERE student_id = ?", (sid,)
).fetchone()
name = f"{row['first_name']} {row['last_name']}"
```

### Constants

Use the constants a module already declares for statuses, year groups and terms rather than hardcoding values. For grades, use the scales in `domain/academics/qualifications/grade_scales.py`:

```python
from education_system.systems.sixth_form.domain.academics.qualifications.grade_scales import (
    QUALIFICATION_TYPES, SCALES, validate_grade,
)
```
