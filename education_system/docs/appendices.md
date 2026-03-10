# Appendices

Appendix sections extracted from CHANGELOG.md.

---

## APPENDIX A — DETAILED BUG REPORT

The following is a comprehensive log of all bugs reported and resolved, formatted
for cross-reference with git commit messages and issue tracker IDs where applicable.

---

### BUG-001 — ParkingManager.self.self.conn (v0.0.9)
**Severity:** Critical  
**Module:** parking_management.py  
**Symptom:** `AttributeError: 'ParkingManager' object has no attribute 'self'` on
any call to any `ParkingManager` method.  
**Root cause:** All 32 database cursor operations used `self.self.conn` instead of
`self.conn`. The double `self.` meant Python tried to look up `self` as an attribute
of the `ParkingManager` instance.  
**Fix:** Global search-and-replace `self.self.conn` → `self.conn` across the entire file.  
**Affected methods:** All 32 methods in the class.  
**Regression risk:** None — purely additive fix.

---

### BUG-002 — Database nested path (v0.0.8)
**Severity:** Critical  
**Module:** refactored/database/db.py  
**Symptom:** `sqlite3.OperationalError: unable to open database file` on startup.
The error path shown was `refactored/database/refactored/db_files/student_records.db`.  
**Root cause:** `DB_PATH = os.path.join(BASE_DIR, 'refactored', 'db_files', 'student_records.db')`
where `BASE_DIR = os.path.dirname(__file__)` was already `refactored/database/`. The
string `'refactored'` was prepended again.  
**Fix:** `PROJECT_ROOT` calculated as `os.path.dirname(os.path.dirname(os.path.dirname(
os.path.abspath(__file__))))` to correctly resolve to the project root.  
**Verification:** `os.path.exists(DB_PATH)` returns `True` after fix.

---

### BUG-003 — Chatbot load_config AttributeError (v0.4.0)
**Severity:** High  
**Module:** university_chatbot.py  
**Symptom:** `AttributeError: 'UniversityChatbot' object has no attribute 'load_config'`  
**Root cause:** `__init__` called `self.load_config()` but the method was never defined.
The configuration was intended to be loaded from `chatbot_config.json` but no loading
function was implemented.  
**Fix:** Added `load_config(self)` method that reads `chatbot_config.json` if it exists,
otherwise uses built-in defaults. Also added `save_config(self)` to persist changes.

---

### BUG-004 — Library auth.current_user dot notation (v0.0.5)
**Severity:** High  
**Module:** library.py  
**Symptom:** `AttributeError: 'dict' object has no attribute 'user_id'` when any
authenticated library function was called.  
**Root cause:** `auth.current_user` is a Python `dict`, not an object with attributes.
Code used `auth.current_user.user_id` (dot notation) instead of `auth.current_user['user_id']`
(dict access).  
**Fix:** All 47 occurrences of dot notation on `auth.current_user` converted to dict access.  
**Pattern:** `auth.current_user.X` → `auth.current_user['X']` for all attributes.

---

### BUG-005 — main.py syntax error (v0.0.7)
**Severity:** Critical  
**Module:** main.py  
**Symptom:** `SyntaxError: invalid syntax` at line 847, preventing the entire system
from starting.  
**Root cause:** An unclosed parenthesis in a multi-line function call:
```python
# Broken:
result = some_function(
    param1=value1,
    param2=value2
# Missing closing parenthesis
next_line_of_code = something()
```
**Fix:** Located and closed the unclosed parenthesis. Also fixed 3 other minor
syntax issues found in the same pass (a missing colon after `else`, a stray backtick,
and an indentation error in a try/except block).

---

### BUG-006 — Chatbot duplicate UniversityChatbot class (v0.5.0)
**Severity:** High  
**Module:** university_chatbot.py  
**Symptom:** The second definition of `UniversityChatbot` silently overrode the first,
causing the complete, correct implementation to be replaced by the stub version.  
**Root cause:** The file contained two class definitions:
- Lines 1–450: Complete `UniversityChatbot` with all methods.
- Lines 1200–1350: Incomplete `UniversityChatbot` with only `__init__` and stubs.
Python executed both, with the second replacing the first in the module namespace.  
**Fix:** The second (incomplete) definition was removed entirely.

---

### BUG-007 — Student support undefined functions (v0.5.0)
**Severity:** Medium  
**Module:** student_support.py  
**Symptom:** `AttributeError: 'StudentSupport' object has no attribute 'X'` for
several menu options.  
**Root cause:** The main menu called 5 methods that existed in the menu routing code
but were never implemented:
- `provide_peer_support_resources()`
- `create_support_group()`
- `track_intervention()`
- `generate_support_report()`
- `manage_resource_library()`  
**Fix:** All 5 methods implemented with full database operations.

---

### BUG-008 — Finance GUI startup errors (v1.3.0)
**Severity:** High  
**Module:** finance.py  
**Symptom:** Finance GUI crashed on startup with `KeyError: 'status'` or
`OperationalError: no such column: phone_number`.  
**Root cause:** Finance queries were referencing columns that had been removed or
renamed in the `students` table: `phone_number` (removed), `status` (removed),
`enrollment_date` (renamed to `registration_datetime`).  
**Fix:** `fix_database_schema()` added. All finance queries updated to use current
column names. `search_students()` method updated with correct SELECT list.

---

### BUG-009 — GradeTrackingGUI edit_selected_grade returns None (v1.3.0)
**Severity:** Medium  
**Module:** grade_tracking_gui.py  
**Symptom:** Clicking "Edit Grade" did nothing — no dialog appeared.  
**Root cause:** `edit_selected_grade()` was implemented as a stub:
```python
def edit_selected_grade(self):
    """Edit the selected grade"""
    return None  # TODO: implement
```
**Fix:** Full implementation that:
1. Gets selected item from TreeView.
2. Queries full grade record from database.
3. Opens `GradeDialog` pre-populated with current values.
4. Saves updated values if dialog is confirmed.
5. Recalculates GPA for the student.
6. Refreshes the TreeView.

---

### BUG-010 — Chatbot font TypeError (v1.2.0)
**Severity:** Low  
**Module:** university_chatbot.py (GUI component)  
**Symptom:** `TypeError: font argument is not a font` when the chatbot GUI window
was opened.  
**Root cause:** Font specification used a tuple format not supported by the target
platform:
```python
# Broken:
label = tk.Label(frame, font=('Arial', 12, 'bold', 'italic'))
# The fourth element is not valid in tkinter font tuples
```
**Fix:** Changed to use `tkFont.Font` object:
```python
import tkinter.font as tkFont
bold_italic = tkFont.Font(family='Arial', size=12, weight='bold', slant='italic')
label = tk.Label(frame, font=bold_italic)
```

---

### BUG-011 — library_gui incomplete methods (v1.2.0)
**Severity:** Medium  
**Module:** library_gui.py  
**Symptom:** Several library GUI buttons were non-functional, showing "Not implemented"
dialogs.  
**Root cause:** 8 methods had placeholder bodies:
- `manage_fine_payments()` — showed messagebox only
- `create_reading_list()` — showed messagebox only
- `manage_reservations()` — showed messagebox only
- `generate_overdue_report()` — returned without generating
- `export_library_data()` — raised NotImplementedError
- `import_books_from_file()` — empty body
- `manage_digital_resources()` — empty body
- `view_access_statistics()` — empty body  
**Fix:** All 8 methods fully implemented with appropriate dialogs and database operations.

---

### BUG-012 — housing_gui structural fixes (v1.2.0, v1.1.0)
**Severity:** Medium  
**Module:** housing_accommodation_gui.py  
**Symptom:** Multiple `NameError` and `AttributeError` on housing GUI launch.  
**Root cause (v1.2.0):** The `HousingGUI.__init__` referenced an undefined `root`
variable — should have been `self.root = tk.Tk()` but was `self.root = root`.
**Root cause (v1.1.0):** 22 `orig_` import aliases were named incorrectly — missing
`create_` prefix for function names that started with `create_`.  
**Fix:** Both issues corrected in their respective versions as documented above.

---

### BUG-013 — activity_logger_gui DatabaseManagementDialog (v1.1.0)
**Severity:** Low  
**Module:** activity_logger_gui.py  
**Symptom:** Clicking "Database Management" in the activity logger GUI raised
`NameError: name 'DatabaseManagementDialog' is not defined`.  
**Root cause:** The `DatabaseManagementDialog` class was referenced but not defined.
The file contained a `# TODO: add DatabaseManagementDialog` comment.  
**Fix:** `DatabaseManagementDialog` class implemented with tabs for: vacuum, integrity
check, backup, export to CSV, and connection pool stats.

---

### BUG-014 — module_scheduling entry point (v0.0.2)
**Severity:** Critical  
**Module:** module_scheduling.py  
**Symptom:** Running `python module_scheduling.py` did nothing.  
**Root cause:** `if __name__ == '__main__': ...` block was indented inside the
`ModuleScheduler` class body, making it a class-level statement only evaluated when
the class was defined, not when the module was run as main.  
**Fix:** De-indented to module level.

---

### BUG-015 — modules.py import gap (v0.0.2)
**Severity:** High  
**Module:** module_scheduling.py  
**Symptom:** `ImportError: cannot import name 'get_all_modules' from 'modules'`  
**Root cause:** `modules.py` defined module objects as named instances, not via
utility functions. `module_scheduling.py` tried to import utility functions that
didn't exist.  
**Fix:** Modules imported directly as named instances; wrapper functions `get_all_modules()`
and `get_module_by_code()` added to `module_scheduling.py`.

---

### BUG-016 — library.py dict access fixes second pass (v0.0.6)
**Severity:** Medium  
**Module:** library.py  
**Symptom:** `KeyError: 'user_id'` when checking out a book using the staff interface.  
**Root cause:** After the first round of dot-notation fixes (v0.0.5), some functions
still used a mixture of dict access and attribute access inconsistently. In particular,
some functions used `user['user_id']` but others still used `user.user_id` where `user`
was a sqlite3.Row object (which does support attribute-style access with the right
row_factory).  
**Fix:** `conn.row_factory = sqlite3.Row` confirmed on all connections; all access
standardised to bracket notation for consistency.

---

### BUG-017 — set_auth alias conflict (v0.7.0)
**Severity:** High  
**Module:** main.py  
**Symptom:** `ImportError: cannot import name 'set_auth' from 'module_x'` for
various modules, or more subtly, the wrong module's `set_auth` being called.  
**Root cause:** `main.py` imported `set_auth` from multiple modules without aliasing.
Each import overwrote the previous one in the local namespace:
```python
from student_union import set_auth  # sets set_auth to student_union.set_auth
from internship_management import set_auth  # OVERWRITES to internship_management.set_auth
```
So `set_auth(auth)` only ever called the last-imported version.  
**Fix:** All `set_auth` imports aliased with module prefix:
```python
from student_union import set_auth as set_student_union_auth
from internship_management import set_auth as set_internship_auth
from shop_management import set_auth as set_shop_auth
# etc.
```
And `init_auth_for_modules()` updated to call each alias separately.

---

### BUG-018 — Email metrics missing functions (v0.0.1)
**Severity:** Medium  
**Module:** email_manager.py  
**Symptom:** `AttributeError: module 'email_manager' has no attribute 'get_metrics'`
and similar for `update_metrics`, `record_sent_email`.  
**Root cause:** The `email_metrics` table was created in `_init_communication_tables()`
but no functions existed to interact with it.  
**Fix:** Added `get_email_metrics(period='all')`, `record_sent_email(recipient, subject,
template_name='')`, `update_email_metrics(template_name, delivered=True)`, and
`get_email_dashboard()` dashboard summary function. Also added `email_dashboard()` as
a menu entry.

---

### BUG-019 — Chatbot permissions schema (v0.5.0)
**Severity:** Medium  
**Module:** university_chatbot.py  
**Symptom:** Chatbot permission checks failing with `KeyError` or `OperationalError:
no such column`.  
**Root cause:** The chatbot was creating its own `permissions` table in a separate
SQLite file, separate from the main `student_records.db`. When it tried to check
permissions by joining with `users`, the tables were in different databases.  
**Fix:** Chatbot redirected to use the main `student_records.db` for all permission
lookups. The chatbot-specific `permissions` table creation removed.

---

### BUG-020 — Accommodation set_auth dual reference (v0.4.0)
**Severity:** Low  
**Module:** main.py  
**Symptom:** Housing accommodation module not reflecting authentication state when
the main auth object was updated.  
**Root cause:** The accommodation module had two separate auth variables:
`accommodation.py` had `_medical_accommodation_auth` and `housing_accommodation.py`
had `_accommodation_auth`. Both needed to be set, but only one `set_auth` was being
called.  
**Fix:** `init_auth_for_modules()` updated to call both:
```python
set_accommodation_auth(auth)         # housing_accommodation.py
set_medical_accommodation_auth(auth) # accommodation.py
```
The import aliases in `main.py` updated accordingly.

---

### BUG-021 — Alumni events registration foreign key (v0.0.1)
**Severity:** High  
**Module:** alumni_management.py  
**Symptom:** `sqlite3.IntegrityError: FOREIGN KEY constraint failed` when registering
an existing alumnus for a newly created event.  
**Root cause:** `alumni_events` table was created with `FOREIGN KEY (alumni_id)
REFERENCES alumni(id)` but the `alumni` table was created with `alumni_id TEXT PRIMARY
KEY` (not `id`). The FK referenced `id` which didn't exist.  
**Fix:** FK corrected to `REFERENCES alumni(alumni_id)`.

---

### BUG-022 — Trip management auth null check (v0.0.9)
**Severity:** Medium  
**Module:** trip_management.py  
**Symptom:** "You must be logged in to access trip management" even when the user
was authenticated.  
**Root cause (secondary):** Even after fixing the auth-not-passed issue (BUG described
in main Trip Management section), there was a secondary bug: `_trip_auth_instance` was
initialised as `None` at module load time, but `set_trip_auth()` wasn't defined until
line 800+. If any trip function was called before that line was parsed, the variable
didn't exist. Python parses the entire module before executing, so this was not the
actual issue — the real secondary cause was that `display_trip_management_menu()` had
a guard check:
```python
if not _trip_auth_instance or not _trip_auth_instance.current_user:
    print("You must be logged in to access trip management.")
    return
```
And `_trip_auth_instance` was a different variable than `auth` used elsewhere in the
file.  
**Fix:** Standardised to use a single `_auth` variable, and ensured `set_trip_auth`
set the same variable that `display_trip_management_menu` checked.

---

### BUG-023 — Finance reporting GUI attribute (v1.9.0)
**Severity:** Medium  
**Module:** finance_reporting.py, main.py  
**Symptom:** `AttributeError: 'StudentManagementGUI' object has no attribute 'reporting_integration'`  
**Root cause:** `integrate_reporting_with_main_gui()` was defined inside the
`StudentManagementGUI` class at the wrong indentation level. When `main.py` imported it:
```python
from enhanced_reporting import integrate_reporting_with_main_gui
```
Python raised `ImportError` because there was no module-level function by that name.
(There was a class method, but that's not accessible via `from module import name`.)  
**Fix:** Extracted to module level as documented in the finance_reporting section.

---

### BUG-024 — Parent portal email regex (2025-09-02)
**Severity:** Low  
**Module:** parent_portal_gui.py  
**Symptom:** `SyntaxError: EOL while scanning string literal` on import.  
**Root cause:** Email validation regex was missing the closing quote:
```python
pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
```
The string literal was never closed, so Python's lexer consumed code on subsequent
lines as part of the string.  
**Fix:** Added closing quote and end anchor:
```python
pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
```

---

### BUG-025 — Plagiarism empty try block (2025-08-21)
**Severity:** Low  
**Module:** main.py (integrate_ai_detector_with_main function)  
**Symptom:** `SyntaxError: expected an indented block` on Python < 3.12, or silent
failure on Python >= 3.12 when the fallback AI detector was needed.  
**Root cause:** An automated code formatter had inserted `pass  # auto-inserted` after
an empty `try:` block. The structure was:
```python
try:
    pass  # auto-inserted
    ai_detector = create_minimal_ai_detector()
```
The `pass` before `ai_detector = ...` was harmless for the try block, but a `return True`
statement that should have been inside the try was placed after the except, making the
function always return `None`.  
**Fix:** Removed the erroneous `pass`, restructured the try/except as documented.

---

### BUG-026 — AcademicAffairs missing import (v2.5.0)
**Severity:** Critical  
**Module:** AcademicAffairs.py  
**Symptom:** `ImportError: cannot import name 'AcademicAffairsManager' from 'AcademicAffairs'`  
**Root cause:** The file started with:
```python
from dataclasses import dataclass
from datetime import datetime
import uuid
```
But was missing `import sqlite3`. When `_create_tables()` was called, `sqlite3.connect()`
raised `NameError: name 'sqlite3' is not defined`.  
**Fix:** Added `import sqlite3` and `import logging` to imports. Also added `from typing
import List, Optional, Dict, Any`.

---

### BUG-027 — Email manager database path computation (v2.2.0)
**Severity:** High  
**Module:** email_manager.py  
**Symptom:** Email sends logged to a different database than the one the rest of the
system used, causing sent messages to not appear in the communication dashboard.  
**Root cause:** `email_manager.py` computed `DB_PATH` using `os.getcwd()` (current
working directory) rather than the project root:
```python
DB_PATH = os.path.join(os.getcwd(), 'student_records.db')
```
If the process was started from a different directory, this pointed to a different file
or created a new empty database.  
**Fix:** Changed to use the same `PROJECT_ROOT`-relative calculation as all other modules.

---

*End of Bug Report Appendix*



---

## APPENDIX B — FULL DATABASE MIGRATION HISTORY

The following documents every schema change applied to `student_records.db` across the
development period, in chronological order.

### 2025-06-09 (v0.0.8)
- Fixed: `db.py` `DB_PATH` now correctly points to project root relative path.
- No schema changes — existing schema preserved.

### 2025-06-09 (v0.0.9)
- Added `DatabaseManager` class for thread-safe connections.
- Applied `PRAGMA journal_mode=WAL` to all new connections.
- Applied `PRAGMA foreign_keys=ON` to all new connections.

### 2025-06-09 (v0.0.9 — parking)
- `parking_permits` table: Added `student_id TEXT REFERENCES students(student_id)`.
- `vehicles` table: Added `student_id TEXT REFERENCES students(student_id)`.
- `parking_violations` table: Added `status TEXT DEFAULT 'unpaid'` if missing.
- `violation_appeals` table: Created new.

### 2025-06-09 (v0.0.9 — users)
- `users` table: Added `first_name TEXT`, `last_name TEXT`, `student_id TEXT`,
  `is_locked INTEGER DEFAULT 0`, `failed_login_count INTEGER DEFAULT 0`,
  `mfa_secret TEXT`, `mfa_enabled INTEGER DEFAULT 0`.

### 2025-06-09 (v0.0.9 — library)
- `books` table: Added `subject TEXT`, `location TEXT`, `description TEXT`,
  `added_date TEXT`, `updated_date TEXT`.
- All 15 new library tables created (see Appendix B).

### 2025-06-09 (v0.0.1 — alumni)
- All 23 alumni tables created (see Appendix B).

### 2025-06-10 (v0.0.2 — module_scheduling)
- `module_schedules` table: Created with columns: `schedule_id TEXT PRIMARY KEY`,
  `module_code TEXT`, `room TEXT`, `day_of_week TEXT`, `start_time TEXT`,
  `end_time TEXT`, `academic_year TEXT`, `term TEXT`, `instructor_id INTEGER`.

### 2025-06-12 (v0.4.0 — chatbot)
- `chatbot_conversations` table: Created.
- `chatbot_sessions` table: Created.
- Chatbot permissions added to `permissions` and `role_permissions` tables.

### 2025-06-15 (v0.5.0 — student_support)
- `support_tickets` table: Added `priority TEXT DEFAULT 'medium'`,
  `sla_due_date TEXT`, `resolved_at TEXT`.
- `ticket_activity_log` table: Created.
- `kb_categories` table: Created.
- `kb_articles` table: Created.

### 2025-06-16 (v0.5.0 — email_manager)
- `messages` table: Added `sent_at TEXT`, `is_read INTEGER DEFAULT 0`,
  `read_at TEXT`, `folder TEXT DEFAULT 'inbox'`,
  `is_deleted_by_sender INTEGER DEFAULT 0`,
  `is_deleted_by_recipient INTEGER DEFAULT 0`,
  `attachment_path TEXT`, `parent_message_id INTEGER`.
- `email_metrics` table: Created.
- `email_queue` table: Created.
- `email_logs` table: Created.

### 2025-06-18 (v0.6.0 — accommodation)
- `audit_log` table: Added `accommodation_id INTEGER`, `details TEXT`,
  `ip_address TEXT`.
- `accommodations` table: Added `notes TEXT`, `template_applied TEXT`,
  `document_path TEXT`, `last_reviewed TEXT`, `review_notes TEXT`,
  `created_at TEXT`, `updated_at TEXT`.

### 2025-06-20 (v0.7.0 — chatbot auth)
- `sessions` table: Created (for main authentication, not chatbot-specific).
  Columns: `session_id TEXT PRIMARY KEY`, `user_id INTEGER`, `created_at TEXT`,
  `last_activity TEXT`, `ip_address TEXT`.

### 2025-06-26 (v0.8.0 — students table)
- `students` table: Removed `phone_number` (renamed to `emergency_phone`).
  Actually: added `emergency_phone TEXT` as new column; `phone_number` deprecated
  (kept for backwards compatibility but not used in queries).
- `students` table: Added `title TEXT DEFAULT ''`, `gender TEXT`, `dob TEXT`,
  `age INTEGER`.
- `students` table: `enrollment_date` column kept but `registration_datetime` added
  as the preferred column (both populated going forward).

### 2025-07-01 (v0.9.0 — grade_tracking)
- `grades` table: Added `late_penalty REAL DEFAULT 0.0`, `feedback TEXT`,
  `is_final INTEGER DEFAULT 0`.
- `intervention_records` table: Created.
- `grade_predictions` table: Created.

### 2025-07-06 (v1.0.0 — grade_tracking_gui)
- `grade_tracking_gui` reads from existing tables — no schema changes.

### 2025-07-27 (v1.8.0 — grade_tracking analytics)
- `grade_predictions` table (extended): Added `predicted_gpa REAL`,
  `success_probability REAL`, `dropout_risk REAL`, `prediction_date TEXT`.

### 2025-08-03 (document_manager)
- `documents` table: Added `original_filename TEXT`, `file_size_bytes INTEGER`,
  `mime_type TEXT`, `access_count INTEGER DEFAULT 0`, `tags TEXT`,
  `is_archived INTEGER DEFAULT 0`, `archived_reason TEXT`.
- `document_versions_archive` table: Created.
- `notification_templates` table: Created.
- `api_keys` table: Created.
- `document_text_content` table: Created (for OCR output).
- Added indexes: `idx_documents_student_id`, `idx_documents_doc_type`,
  `idx_documents_status`, `idx_documents_expiry`.

### 2025-08-20 (attendance_gui)
- `attendance_achievements` table: Created.
- `attendance_points` table: Created.
- `qr_session_tokens` table: Created.

### 2025-08-25 (health_portal_gui)
- `health_audit_log` table: Created.
- `health_data_retention_settings` table: Created.
- `health_records_archive` table: Created (for retention policy archival).
- `disease_surveillance` table: Created.
- `public_health_alerts` table: Created.
- `vital_signs` table: Created.
- `care_plans` table: Created.
- `care_plan_goals` table: Created.
- `prescriptions` table: Created.
- `medication_adherence_log` table: Created.
- `drug_interactions` table: Created (pre-populated with 50 known interactions).

### 2025-09-01 (parent_portal)
- `parent_accounts` table: Created.
- `parent_student_links` table: Created.
- `parent_notifications` table: Created.
- `parent_messages` table: Created.

### 2025-09-04 (data_backup)
- `backup_log` table: Created.
- `backup_settings` table: Created.

### 2025-09-17 (automated test runner)
- `import_history` table: Created.
- `batch_operation_log` table: Created.

### 2025-10-15 (AcademicAffairs)
- `transfer_credits` table: Created.
- `committees` table: Created.
- `committee_members` table: Created.
- `meetings` table: Created.
- `meeting_minutes` table: Created.
- `portfolios` table: Created.
- `portfolio_artifacts` table: Created.

### 2026-01-27 (v2.3.0 consolidation)
- No schema changes. Documentation consolidated.

### 2026-03-07 (v2.5.0)
- No schema changes beyond what was added in AcademicAffairs integration above.
- `report_templates` table verified to exist (created in v1.9.0 if missing).

---

*End of Database Migration History*


---


---

## APPENDIX C — CONFIGURATION REFERENCE

All configuration files used by the system, their locations, and default values.

---

### email_config.json
Location: `[project_root]/email_config.json`
```json
{
    "server": "smtp.gmail.com",
    "port": 587,
    "use_tls": true,
    "username": "",
    "password": "",
    "from_address": "noreply@university.ac.uk",
    "from_name": "University Student Management System",
    "max_bulk_batch_size": 50,
    "bulk_send_delay_seconds": 0.1,
    "default_signature": "\n\nBest regards,\nUniversity Administration",
    "reply_to": "admin@university.ac.uk"
}
```
If this file does not exist, all SMTP fields default to empty strings. Email sending
will fail gracefully with a log warning rather than crashing.

---

### chatbot_config.json
Location: `[project_root]/chatbot_config.json`
```json
{
    "model_name": "gpt-3.5-turbo",
    "max_tokens": 500,
    "temperature": 0.7,
    "system_prompt": "You are a helpful university assistant. Answer questions about student services, courses, and campus facilities.",
    "session_timeout_minutes": 30,
    "max_conversation_history": 10,
    "enable_authentication": true,
    "enable_flask_api": false,
    "flask_host": "0.0.0.0",
    "flask_port": 5000,
    "allowed_intents": [
        "student_info", "course_info", "library", "health", "finance",
        "housing", "alumni", "schedule", "general"
    ]
}
```

---

### backup_settings (stored in database)
Table: `backup_settings`
```
Key: backup_interval_hours  Default: 24
Key: backup_destination     Default: [project_root]/backups/
Key: max_backups_to_keep    Default: 10
Key: auto_backup_enabled    Default: 1
Key: differential_enabled   Default: 0
Key: email_on_failure       Default: 0
Key: email_on_success       Default: 0
Key: notification_email     Default: (empty)
```

---

### health_data_retention_settings (stored in database)
Table: `health_data_retention_settings`
```
data_type: health_records       retention_years: 7   auto_delete: 0  archive: 1
data_type: vaccinations         retention_years: 10  auto_delete: 0  archive: 1
data_type: appointments         retention_years: 5   auto_delete: 1  archive: 1
data_type: audit_logs           retention_years: 3   auto_delete: 1  archive: 0
data_type: prescriptions        retention_years: 7   auto_delete: 0  archive: 1
data_type: vital_signs          retention_years: 5   auto_delete: 1  archive: 1
data_type: disease_surveillance retention_years: 10  auto_delete: 0  archive: 1
```

---

### Attendance thresholds (stored in database)
Table: `attendance_settings`
```
Key: minimum_attendance_percentage   Default: 75
Key: late_threshold_minutes          Default: 10
Key: qr_validity_seconds             Default: 300
Key: email_alerts_enabled            Default: 1
Key: alert_threshold_percentage      Default: 70
Key: at_risk_threshold               Default: 75
Key: critical_threshold              Default: 50
```

---

### SLA configuration for helpdesk
SLA due dates calculated from ticket creation time based on priority:
```
Priority: critical  SLA hours: 4
Priority: high      SLA hours: 8
Priority: medium    SLA hours: 24
Priority: low       SLA hours: 72
```
SLA status labels:
```
OVERDUE:  sla_due_date < current_time AND status NOT IN ('resolved', 'closed')
AT RISK:  sla_due_date < current_time + 2 hours AND status NOT IN ('resolved', 'closed')
ON TRACK: all others
```

---

### Permission groups by feature area

The following groups represent the minimum permissions required for common operations.

**View own student record:**
`view_own_record`

**View any student record:**
`view_any_student`

**Full student management:**
`create_student`, `view_any_student`, `edit_any_student`, `delete_student`

**Grade recording:**
`manage_grades` OR (`view_assigned_modules` AND `record_grades`)

**Attendance:**
`take_attendance` (recording) OR `view_attendance` (read-only)

**Health portal — student:**
`view_own_health_record`, `view_own_appointments`, `view_own_vaccinations`,
`schedule_health_appointment`

**Health portal — health provider:**
`manage_health_records`, `manage_health_appointments`, `record_vaccination`,
`issue_health_advisories`, `view_any_health_record`

**Library — student:**
`view_books`, `checkout_books`, `view_reading_lists`

**Library — librarian:**
`manage_books`, `manage_loans`, `view_books`

**Finance — student:**
`view_own_finances`

**Finance — staff:**
`view_finance`, `process_payments`, `generate_financial_reports`

**Finance — admin:**
`manage_finance`, `manage_scholarships`, `generate_financial_reports`

**Parking — student:**
`view_own_permits`, `create_permit`, `pay_violations`

**Parking — admin:**
`manage_parking`, `manage_permits`, `manage_violations`

**Communication — all roles:**
`send_messages`, `view_messages`, `view_announcements`, `use_chat_rooms`

**Communication — admin/staff:**
`create_announcements`, `access_communication_dashboard`, `send_emails`

**System administration:**
`manage_users`, `system_config`, `backup_restore`, `view_logs`, `manage_logs`

---


---

## APPENDIX D — INSTALLER AND SETUP REFERENCE

### Requirements (requirements.txt — as of v2.5.0)

**Required (core):**
```
# No external packages required for basic CLI functionality
# Python stdlib only: sqlite3, tkinter, hashlib, datetime, os, sys, json, csv,
# threading, logging, io, re, shutil, glob, pathlib, uuid, secrets, argparse,
# contextlib, functools, typing, dataclasses, queue, time
```

**Required for full GUI:**
```
tkinter  # Usually bundled with Python — may need python3-tk on Linux
```

**Optional — enhanced features:**
```
pandas>=1.5.0          # Excel export, data analysis
openpyxl>=3.0.0        # Excel file reading/writing
matplotlib>=3.5.0      # Charts in GUI and reports
seaborn>=0.11.0        # Enhanced chart styling
reportlab>=3.6.0       # PDF report generation
cryptography>=3.4.0    # Health data field-level encryption
pyotp>=2.6.0           # Multi-factor authentication (TOTP)
qrcode>=7.3.0          # QR code generation for attendance check-in
Pillow>=9.0.0          # Image handling (QR display, GUI images)
pytesseract>=0.3.8     # OCR for document text extraction
flask>=2.0.0           # REST API for chatbot
requests>=2.27.0       # External API calls from ai_detector
```

### Installation steps
```bash
# 1. Clone the repository
git clone [repository_url]
cd university-management-system

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install pandas openpyxl matplotlib seaborn reportlab cryptography pyotp qrcode Pillow

# 4. Set environment variables (optional, for encryption)
export HEALTH_PORTAL_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 5. Run the system
python main.py
```

### First login credentials
```
Admin account:   username: admin,   password: admin123
Staff account:   username: staff,   password: staff123
Student account: username: student, password: student123
Parent account:  username: parent1, password: parent123
```
All passwords should be changed after first login. The admin account has full access
to all system features including user management, system configuration, and all data.

### Database location
```
Default: [project_root]/refactored/db_files/student_records.db
Backup:  [project_root]/refactored/db_files/auto_backups/
Logs:    [project_root]/logs/
```

---


---

## APPENDIX E — TESTING REFERENCE

### Manual test procedures

**Authentication test:**
1. Start system.
2. Log in as `admin` / `admin123`. Verify all navigation buttons are enabled.
3. Log out.
4. Log in as `student` / `student123`. Verify restricted buttons are disabled.
5. Attempt to access a restricted function directly. Verify access denied message.
6. Enter wrong password 5 times. Verify account lockout message.
7. Log in as admin, unlock the student account.

**Student CRUD test:**
1. Log in as admin.
2. Add a new student with all required fields.
3. Verify student appears in the student list.
4. Edit the student's course.
5. Verify change was saved.
6. Search for the student by name.
7. Delete the student.
8. Verify student no longer appears.

**Grade recording test:**
1. Log in as staff.
2. Navigate to Grade Tracking.
3. Add a grade for an enrolled student.
4. Verify GPA is recalculated.
5. Edit the grade.
6. Verify GPA updates again.
7. Export grades to CSV.
8. Verify CSV file contains correct data.

**Email test:**
1. Log in as admin.
2. Navigate to Communication.
3. Send a message to the student account.
4. Log out, log in as student.
5. Navigate to Communication inbox.
6. Verify message received.
7. Reply to the message.
8. Log out, log in as admin.
9. Verify reply received.

**Health portal test:**
1. Log in as staff.
2. Navigate to Health Portal.
3. Add a vaccination record for a student.
4. Schedule an appointment.
5. Confirm an appointment.
6. View the health dashboard.
7. Generate a vaccination coverage report.

**Backup test:**
1. Log in as admin.
2. Navigate to Data Backup.
3. Create a full backup.
4. Verify backup file created in backup directory.
5. Add a student record.
6. Restore from the backup.
7. Verify the newly added student is no longer in the system (restore succeeded).

---

### Automated test phases (run_tests.py)

Phase 1 — Authentication:
```
Login as admin → verify success
Login as student → verify success
Login as staff → verify success
Check permission (admin, manage_students) → expect True
Check permission (student, manage_students) → expect False
Wrong password → expect failure
```

Phase 2 — Student Records:
```
Add student (first_name='Test', last_name='User', course='CS') → expect success
Get student by ID → expect data returned
Update student email → expect success
Search student by name → expect result found
```

Phase 3 — Module Management:
```
Add module (code='TEST101', name='Test Module', credits=20) → expect success
Enroll student in module → expect success
View enrolled students → expect student in list
```

Phase 4 — Grade Tracking:
```
Add assessment for module → expect success
Record grade (student, assessment, score=75) → expect success
Get student grades → expect grade in list
Calculate GPA → expect valid float in range 0.0–4.0
Export grades to CSV → expect file created
```

Phase 5 — Batch Operations:
```
Generate student import template → expect CSV file created
Run data quality validation → expect no critical errors
Find duplicate students → expect empty result (clean test data)
Export all students → expect CSV file created
Create database backup → expect backup file created
```

Phase 6 — Document Management:
```
Store document for student → expect doc_id returned
View document details → expect correct data
Update document status to 'approved' → expect success
Export compliance report → expect file created
```

Phase 7 — Finance:
```
Assign tuition fee to student → expect success
Record payment → expect success
View financial statement → expect balance reduced
Generate invoice → expect PDF created
```

Phase 8 — Communication:
```
Send message student → admin → expect success
Get admin inbox → expect message present
Send announcement → all students → expect success
Get student announcements → expect announcement present
Create chat room → expect room_id returned
Send chat message → expect success
Get chat messages → expect message present
```

---

*End of Testing Reference*

---

*CHANGELOG.md — Final Version*
*University Student Management System*
*Compiled from full development history: June 2025 — March 2026*
*Total entries: 45+ versions, 85+ files, 180+ bugs, 95+ features*


---


---

## APPENDIX F — COMPLETE ROLE AND PERMISSIONS MATRIX

The following matrix shows which roles have which permissions by default. This was
established across multiple permission setup functions throughout the codebase.

Legend: ✓ = assigned by default | — = not assigned (can be granted manually)

### Core System Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_users | ✓ | — | — | — | — | — | — |
| view_any_student | ✓ | ✓ | ✓ | — | — | — | — |
| edit_any_student | ✓ | ✓ | — | — | — | — | — |
| delete_student | ✓ | — | — | — | — | — | — |
| view_own_record | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| edit_own_profile | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| system_config | ✓ | — | — | — | — | — | — |
| backup_restore | ✓ | — | — | — | — | — | — |
| view_logs | ✓ | ✓ | — | — | — | — | — |
| manage_logs | ✓ | — | — | — | — | — | — |
| export_data | ✓ | ✓ | — | — | — | — | — |
| view_analytics | ✓ | ✓ | ✓ | — | — | — | — |
| batch_operations | ✓ | ✓ | — | — | — | — | — |

### Academic Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_modules | ✓ | ✓ | — | — | — | — | — |
| view_modules | ✓ | ✓ | ✓ | ✓ | — | — | — |
| enrol_students | ✓ | ✓ | — | — | — | — | — |
| manage_grades | ✓ | ✓ | ✓ | — | — | — | — |
| view_any_grade | ✓ | ✓ | ✓ | — | — | — | — |
| view_own_grades | ✓ | ✓ | ✓ | ✓ | — | — | — |
| manage_assessments | ✓ | ✓ | ✓ | — | — | — | — |
| manage_calendar | ✓ | ✓ | ✓ | — | — | — | — |
| view_calendar | ✓ | ✓ | ✓ | ✓ | — | — | — |
| manage_attendance | ✓ | ✓ | — | — | — | — | — |
| take_attendance | ✓ | ✓ | ✓ | — | — | — | — |
| view_attendance | ✓ | ✓ | ✓ | ✓ | — | — | — |
| manage_assignments | ✓ | ✓ | ✓ | — | — | — | — |
| submit_assignments | ✓ | — | — | ✓ | — | — | — |
| grade_submissions | ✓ | ✓ | ✓ | — | — | — | — |
| check_plagiarism | ✓ | ✓ | ✓ | — | — | — | — |
| submit_plagiarism_check | ✓ | ✓ | ✓ | ✓ | — | — | — |
| view_plagiarism_reports | ✓ | ✓ | ✓ | — | — | — | — |

### Finance Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_finance | ✓ | — | — | — | — | — | — |
| view_finance | ✓ | ✓ | — | — | — | — | — |
| process_payments | ✓ | ✓ | — | — | — | — | — |
| manage_scholarships | ✓ | ✓ | — | — | — | — | — |
| view_financial_reports | ✓ | ✓ | — | — | — | — | — |
| generate_financial_reports | ✓ | ✓ | — | — | — | — | — |
| view_own_finances | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| view_child_fees | — | — | — | — | — | — | ✓ |

### Library Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_books | ✓ | — | — | — | ✓ | — | — |
| view_books | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| checkout_books | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| manage_loans | ✓ | — | — | — | ✓ | — | — |
| view_reading_lists | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| manage_reading_lists | ✓ | ✓ | ✓ | — | ✓ | — | — |

### Health Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_health_records | ✓ | — | — | — | — | ✓ | — |
| view_any_health_record | ✓ | — | — | — | — | ✓ | — |
| view_own_health_record | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| update_health_record | ✓ | — | — | — | — | ✓ | — |
| manage_health_appointments | ✓ | — | — | — | — | ✓ | — |
| schedule_health_appointment | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| view_own_appointments | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| manage_vaccinations | ✓ | — | — | — | — | ✓ | — |
| record_vaccination | ✓ | — | — | — | — | ✓ | — |
| issue_health_advisories | ✓ | — | — | — | — | ✓ | — |
| view_health_advisories | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| generate_health_reports | ✓ | ✓ | — | — | — | ✓ | — |
| view_sensitive_health_data | ✓ | — | — | — | — | ✓ | — |

### Campus Services Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_housing | ✓ | ✓ | — | — | — | — | — |
| apply_for_housing | ✓ | — | — | ✓ | — | — | — |
| manage_parking | ✓ | ✓ | — | — | — | — | — |
| create_permit | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| manage_violations | ✓ | ✓ | — | — | — | — | — |
| pay_violations | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| manage_trips | ✓ | ✓ | — | — | — | — | — |
| register_for_trips | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| view_trips | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| join_clubs | ✓ | — | — | ✓ | — | — | — |
| manage_clubs | ✓ | ✓ | — | — | — | — | — |
| book_facilities | ✓ | ✓ | ✓ | ✓ | — | — | — |
| view_internships | ✓ | ✓ | ✓ | ✓ | — | — | — |
| apply_for_internship | ✓ | — | — | ✓ | — | — | — |
| manage_internships | ✓ | ✓ | — | — | — | — | — |

### Communication Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| send_emails | ✓ | ✓ | — | — | — | — | — |
| view_messages | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| send_messages | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| view_announcements | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| create_announcements | ✓ | ✓ | ✓ | — | — | — | — |
| use_chat_rooms | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| message_teachers | — | — | — | — | — | — | ✓ |
| access_communication_dashboard | ✓ | ✓ | — | — | — | — | — |

### Parent Portal Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| access_parent_portal | ✓ | ✓ | — | — | — | — | ✓ |
| view_child_records | ✓ | ✓ | — | — | — | — | ✓ |
| view_child_grades | ✓ | ✓ | — | — | — | — | ✓ |
| view_child_attendance | ✓ | ✓ | — | — | — | — | ✓ |
| manage_parent_portal | ✓ | — | — | — | — | — | — |

### Helpdesk Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_tickets | ✓ | ✓ | — | — | — | — | — |
| view_all_tickets | ✓ | ✓ | — | — | — | — | — |
| create_tickets | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| respond_to_tickets | ✓ | ✓ | — | — | — | — | — |
| escalate_tickets | ✓ | ✓ | — | — | — | — | — |
| manage_kb | ✓ | ✓ | — | — | — | — | — |
| view_kb | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### Document Management Permissions

| Permission | admin | staff | instructor | student | librarian | health_provider | parent |
|---|---|---|---|---|---|---|---|
| manage_documents | ✓ | ✓ | — | — | — | — | — |
| view_any_document | ✓ | ✓ | — | — | — | — | — |
| view_own_documents | ✓ | ✓ | ✓ | ✓ | — | — | — |
| upload_documents | ✓ | ✓ | — | ✓ | — | — | — |
| verify_documents | ✓ | ✓ | — | — | — | — | — |

---


---

## APPENDIX G — VERSION CHANGELOG QUICK REFERENCE

A compact one-line summary of every version for quick scanning:

| Version | Date | Key Change |
|---|---|---|
| Pre-release | 2025-06-09 | Parking schema, GUI destruction, DB consolidation, email+AI fixes |
| v0.0.1 | 2025-06-09 | alumni_management.py: 20+ new tables |
| v0.0.2 | 2025-06-10 | module_scheduling entry point, modules.py integration |
| v0.0.3 | 2025-06-09 | library.py: 15+ new tables |
| v0.0.4 | 2025-06-09 | library.py first auth fix pass |
| v0.0.5 | 2025-06-09 | library.py auth.current_user dot notation: 47 fixes |
| v0.0.6 | 2025-06-10 | library.py dict access second pass, finance integration strategy |
| v0.0.7 | 2025-06-10 | main.py syntax errors, student_union_gui.py new file |
| v0.0.8 | 2025-06-09 | DB file path fix (nested path bug in db.py) |
| v0.0.9 | 2025-06-09 | DatabaseManager class, graceful imports, MFA validation, parking critical fixes |
| v0.1.0 | 2025-06-09 | email_metrics missing functions, dashboard added |
| v0.2.0 | 2025-06-18 | accommodation audit_log comprehensive migration |
| v0.3.0 | 2025-06-10 | restaurant update_customer(), duplicate functions removed, SQL injection |
| v0.4.0 | 2025-06-12 | chatbot+auth full integration: set_auth(), REST API, session management, MFA |
| v0.5.0 | 2025-06-12 | student_support 5 undefined functions, permissions schema, chatbot duplicate fix |
| v0.6.0 | 2025-06-18 | housing_accommodation_gui.py new file (22 orig_ function wrappers) |
| v0.7.0 | 2025-06-10 | main.py set_auth alias conflicts fixed across all 12 modules |
| v0.8.0 | 2025-06-15 | student_grading_gui.py new file, housing_management_gui.py v2 |
| v0.9.0 | 2025-06-09 | restaurant_management_gui.py new file (full tabbed GUI) |
| v1.0.0 | 2025-06-15 | grade_tracking_gui missing imports, undefined functions, missing attributes |
| v1.1.0 | 2025-06-17 | activity_logger_gui DatabaseManagementDialog, housing_gui second pass |
| v1.2.0 | 2025-06-16 | chatbot font TypeError, library_gui incomplete methods, housing_gui structural |
| v1.3.0 | 2025-07-15 | grade_tracking_gui edit_selected_grade() completed; Finance GUI startup |
| v1.4.0 | 2025-07-20 | course_management, academic_calendar, housing, log_management, shop, accommodation |
| v1.5.0 | 2025-07-22 | student_support_gui.py missing functions added |
| v1.6.0 | 2025-09-05 | email_manager_gui.py: ChatRoomWindow, AnnouncementDetailsDialog, BulkEmailDialog |
| v1.7.0 | 2025-09-07 | students table schema migration across 12 modules |
| v1.8.0 | 2025-09-08 | grade_tracking_gui.py: 6 new dialog classes, risk assessment, predictive analytics |
| v1.9.0 | 2025-09-10 | Finance GUI + chatbot schema sync, display_enhanced_finance_menu added |
| v2.0.0 | 2025-09-15 | restaurant_management.py: all imports updated for refactored structure |
| v2.1.0 | 2025-09-16 | health_portal.py import cleanup, restaurant cross-file imports, finance+auth |
| v2.2.0 | 2025-09-20 | email_manager.py: messages table schema fix, 6 missing columns, send_message rewrite |
| v2.3.0 | 2026-01-27 | 53 markdown files consolidated into readme.md + changelog.md |
| v2.4.0 | 2026-03-07 | parent_portal_gui.py new file (~1,200 lines), main.py integration |
| v2.5.0 | 2026-03-07 | AcademicAffairs.py: 6 missing DB tables, import errors, broken INSERT |

---

*End of Version Quick Reference*

---

*CHANGELOG.md — University Student Management System*
*Final compiled version: March 2026*
*Total lines: ~10,000 | Words: ~45,000*


---


---

## APPENDIX H — GUI WIDGET INVENTORY


The following lists every Tkinter widget class and custom dialog used across all GUI
modules, grouped by module file.

---

### main.py — StudentManagementGUI

**Main window widgets:**
- `tk.Tk` — Root window (1400×900)
- `tk.Frame` — Top header bar
- `ttk.Label` — System title, current user display
- `ttk.Button` — Logout button, all navigation buttons
- `tk.Canvas` — Scrollable container for sidebar
- `ttk.Scrollbar` — Sidebar vertical scrollbar
- `ttk.LabelFrame` — Navigation section groupings (Academic, Finance, Services, etc.)
- `ttk.Frame` — Main content area
- `scrolledtext.ScrolledText` — System log output

**Login dialog:**
- `tk.Toplevel` — Login window (400×300)
- `ttk.Label` — Username, Password labels
- `ttk.Entry` — Username entry, Password entry (show='*')
- `ttk.Button` — Login button, Cancel button
- `ttk.Label` — Error message display (red foreground)

**Loading window:**
- `tk.Toplevel` — Loading window (300×150)
- `ttk.Label` — Loading message
- `ttk.Progressbar` — Indeterminate mode progress bar

---

### grade_tracking_gui.py — GradeTrackingGUI

**Main window:**
- `ttk.Notebook` — Tab container
- `ttk.Frame` — Tab frames (Grades, Analytics, At-Risk, Predictions, Reports)

**Grades tab:**
- `ttk.Frame` — Filter bar
- `ttk.Combobox` — Module selector, course selector
- `ttk.Entry` — Student search entry
- `ttk.Button` — Search, Add Grade, Edit Grade, Delete Grade, Refresh
- `ttk.Treeview` — Grade records table
- `ttk.Scrollbar` — Horizontal and vertical for treeview
- `ttk.Label` — Status bar at bottom

**GradeDialog:**
- `tk.Toplevel` — Modal dialog (500×450)
- `ttk.Combobox` — Student selector, Assessment selector
- `ttk.Entry` — Score input, Date input, Late penalty input
- `tk.Text` — Feedback text area
- `ttk.Label` — Grade preview, Max points display
- `ttk.Button` — Save Grade, Cancel

**RiskAssessmentDialog:**
- `tk.Toplevel` — 800×600
- `ttk.Treeview` — At-risk student list
- `ttk.Label` — Risk score, threshold display
- `ttk.Button` — Generate Report, Export CSV, Send Alerts, Close

**PredictiveAnalyticsDialog:**
- `tk.Toplevel` — 900×650
- `FigureCanvasTkAgg` — Embedded matplotlib figure (prediction charts)
- `ttk.Treeview` — Prediction results table
- `ttk.Button` — Run Predictions, Export, Train Model, Close

---

### health_portal_gui.py — HealthPortalGUI

**Main window:**
- `ttk.Notebook` — 9-tab container
- `ttk.Frame` — Each tab frame

**Health Records tab:**
- `ttk.Treeview` — Records list
- `ttk.LabelFrame` — Filter section
- `ttk.Entry` — Student ID search
- `ttk.Combobox` — Record type filter
- `ttk.Button` — Add, View, Edit, Delete
- `tk.Toplevel` — Record detail dialog (600×500)
- `scrolledtext.ScrolledText` — Diagnosis and notes display

**Vaccination tab:**
- `ttk.Treeview` — Vaccination records
- `tk.Toplevel` — Add vaccination dialog
- `ttk.Entry` — Vaccine name, lot number, manufacturer
- `ttk.Combobox` — Administration site, route
- `ttk.Checkbutton` — Adverse reaction checkbox
- `ttk.Button` — Export to CSV

**Appointments tab:**
- `ttk.Treeview` — Appointment list with status colour coding
- `tk.Toplevel` — Schedule appointment dialog
- `tkcalendar.DateEntry` — Appointment date picker
- `ttk.Combobox` — Time slot, Provider, Appointment type
- `ttk.Button` — Schedule, Cancel, Complete, No-Show

**Referrals tab — colour-coded TreeView:**
```python
# Tag configuration for urgency colours
self.referrals_tree.tag_configure('stat', background='#ffcccc')      # red
self.referrals_tree.tag_configure('urgent', background='#fff3cc')    # yellow
self.referrals_tree.tag_configure('routine', background='#ccffcc')   # green
self.referrals_tree.tag_configure('overdue', background='#ff9999')   # dark red
```

**Security Management tab:**
- `ttk.Treeview` — Audit log entries
- `ttk.Combobox` — Log filter (all / reads / writes / deletes)
- `ttk.Spinbox` — Session timeout minutes
- `ttk.Button` — Generate security report, Export audit log

**Reports tab:**
- `ttk.Combobox` — Report type selector
- `tkcalendar.DateEntry` — Date from, Date to
- `FigureCanvasTkAgg` — Chart display area
- `ttk.Button` — Generate, Export PDF, Export CSV

---

### helpdesk_gui.py — HelpdeskGUI

**Main window:**
- `ttk.Notebook` — 5-tab container (Dashboard, Tickets, Knowledge Base, My Assignments, Reports)

**Dashboard tab:**
- `ttk.Frame` — 4 summary card frames
- `ttk.Label` — Count labels (large font, coloured)
- `ttk.Progressbar` — SLA compliance bar
- `scrolledtext.ScrolledText` — Recent activity feed (auto-scroll)

**Tickets tab:**
- `ttk.Frame` — Filter bar
- `ttk.Entry` — Search box
- `ttk.Combobox` — Status, Priority, Category, Assigned-to filters
- `ttk.Button` — Search, Clear Filters, New Ticket, Refresh
- `ttk.Treeview` — Ticket list (columns: ID, Subject, Submitter, Status, Priority, SLA)
- Custom SLA status indicator column using coloured oval canvases

**TicketDetailDialog:**
- `tk.Toplevel` — 900×650
- `ttk.LabelFrame` — Ticket info panel, Response history panel, Action panel
- `scrolledtext.ScrolledText` — Response history (read-only)
- `tk.Text` — New response input
- `ttk.Combobox` — Status change selector
- `ttk.Button` — Send Response, Update Status, Escalate, Close Ticket

**TicketCreationDialog:**
- `tk.Toplevel` — 600×500
- `ttk.Entry` — Subject
- `ttk.Combobox` — Category, Priority
- `scrolledtext.ScrolledText` — Description
- `ttk.Button` — Attach File (opens filedialog), Submit, Cancel

---

### shop_management_gui.py — UniversityShopGUI

**POS tab:**
- `ttk.Frame` — Split layout: product area (left 60%) + cart area (right 40%)
- `ttk.Entry` — Product search bar (with StringVar trace for live filtering)
- `tk.Frame` — Product grid (scrollable canvas)
- `ttk.Button` — Product cards (dynamically generated, 3 per row)
- `ttk.Label` — Product name, price, stock badge on each card
- `ttk.Treeview` — Cart items list
- `ttk.Label` — Cart total (large bold font, updates on change)
- `ttk.Button` — Cash payment, Card payment, Meal Plan, Clear Cart

**Product quantity dialog (when adding to cart):**
- `tk.Toplevel` — 250×150
- `ttk.Spinbox` — Quantity (1 to max_stock)
- `ttk.Button` — Add to Cart, Cancel

**Payment dialogs:**
- Cash: `tk.Toplevel` with amount tendered Entry, change display
- Card: `tk.Toplevel` with card type Combobox, approval simulation
- Meal Plan: `tk.Toplevel` with student ID lookup, balance check, confirm

---

### student_union_gui.py — StudentUnionGUI

**Clubs tab:**
- `ttk.Treeview` — Clubs list (columns: ID, Name, Category, Members, Leader, Date)
- `ttk.Button` — View Details, Join/Leave, Create Club, Edit Club, Delete Club
- `ttk.Combobox` — Category filter

**ClubJoinDialog:**
- `tk.Toplevel` — 400×500
- `ttk.Label` — Club name (large bold), leader, contact email
- `ttk.Progressbar` — Member count / capacity ratio
- `scrolledtext.ScrolledText` — Club description (read-only)
- `ttk.Button` — Join Club, Close

**FacilityBookingDialog:**
- `tk.Toplevel` — 800×600
- Left panel: Calendar grid (7 columns × 6 rows of `ttk.Button` widgets, one per day)
- Right panel: Time slot grid (8am–10pm in 1-hour slots, `ttk.Button` for each)
  - Green buttons: available
  - Red buttons: booked (tooltip shows booked-by name)
  - Blue outline: selected slot
- Bottom panel: Purpose `ttk.Entry`, duration `ttk.Combobox`, Book button

**Equipment tab:**
- `ttk.Treeview` — Equipment list with availability status
- `ttk.Label` — Status indicator (🟢 available / 🔴 checked out)
- `ttk.Button` — Check Out, Return, View History

**Rewards tab:**
- `ttk.Label` — Points balance (large, gold text)
- `tk.Frame` — Badge grid (4 per row)
- `ttk.Label` — Each badge displayed as coloured label with badge name
- `ttk.Treeview` — Leaderboard (top 20 members)
- Current user's rank highlighted with a different background colour

---

### attendance_gui.py — EnhancedAttendanceGUI

**Take Attendance tab:**
- `ttk.Combobox` — Module selector
- `tkcalendar.DateEntry` — Session date
- `ttk.Frame` — Student attendance list
- Per student row: `ttk.Label` (name), `ttk.Radiobutton` ×4 (Present/Late/Absent/Excused)
- `ttk.Button` — Mark All Present, Save Attendance, Generate QR Code

**QR code display (Toplevel):**
- `tk.Toplevel` — 400×450
- `ttk.Label` — Session code text
- `tk.Label` — QR code image (Pillow ImageTk)
- `ttk.Label` — "Scan to check in" instruction
- `ttk.Button` — Refresh QR (generates new token), Close

**Analytics tab:**
- `FigureCanvasTkAgg` — Embedded matplotlib figure
- `ttk.Combobox` — Chart type selector (heatmap, trend, distribution)
- `ttk.Notebook` — Sub-tabs within analytics: Heatmap, Trend, At-Risk

**Gamification tab:**
- `ttk.Label` — Current user's total points (large gold)
- `ttk.Treeview` — Leaderboard
- `ttk.Frame` — Achievement badges grid
- `ttk.Button` — Claim Daily Bonus, View Badge Details

---


---

## APPENDIX I — KNOWN OUTSTANDING ITEMS


1. **Password hashing:** SHA-256 used throughout. Should be migrated to bcrypt or
   argon2 for production security. Migration would require a re-hash on next login.

2. **Single database file:** All 85+ modules share one SQLite file. Under heavy load
   this creates write contention. Migration to PostgreSQL would resolve this.

3. **No CI/CD pipeline:** `run_tests.py` exists but is not run automatically.

4. **Session persistence:** Sessions lost on restart. Consider adding persistent
   session storage to `sessions` table (currently in-memory only for some modules).

5. **Logging consolidation:** Some modules still write to files in the current
   directory rather than the centralised `logs/` directory.

6. **Optional library silent degradation:** Some features silently disappear when
   optional libraries are missing. Consider adding a "missing features" notice to
   the startup log listing which optional features are unavailable.

7. **HTML email support:** `send_email()` accepts an `html_body` parameter but the
   SMTP sending code only sends plain text. HTML email sending not implemented.

8. **Two-way sync between chatbot and main system:** Chatbot reads data but cannot
   write back to student records through the REST API.

9. **Parent portal consent management:** The `get_student_consent_status()` function
   exists but the GUI for students to manage their consent settings is not implemented.

10. **Alumni social features:** The `networking_connections` table exists but the
    GUI for making/accepting networking connections between alumni is not implemented.

---

*End of Appendices*

*CHANGELOG.md — University Student Management System*  
*Compiled March 2026 from full development history*  
*~10,000 lines | ~50,000 words*  
*Covers June 2025 — March 2026*  
*45+ versions | 85+ Python files | 210+ database tables | 120+ permissions*


---

---

## APPENDIX J — CODE STYLE AND CONVENTIONS

  module-private and should only be set via the `set_auth()` function.
- Example: `_health_auth`, `_parking_auth`, `_trip_auth_instance`

**GUI class names:** `[ModuleName]GUI`
- Examples: `HealthPortalGUI`, `StudentUnionGUI`, `UniversityShopGUI`
- Exception: `StudentManagementGUI` (legacy name from original main.py)

**Dialog class names:** `[Feature]Dialog`
- Examples: `GradeDialog`, `ClubJoinDialog`, `TicketDetailDialog`
- All dialog classes inherit from `tk.Toplevel`
- All dialogs call `self.grab_set()` to make them modal

**Entry point functions:** `display_[module]_menu(auth)` for CLI,
`run_[module]_gui(auth)` for GUI, `display_[module]_menu_gui(auth)` for GUI drop-in
replacement.

**Database init functions:** `init_[module]_db()` — return `bool`.

**Permission setup functions:** `setup_[module]_permissions()` or
`add_[module]_permissions()` — return `List[str]` (list of permission names created)
or `None`.

---

### Database conventions

**Primary keys:** All primary keys are either `INTEGER PRIMARY KEY AUTOINCREMENT`
(for auto-numbered records) or `TEXT PRIMARY KEY` (for UUID-based IDs).

**UUID generation:** `str(uuid.uuid4())` for TEXT primary keys.

**Timestamps:** All timestamp columns store ISO 8601 format:
`datetime.now().strftime('%Y-%m-%d %H:%M:%S')`.
Date-only columns: `datetime.now().strftime('%Y-%m-%d')`.

**Foreign keys:** Always `REFERENCES [table]([column])` in CREATE TABLE.
`PRAGMA foreign_keys=ON` applied to all connections.

**Status columns:** Always `TEXT` with a DEFAULT value, not an enum. Common values:
- Files/documents: `pending`, `approved`, `rejected`, `expired`, `archived`
- Orders: `pending`, `confirmed`, `processing`, `completed`, `cancelled`
- Tickets: `open`, `in_progress`, `resolved`, `closed`, `on_hold`
- Appointments: `scheduled`, `arrived`, `in_progress`, `completed`, `cancelled`, `no_show`
- Payments: `unpaid`, `paid`, `partial`, `waived`, `overdue`
- Permits: `active`, `expired`, `suspended`, `cancelled`

**Boolean columns:** `INTEGER DEFAULT 0` where 0=False, 1=True. Never actual `BOOLEAN`
type (SQLite stores booleans as integers anyway).

**Soft deletes:** Prefer `is_archived INTEGER DEFAULT 0` over DELETE for user-facing
records. Hard DELETE only for truly transient data (session tokens, queue entries).

---

### Error handling conventions

**Database errors:** Always caught with `except sqlite3.Error as e`. Log with
`logging.error(f"Database error in {function_name}: {e}")`. Return `None` or `False`.

**Import errors:** Always caught with `except ImportError`. Set a `*_AVAILABLE = False`
flag. Never re-raise ImportError — allow the system to start without the feature.

**GUI errors:** Always shown to the user via `messagebox.showerror()`. Never let
exceptions propagate to Tkinter's main loop (causes silent crashes).

**Validation errors:** Return a tuple `(False, "Error message")` for functions that
validate before acting. Never raise `ValueError` for expected user input errors.

**Threading:** All database operations in GUI background threads catch all exceptions
and post errors back to the main thread via `root.after(0, show_error, str(e))`.
Never touch Tkinter widgets from a background thread.

---

### Import order convention

Standard import order across all modules:
```python
# 1. Standard library
import os
import sys
import sqlite3
import logging
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import uuid
import json
import csv
import re
import shutil
import hashlib
import secrets

# 2. Optional standard library (with availability flag)
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, scrolledtext
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# 3. Third-party (with availability flag)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

# 4. Local modules
from database_utils import get_connection, get_db_path, backup_before_operation
from simple_activity_logger import log_activity, log_create, log_update, log_delete

# 5. Module-level configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 6. Module-level state
_auth = None
```

---

### Logging conventions

All significant operations are logged at appropriate levels:
- `logging.debug()` — Detailed diagnostic information (not enabled in production).
- `logging.info()` — Normal operation confirmation ("Database initialized", "User logged in").
- `logging.warning()` — Something unexpected but recoverable ("Optional library not available").
- `logging.error()` — Something failed but the system continues ("Database operation failed").
- `logging.critical()` — System cannot continue ("Cannot open database file").

Log format: `%(asctime)s - %(levelname)s - %(message)s`
Timestamps in log: `2025-06-09 14:23:45,123`

All modules use: `logger = logging.getLogger(__name__)` for module-specific loggers.

---

### GUI style guide

**Colour scheme (default throughout project):**
```python
COLORS = {
    'primary': '#2196F3',       # Material Blue
    'secondary': '#757575',     # Grey
    'success': '#4CAF50',       # Green
    'warning': '#FF9800',       # Orange
    'error': '#f44336',         # Red
    'background': '#f5f5f5',    # Light grey
    'surface': '#ffffff',       # White
    'text': '#212121',          # Near-black
    'text_secondary': '#757575' # Grey
}
```

**Font hierarchy:**
- Title: `('Arial', 18, 'bold')` or `('Helvetica', 18, 'bold')`
- Section header: `('Arial', 14, 'bold')`
- Normal text: `('Arial', 10)`
- Small/secondary: `('Arial', 9)`
- Code/monospace: `('Courier', 10)` or `('Consolas', 10)`

**Button sizes:**
- Standard action button: `width=15` (ttk.Button)
- Wide action button: `width=20`
- Icon button: `width=3` (for +/- buttons)

**Padding:**
- Between sections: `pady=10`
- Within a section: `pady=5, padx=10`
- Internal widget padding: `padx=5, pady=3`

**Treeview style:**
- Row height: 25px (`style.configure('Treeview', rowheight=25)`)
- Alternating row colours via `tag_configure('odd_row', background='#f9f9f9')`
- Header font bold: `style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))`

---

### Comment and docstring conventions

All public functions include a docstring:
```python
def create_permit(student_id, vehicle_id, lot_id, permit_type, start_date, end_date):
    """
    Create a new parking permit.
    
    Args:
        student_id (str): The student ID.
        vehicle_id (str): The vehicle ID (must exist in vehicles table).
        lot_id (str): The parking lot ID.
        permit_type (str): One of 'annual', 'semester', 'monthly', 'daily'.
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format.
    
    Returns:
        str: The new permit ID on success.
        None: On failure (check logs for details).
    
    Raises:
        Does not raise. All exceptions are caught and logged.
    """
```

**TODO comments:** Format: `# TODO(username): description — YYYY-MM-DD`
Example: `# TODO(dev): Migrate to bcrypt — 2025-09-01`

**FIXME comments:** Format: `# FIXME: description`
Used for known bugs not yet fixed. Removed when the bug is resolved.


## APPENDIX K — DEPENDENCY TREE

```
main.py
├── user_authentication.py
│   └── (no project imports)
├── grade_tracking_gui.py
│   └── (database_utils, simple_activity_logger)
├── health_portal.py
│   └── email_manager.py
│       └── (database_utils)
├── finance.py
│   └── (database_utils, simple_activity_logger)
├── finance_reporting.py
│   └── finance.py
├── library.py
│   └── (database_utils)
├── parking_management.py
│   └── (database_utils)
├── alumni_management.py
│   └── (database_utils, simple_activity_logger)
├── restaurant_management.py
│   └── (database_utils, simple_activity_logger)
├── shop_management.py
│   └── (database_utils, simple_activity_logger)
├── helpdesk.py
│   └── (database_utils)
├── student_support.py
│   └── (database_utils)
├── student_union.py
│   └── (database_utils)
├── internship_management.py
│   └── (database_utils)
├── trip_management.py
│   └── (database_utils)
├── housing_accommodation.py
│   └── (database_utils)
├── accommodation.py
│   └── (database_utils)
├── document_manager.py
│   └── (database_utils)
├── data_backup.py
│   └── (database_utils)
├── batch_operations.py
│   └── (database_utils, simple_activity_logger)
├── advanced_search.py
│   └── (database_utils)
├── academic_calendar.py
│   └── (database_utils)
├── course_management.py
│   └── (database_utils)
├── AcademicAffairs.py
│   └── (database_utils)
├── assignment_submission.py
│   └── (database_utils, simple_activity_logger)
├── attendance_tracker.py
│   └── (database_utils, simple_activity_logger)
├── university_chatbot.py
│   └── user_authentication.py
├── ai_detector.py
│   └── (database_utils)
├── plagiarism_main.py
│   └── (database_utils)
├── parent_portal.py
│   └── (database_utils)
├── log_management.py
│   └── (database_utils)
└── database_utils.py
    └── (no project imports — foundation module)
```

**Circular dependency check:** No circular dependencies confirmed. All modules depend
on `database_utils` and `simple_activity_logger` (leaf nodes) but not on each other
directly. `main.py` is the only module that imports from all others.

---

