# Primary School Database Guide

> Last Updated: October 2026

## Overview

The Primary School Management System uses SQLite as its database engine, storing all domain data in a single file at:

```
var/data/primary/primary.db
```

Authentication data is stored separately in the shared auth database:

```
var/data/platform/db_files/auth.db
```

This separation ensures that authentication concerns are decoupled from domain data and shared consistently across all seven Education System systems.

---

## Table Listing by Domain Area

Each domain module creates its own tables, so the authoritative definition of a table is the `_SCHEMA` string in its module under `src/education_system/systems/primary/domain/`. Tables are listed under the area that defines them.

| Area | Tables |
|---|---|
| Academics | `academic_breaks`, `academic_terms`, `academic_years`, `attendance_records`, `calendar_events`, `classes`, `club_memberships`, `clubs`, `homework_assignments`, `homework_submissions`, `lesson_plans`, `library_books`, `library_loans`, `subjects`, `timetable_slots`, `year_groups` |
| Admissions | `admissions` |
| Assessment | `assessment_records`, `early_warning_alerts`, `eyfs_profile_results`, `intervention_reviews`, `interventions`, `ks1_sats_results`, `ks2_sats_results`, `mtc_results`, `observations`, `phonics_assessments`, `phonics_screening_results`, `progress_reviews`, `progress_targets`, `pupil_phonics`, `pupil_reading_levels`, `pupil_targets`, `reading_level_assessments` |
| Finance | `dinner_money_ledger`, `expense_claim_lines`, `expense_claims`, `funding_allocations`, `funding_streams`, `pp_interventions`, `pupil_premium_records`, `receipt_lines`, `receipts`, `trip_bookings`, `trip_payments`, `trips` |
| Governance | `audit_report_defs`, `audit_report_runs`, `census_returns`, `compliance_items`, `gdpr_breaches`, `gdpr_consents`, `gdpr_processing`, `gdpr_requests`, `governance_meetings`, `governors`, `hs_actions`, `hs_incidents`, `learner_aims` (unused since 2026-11-05: ILR aims removed) (unused since 2026-11-05 — ILR aims removed), `policies`, `policy_revisions`, `risk_actions`, `risk_reviews`, `risks` |
| Learners | `leavers`, `pupil_onboarding`, `pupils` |
| Operations | `activity_events`, `announcements`, `asset_maintenance`, `assets`, `attachments`, `data_export_jobs`, `data_export_presets`, `documents`, `letter_templates`, `messages`, `newsletters`, `notifications`, `parent_contacts`, `parents_evening_bookings`, `parents_evenings`, `pupil_reports`, `todos`, `visitors`, `wraparound_attendance`, `wraparound_sessions` |
| Pastoral | `absence_requests`, `accessibility_arrangements`, `attendance_concerns`, `behaviour_incidents`, `complaints`, `ed_incidents`, `emergency_events`, `feedback`, `first_aid_incidents`, `house_point_awards`, `houses`, `medical_records`, `school_council_meetings`, `school_council_members`, `school_council_motions`, `send_records`, `send_reviews`, `support_plan_reviews`, `support_plans`, `survey_responses`, `surveys`, `transport_arrangements`, `transport_routes`, `wellbeing_checkins` |
| Safeguarding | `prevent_referrals`, `safeguarding_actions`, `safeguarding_concerns` |
| Staff | `appraisal_objectives`, `appraisals`, `class_teacher_assignments`, `cover_arrangements`, `cpd_activities`, `cpd_records`, `dbs_checks`, `department_members`, `departments`, `recruitment_applicants`, `staff`, `staff_absences`, `staff_hr_events`, `staff_hr_records`, `staff_wellbeing_entries`, `teaching_assistants`, `vacancies` |
| System settings | `settings_kv` |

---

## Connection Patterns

All database access goes through the domain modules; there is no central connection factory.

### Standard Connection Pattern

`domain/learners/pupils/pupils.py` owns the connection that most other modules borrow. It reads its location from `education_system.paths`:

```python
import os
import sqlite3

from education_system import paths

DB_PATH = paths.PRIMARY_PUPILS_DB
_DATA_DIR = DB_PATH.parent


def _connect() -> sqlite3.Connection:
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_pupil(pupil_id: str):
    init_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM pupils WHERE pupil_id = ?",
            (pupil_id,),
        ).fetchone()
```

### Key Rules

1. **Always use `_connect()`** to obtain connections -- never construct them directly in business logic.
2. **Always call `init_db()` first** so the module's tables exist.
3. **Always use parameterized queries** (`?` placeholders) -- never interpolate user input into SQL strings.
4. **Use a `with` block** so the transaction is committed or rolled back on error. It does not close the connection.

### Write Operations

```python
def add_note(pupil_id: str, note: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO pupil_notes (pupil_id, note) VALUES (?, ?)",
            (pupil_id, note),
        )
        conn.commit()
```

---

## Schema Initialization

The database schema is **created as modules are used**. Each module has an `init_db()` that runs its `_SCHEMA` with `CREATE TABLE IF NOT EXISTS`, guarded by a `_DB_READY` flag so it does its work once per process. These tables are not managed by Alembic. A module adds columns to an existing table in its own step, as `_migrate()` in `domain/learners/pupils/pupils.py` does.

### Manual Re-initialization

To reset the database (destroys all data):

```bash
rm var/data/primary/primary.db
python -m education_system --primary --gui
```

The tables will be recreated as each module is next used.

---

## Backup and Restore

### Creating a Backup

SQLite databases can be backed up by copying the file while no writes are in progress:

```bash
# Stop the application first, or use SQLite's backup API
mkdir -p var/backups/primary
cp var/data/primary/primary.db var/backups/primary/primary_backup_$(date +%Y%m%d_%H%M%S).db
```

For a live backup without stopping the application (using SQLite's `.backup` command):

```bash
sqlite3 var/data/primary/primary.db \
  ".backup 'var/backups/primary/primary_backup.db'"
```

### Restoring from Backup

```bash
# Stop the application
cp var/backups/primary/primary_backup.db var/data/primary/primary.db
```

### Backup Recommendations

- Schedule daily automated backups of both `primary.db` and `auth.db`.
- Retain at least 30 days of rolling backups.
- Store backups in a separate location from the application server.
- Test restore procedures termly.
- Encrypt backups at rest (the database contains data about minors).

---

## Journal Mode and Concurrency

The Primary School's connections do not switch on Write-Ahead Logging, so `primary.db` uses SQLite's default rollback journal.

### Concurrency Limitations

- SQLite allows only **one writer at a time**, and readers wait while a write commits. Python's `sqlite3` waits up to 5 seconds for a lock by default, then raises `database is locked`.
- For the Primary School system's expected load (single school, tens of concurrent users), SQLite provides adequate performance.
- If the application is deployed behind a multi-process web server, watch for `database is locked` errors.
