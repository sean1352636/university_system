# Technical Reference

Detailed technical documentation for the University Student Management System.
Extracted from development history — covers module APIs, integration patterns,
function signatures, database schemas, and error handling conventions.

---

## Table of Contents

### Module Technical References

- [Plagiarism Checker — Technical Reference](#plagiarism-checker--technical-reference)
- [Parent Portal — Technical Reference](#parent-portal--technical-reference)
- [Trip Management — Technical Reference](#trip-management--technical-reference)
- [Log Management — Technical Reference](#log-management--technical-reference)
- [Advanced Search System — Technical Reference](#advanced-search-system--technical-reference)
- [Finance Reporting — Technical Reference](#finance-reporting--technical-reference)
- [Module Scheduling — Technical Reference](#module-scheduling--technical-reference)
- [DatabaseManager Class — Technical Reference (v0.0.9)](#databasemanager-class--technical-reference-v009)
- [simple_activity_logger.py — Technical Reference](#simple_activity_loggerpy--technical-reference)
- [database_utils.py — Technical Reference](#database_utilspy--technical-reference)

### Integration Patterns

- [Integration — Calendar System](#integration--calendar-system)
- [Reporting Module — Integration Pattern Reference](#reporting-module--integration-pattern-reference)
- [System-Wide Error Handling Patterns](#system-wide-error-handling-patterns)

### Database References

- [main.py — Attribute Error Fixes (2025-06-23)](#mainpy--attribute-error-fixes-2025-06-23)
- [alumni_management.py — 20+ New Tables Reference (v0.0.1)](#alumni_managementpy--20+-new-tables-reference-v001)
- [library.py — 15+ New Tables Reference (v0.0.3)](#librarypy--15+-new-tables-reference-v003)

### Code Reference

- [COMPLETE FUNCTION SIGNATURE REFERENCE](#complete-function-signature-reference)
- [GLOSSARY OF KEY TERMS](#glossary-of-key-terms)

### Project Reference

- [EXTENDED MODULE REFERENCE — CONTINUED](#extended-module-reference--continued)
- [CHANGE LOG — MINOR FIXES AND MAINTENANCE](#change-log--minor-fixes-and-maintenance)
- [SUMMARY STATISTICS](#summary-statistics)
- [DEVELOPMENT NARRATIVE — TIMELINE AND CONTEXT](#development-narrative--timeline-and-context)
- [INDEX OF ALL CHANGES BY FILE](#index-of-all-changes-by-file)

---

## EXTENDED MODULE REFERENCE — CONTINUED


---

## Plagiarism Checker — Technical Reference


### Integration history

#### 2025-06-09 — ai_integration import removed from main.py
Error: `ModuleNotFoundError: No module named 'ai_integration'`

The `ai_integration.py` file had been deleted during a previous refactoring session.
`main.py` still had an import for it at line 14:
```python
# Removed:
from ai_integration import display_ai_detector_menu_from_main, integrate_ai_detector_with_main
```

Replaced with direct import from `ai_detector.py`:
```python
from ai_detector import AIDetector
```

Two replacement functions defined at module level in `main.py`:

**`integrate_ai_detector_with_main()`:**
```python
def integrate_ai_detector_with_main():
    global ai_detector
    try:
        ai_detector = AIDetector()
        if auth:
            ai_detector.set_auth(auth)
        print("AI detector system initialized successfully!")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize AI detector: {e}")
        print(f"Warning: AI detector initialization failed: {e}")
        return False
```

**`integrate_plagiarism_checker_with_main()`:**
```python
def integrate_plagiarism_checker_with_main():
    try:
        from plagiarism_main import PlagiarismChecker
        checker = PlagiarismChecker()
        logging.info("Plagiarism checker database tables initialized")
    except Exception as e:
        logging.error(f"Error initializing plagiarism checker: {e}")
        return False
    permissions = add_plagiarism_permissions()
    if permissions:
        logging.info(f"Added plagiarism checker permissions: {', '.join(permissions)}")
    logging.info("Plagiarism checker integration completed successfully!")
    return True
```

#### 2025-06-12 — Permissions integration with UserAuth

`add_plagiarism_permissions(auth_instance)` added to `user_authentication.py`:
- Uses existing `DatabaseConnectionManager` pattern (not creating a new connection).
- Permissions list:
  ```python
  plagiarism_permissions = [
      ('check_plagiarism', 'Check documents for plagiarism'),
      ('manage_plagiarism_system', 'Manage plagiarism detection system'),
      ('view_plagiarism_reports', 'View plagiarism detection reports'),
      ('access_plagiarism_menu', 'Access plagiarism checker menu'),
      ('submit_plagiarism_check', 'Submit documents for plagiarism checking'),
      ('manage_document_repository', 'Manage the document repository'),
      ('view_similarity_scores', 'View document similarity scores'),
      ('export_plagiarism_data', 'Export plagiarism check data'),
  ]
  ```
- Role assignments: `admin` and `staff` get all permissions; `instructor` gets
  `check_plagiarism`, `view_plagiarism_reports`, `submit_plagiarism_check`,
  `view_similarity_scores`; `student` gets `submit_plagiarism_check` only.
- `test_plagiarism_authentication()` function added to verify setup.

#### 2025-07-07 — PlagiarismCheckerGUI create_menu_buttons fix
Error: `AttributeError: 'PlagiarismCheckerGUI' object has no attribute 'create_menu_buttons'`

The `__init__` method was calling `self.create_menu_buttons(parent_frame)` but the
method was named `create_menu_buttons_with_integration()`.

Fix: Added `create_menu_buttons(self, parent)` as an alias:
```python
def create_menu_buttons(self, parent):
    """Alias for create_menu_buttons_with_integration — fixes AttributeError"""
    return self.create_menu_buttons_with_integration(parent)
```

Final button list in `create_menu_buttons_with_integration`:
- "Submit Document" → `self.submit_document`
- "Check for Plagiarism" → `self.check_plagiarism`
- "View Results" → `self.view_results`
- "Search Repository" → `self.search_repository`
- "View Statistics" → `self.view_statistics`
- "Assignment System" → `self.open_assignment_system`
- "Assignment Reports" → `self.view_assignment_reports`
- "System Setup" → `self.setup_system`
- "Test System" → `self.test_system`
- "Help" → `self.show_help`
- "Exit" → `self.exit_application`

#### 2025-08-21 — Empty try block syntax fix

```python
# Before (invalid Python — empty try block):
try:
    ai_detector = create_minimal_ai_detector()
    pass  # auto-inserted to fix empty try block
    print("✅ Minimal AI detector created as fallback")
    return True
except Exception as fallback_error:
    ...

# After (correct):
try:
    ai_detector = create_minimal_ai_detector()
    print("✅ Minimal AI detector created as fallback")
    return True
except Exception as fallback_error:
    logging.error(f"Even fallback AI detector failed: {fallback_error}")
    print(f"❌ Complete AI detector failure: {fallback_error}")
    return False
```

#### 2025-08-30 — Plagiarism tab added to main GUI notebook

`create_tabs()` in `UnifiedManagementGUI` updated:

```python
# After the assignments tab:
if (self.auth.current_user and (
    self.auth.check_permission('check_plagiarism') or
    self.auth.check_permission('access_plagiarism_menu') or
    self.auth.check_permission('submit_plagiarism_check')
)):
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text="Plagiarism Checker")
    self.create_plagiarism_tab(tab_frame)
```

`create_plagiarism_tab(self, parent)` method:
- Adds description label and launch button.
- "Open Plagiarism Checker" button calls `self.open_plagiarism_checker_gui()`.
- Instruction text explaining how to submit documents.

`open_plagiarism_checker_gui(self)`:
```python
def open_plagiarism_checker_gui(self):
    try:
        from plagiarism_main import PlagiarismCheckerGUI, display_plagiarism_checker_menu
        top = tk.Toplevel(self.root)
        top.title("Plagiarism Detection System")
        top.geometry("1100x750")
        gui = PlagiarismCheckerGUI(top, self.auth)
        self.log_output("✅ Plagiarism Checker GUI opened")
    except ImportError as e:
        messagebox.showinfo("Plagiarism Checker",
                            f"GUI not available: {e}\nOpening text interface...")
        display_plagiarism_checker_menu(self.auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Plagiarism Checker: {e}")
        self.log_output(f"❌ Plagiarism Checker failed: {e}")
```

---

## Parent Portal — Technical Reference


### Integration history

#### 2025-06-09 — Original parent portal redesign

`parent_portal.py` was split into two files to separate concerns:
- `parent_portal.py` — `UniversityParentPortal` class (user interface, views).
- `parent_portal_integration.py` — Utility functions for other modules to call.

**`parent_portal_integration.py` utility functions:**
- `init_parent_portal()` — Creates all parent portal database tables.
- `display_parent_portal_menu(auth)` — Entry point for CLI menu.
- `send_parent_notification(parent_id, subject, body)` — Send notification to a parent.
- `add_academic_report(student_id, report_data)` — Adds a report that parents can view.
- `add_fee_record(student_id, fee_data)` — Creates a financial record visible to parents.
- `check_parent_access(parent_id, student_id)` — Checks if a parent-student link exists.
- `get_student_consent_status(student_id)` — Returns consent flags for data sharing.
- `update_student_consent(student_id, consent_type, value)` — Updates consent.
- `record_academic_probation(student_id, reason)` — Flags and notifies parents.
- `update_dining_account(student_id, balance)` — Updates dining balance visible to parents.

**Database tables created:**
```sql
CREATE TABLE IF NOT EXISTS parent_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    created_at TEXT,
    is_active INTEGER DEFAULT 1,
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS parent_student_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES parent_accounts(id),
    student_id TEXT REFERENCES students(student_id),
    relationship TEXT DEFAULT 'parent',
    approved INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS parent_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES parent_accounts(id),
    title TEXT,
    message TEXT,
    notification_type TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TEXT,
    related_student_id TEXT
);

CREATE TABLE IF NOT EXISTS parent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES parent_accounts(id),
    recipient_staff_id INTEGER REFERENCES users(id),
    subject TEXT,
    body TEXT,
    sent_at TEXT,
    is_read INTEGER DEFAULT 0,
    reply_to_id INTEGER,
    direction TEXT DEFAULT 'parent_to_staff'
);
```

#### 2025-06-29 — Integration gaps found and fixed

`open_parent_portal()` in `main.py` was not passing auth to the parent portal:
```python
# Broken:
def open_parent_portal(self):
    from parent_portal import ParentPortalGUI
    app = ParentPortalGUI()  # No auth passed
    app.run()

# Fixed:
def open_parent_portal(self):
    if not self.auth or not self.auth.current_user:
        messagebox.showerror("Error", "Please login first")
        return
    user_role = self.auth.current_user.get('role', '')
    if user_role not in ('parent', 'admin', 'staff'):
        messagebox.showerror("Access Denied",
                             "You don't have permission to access the parent portal")
        return
    try:
        from parent_portal import ParentPortal, ParentPortalGUI, integrate_parent_portal_with_main
        if not integrate_parent_portal_with_main():
            messagebox.showerror("Error", "Failed to initialize parent portal database")
            return
        parent_app = ParentPortalGUI(self.auth)
        parent_app.run()
        self.log_output("✅ Parent Portal opened successfully")
    except Exception as gui_error:
        error_msg = f"Parent Portal GUI failed: {str(gui_error)}"
        self.log_output(f"❌ {error_msg}")
        if messagebox.askyesno("GUI Failed",
                               f"{error_msg}\n\nWould you like to try the text interface?"):
            display_parent_portal_menu(self.auth)
```

**`parent` role added to `user_authentication.py` ROLES dict:**
```python
'parent': 'Parent with access to children\'s academic records'
```

**Parent permissions added to PERMISSIONS dict:**
```python
'view_child_records': 'View linked child\'s academic records',
'view_child_grades': 'View linked child\'s grades',
'view_child_attendance': 'View linked child\'s attendance records',
'view_child_fees': 'View linked child\'s fee statements',
'message_teachers': 'Send messages to staff members',
'manage_parent_portal': 'Manage parent portal settings and links',
'access_parent_portal': 'Access the parent portal',
```

**`setup_parent_portal_permissions()` added:**
Assigns all parent permissions to the `parent` role and `access_parent_portal` plus
`view_child_records` to `admin` and `staff`.

#### 2025-06-29 — parent_portal.py `integrate_parent_portal_with_main()` enhanced

Before: Only created tables. After: Also creates sample data for testing:
```python
def integrate_parent_portal_with_main():
    """Enhanced integration with sample data creation"""
    try:
        init_parent_portal_db()
        create_sample_parent_data()
        logging.info("Parent portal integration complete!")
        return True
    except Exception as e:
        logging.error(f"Parent portal integration failed: {e}")
        return False

def create_sample_parent_data():
    """Create sample parent accounts and links for testing"""
    conn = get_connection()
    cursor = conn.cursor()
    sample_parents = [
        ('parent1', hash_password('parent123'), 'parent1@example.com', 'John', 'Smith'),
        ('parent2', hash_password('parent123'), 'parent2@example.com', 'Mary', 'Jones'),
    ]
    for username, pwd_hash, email, first_name, last_name in sample_parents:
        cursor.execute('SELECT id FROM parent_accounts WHERE username = ?', (username,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO parent_accounts (username, password_hash, email, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, pwd_hash, email, first_name, last_name,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
```

#### 2025-09-02 — parent_portal_gui.py integration fix

`parent_portal_gui.py` `run_parent_portal_gui(auth)` function:
```python
def run_parent_portal_gui(auth):
    """Module-level entry point for launching parent portal GUI"""
    try:
        app = ParentPortalGUI(auth)
        root = app.create_main_window()
        if root:
            root.mainloop()
        else:
            # Fallback to CLI
            from refactored.services.parent_portal import display_parent_portal_menu
            display_parent_portal_menu(auth)
    except Exception as e:
        print(f"Error running Parent Portal GUI: {e}")
        try:
            from refactored.services.parent_portal import display_parent_portal_menu
            display_parent_portal_menu(auth)
        except Exception as cli_error:
            print(f"CLI version also failed: {cli_error}")
```

Email regex fix in `validate_email()`:
```python
# Before (missing closing quote — SyntaxError):
pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}

# After:
pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
```

---

## Trip Management — Technical Reference


### Integration history

#### 2025-06-13 — Academic calendar integration

`calendar_trip_integration.py` new file created to link both systems:

`IntegratedAcademicSystem` class:
- `__init__(self, auth)` — Stores auth. Sets up both calendar and trip auth.
- `create_trip_with_calendar_event(self, trip_data)` — Creates a trip record AND a
  corresponding calendar event on the same date. Returns both IDs.
- `get_trips_with_calendar_context(self)` — Joins trip records with any matching calendar
  events on the same date for display.
- `sync_trip_changes_to_calendar(self, trip_id)` — Updates the linked calendar event
  when trip details change.

#### 2025-06-25 — Auth not passed to trip management

Error: "You must be logged in to access trip management." even when user was logged in.

Root cause: `open_trip_management()` in `StudentManagementGUI` was creating a
subprocess-style thread and calling `display_trip_management_menu()` without passing
the auth object, and without calling `set_trip_auth()` first.

Fix:
```python
def open_trip_management(self):
    if not self.auth or not self.auth.current_user:
        messagebox.showerror("Error", "Please login first")
        return
    if not any(self.auth.check_permission(p) for p in
               ('manage_trips', 'view_trips', 'register_for_trips')):
        messagebox.showerror("Access Denied",
                             "You don't have permission to access trip management")
        return

    choice = messagebox.askyesnocancel(
        "Trip Management System",
        "Yes = GUI Interface\nNo = Text Interface (CLI)\nCancel = Return")

    if choice is True:
        try:
            from trip_management import TripManagementGUI, set_auth as set_trip_auth
            set_trip_auth(self.auth)  # CRITICAL: set auth before creating GUI
            trip_app = TripManagementGUI(self.auth)
            trip_app.run()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Trip Management GUI: {e}")
    elif choice is False:
        from trip_management import display_trip_management_menu, set_auth as set_trip_auth
        set_trip_auth(self.auth)  # Also needed for CLI
        display_trip_management_menu(self.auth)
```

#### 2025-07-27 — Missing trip functions defined

The following were called but undefined — all implemented:

**`setup_trip_permissions()`:**
```python
def setup_trip_permissions():
    """Create trip permissions and assign to roles"""
    permissions = {
        'view_trips': 'View available trips',
        'create_trips': 'Create new trips',
        'manage_trips': 'Manage all trip aspects',
        'register_for_trips': 'Register for trips',
        'cancel_trip_registration': 'Cancel trip registration',
        'manage_trip_expenses': 'Manage trip expenses',
        'view_trip_reports': 'View trip management reports',
    }
    role_permissions = {
        'admin': list(permissions.keys()),
        'staff': ['view_trips', 'create_trips', 'manage_trips', 'view_trip_reports'],
        'instructor': ['view_trips', 'register_for_trips', 'cancel_trip_registration'],
        'student': ['view_trips', 'register_for_trips', 'cancel_trip_registration'],
    }
    conn = get_connection()
    cursor = conn.cursor()
    for perm_name, perm_desc in permissions.items():
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description) VALUES (?, ?)',
            (perm_name, perm_desc))
    for role_name, perms in role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE name = ?', (role_name,))
        role_row = cursor.fetchone()
        if role_row:
            role_id = role_row[0]
            for perm_name in perms:
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                perm_row = cursor.fetchone()
                if perm_row:
                    cursor.execute(
                        'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                        (role_id, perm_row[0]))
    conn.commit()
    conn.close()
    return True
```

**`set_trip_auth(auth_instance)`:**
```python
_trip_auth_instance = None

def set_trip_auth(auth_instance):
    global _trip_auth_instance
    _trip_auth_instance = auth_instance
    logging.info("Trip management authentication configured")
```

**`integrate_trip_management_with_main()`:**
```python
def integrate_trip_management_with_main():
    try:
        if not init_trip_db():
            logging.error("Failed to initialize trip database")
            return False
        if not setup_trip_permissions():
            logging.error("Failed to setup trip permissions")
            return False
        logging.info("Trip management integration completed successfully")
        return True
    except Exception as e:
        logging.error(f"Error integrating trip management: {e}")
        return False
```

**`init_trip_db()`:**
```python
def init_trip_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS trips (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        destination TEXT,
        start_date TEXT,
        end_date TEXT,
        organiser_id INTEGER REFERENCES users(id),
        capacity INTEGER DEFAULT 30,
        registration_deadline TEXT,
        cost REAL DEFAULT 0.0,
        status TEXT DEFAULT 'upcoming',
        created_at TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trip_registrations (
        id TEXT PRIMARY KEY,
        trip_id TEXT REFERENCES trips(id),
        student_id TEXT REFERENCES students(student_id),
        registration_date TEXT,
        status TEXT DEFAULT 'confirmed',
        payment_status TEXT DEFAULT 'unpaid',
        notes TEXT,
        emergency_contact TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trip_calendar_links (
        id TEXT PRIMARY KEY,
        trip_id TEXT REFERENCES trips(id),
        calendar_event_id TEXT,
        created_at TEXT
    )''')
    conn.commit()
    conn.close()
    return True
```

#### 2025-08-20 — TripManagementGUI added

`trip_management_gui.py` new file:

**`TripManagementGUI` class:**
- **Trips tab:** TreeView of all trips filtered by status dropdown. Create/edit/delete
  (admin/staff only). Register/cancel buttons for students.
- **My Registrations tab:** List of trips the current user is registered for. Cancel
  registration button with confirmation dialog.
- **All Registrations tab (admin/staff):** All registrations for a selected trip.
  Download participant list as CSV.
- **Reports tab:** Trip summary report, expense breakdown, occupancy rate per trip.

**`run_trip_management_gui(auth)` entry point:**
```python
def run_trip_management_gui(auth):
    root = tk.Toplevel() if tk._default_root else tk.Tk()
    root.title("Trip Management System")
    root.geometry("1100x700")
    app = TripManagementGUI(root, auth)
    if not tk._default_root:
        root.mainloop()

def display_trip_management_menu_gui(auth):
    """Drop-in replacement for display_trip_management_menu using GUI"""
    run_trip_management_gui(auth)
```

---

## Log Management — Technical Reference


#### log_management.py — File path refactoring (2025-07-31)
All log file paths were previously hard-coded as relative paths like `'system.log'`,
`'error.log'`, `'activity.log'`. This caused logs to be written to whichever directory
the process was started from.

Refactored to use consistent project-root-relative paths:
```python
import os

_THIS_FILE = os.path.abspath(__file__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE)))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

SYSTEM_LOG = os.path.join(LOG_DIR, 'system.log')
ERROR_LOG = os.path.join(LOG_DIR, 'error.log')
ACTIVITY_LOG = os.path.join(LOG_DIR, 'activity.log')
SECURITY_LOG = os.path.join(LOG_DIR, 'security.log')
AUDIT_LOG = os.path.join(LOG_DIR, 'audit.log')
```

All `logging.FileHandler('system.log')` references updated to
`logging.FileHandler(SYSTEM_LOG)` etc.

**`RotatingFileHandler` applied to all logs:**
```python
handler = logging.handlers.RotatingFileHandler(
    SYSTEM_LOG,
    maxBytes=10 * 1024 * 1024,  # 10 MB per file
    backupCount=5
)
```

#### log_management.py — GUI integration tab (2025-08-27)

`create_tabs()` updated to include "Log Management" tab:
```python
if self.auth.check_permission('view_logs') or self.auth.check_permission('manage_logs'):
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text="Log Management")
    self.create_log_management_tab(tab_frame)
```

`create_log_management_tab(self, parent)`:
- Statistics section: number of log entries today, last 7 days, total.
- Log level breakdown: info/warning/error/critical counts.
- "Open Full Log Manager" button calling `self.open_log_management_gui()`.
- Recent entries preview: last 10 log lines in a `ScrolledText` widget.

`open_log_management_gui(self)`:
```python
def open_log_management_gui(self):
    try:
        from log_management import LogManagementGUI
        top = tk.Toplevel(self.root)
        top.title("Log Management")
        top.geometry("1200x800")
        LogManagementGUI(top, self.auth)
    except ImportError:
        display_log_management_menu(self.auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Log Management: {e}")
```

---

## Advanced Search System — Technical Reference


#### advanced_search.py — Integration fix (2025-06-17)

`integrate_advanced_search_with_main()` called in `init_all_databases()` to register
the module. Earlier sessions had advanced search completely isolated.

Main GUI integration in `create_tabs()`:
```python
if self.auth.check_permission('view_any_student'):
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text="Advanced Search")
    self.embedded_advanced_search = self.create_advanced_search_safely(tab_frame)
```

`create_advanced_search_safely(self, parent_frame)`:
- Wraps `AdvancedSearchGUI(parent_frame, self.auth)` in try/except.
- Falls back to a simple search `Entry` + `Button` if `AdvancedSearchGUI` fails.
- Returns the created widget so caller can reference it for refresh operations.

**`AdvancedSearchGUI` key methods:**
- `build_filter_row(self, label, filter_key, filter_type)` — Creates a filter row with
  label and appropriate input widget (Entry for text, Combobox for dropdown,
  DateEntry for dates).
- `build_results_table(self, columns)` — Creates a `ttk.Treeview` with the specified
  columns and scrollbars.
- `execute_search(self)` — Collects all filter values, builds the SQL WHERE clause,
  executes the query, and populates the results table.
- `export_results(self, format='csv')` — Exports the current result set.
- `save_search_template(self)` — Saves the current filter configuration as a named
  template in the `search_templates` table.
- `load_search_template(self, template_name)` — Restores a saved template's filter
  values.

**Dynamic query builder:**
```python
def build_search_query(self, filters):
    """Build parameterised query from filters dict"""
    base_query = '''
        SELECT s.student_id, s.first_name, s.last_name, s.course,
               s.email_address, s.registration_datetime, s.gpa,
               COUNT(g.id) as grade_count,
               AVG(g.score) as avg_score
        FROM students s
        LEFT JOIN grades g ON s.student_id = g.student_id
    '''
    conditions = []
    params = []

    if filters.get('name'):
        conditions.append(
            "(s.first_name LIKE ? OR s.last_name LIKE ? OR "
            "s.first_name || ' ' || s.last_name LIKE ?)")
        term = f"%{filters['name']}%"
        params.extend([term, term, term])

    if filters.get('course'):
        conditions.append("s.course = ?")
        params.append(filters['course'])

    if filters.get('gpa_min'):
        conditions.append("s.gpa >= ?")
        params.append(float(filters['gpa_min']))

    if filters.get('gpa_max'):
        conditions.append("s.gpa <= ?")
        params.append(float(filters['gpa_max']))

    if filters.get('registered_from'):
        conditions.append("s.registration_datetime >= ?")
        params.append(filters['registered_from'])

    if filters.get('registered_to'):
        conditions.append("s.registration_datetime <= ?")
        params.append(filters['registered_to'] + ' 23:59:59')

    if filters.get('module_code'):
        base_query += ' JOIN student_modules sm ON s.student_id = sm.student_id'
        conditions.append("sm.module_code = ?")
        params.append(filters['module_code'])

    if conditions:
        base_query += ' WHERE ' + ' AND '.join(conditions)

    base_query += ' GROUP BY s.student_id ORDER BY s.last_name, s.first_name'

    if filters.get('limit'):
        base_query += f" LIMIT {int(filters['limit'])}"

    return base_query, params
```

---

## Finance Reporting — Technical Reference


#### finance_reporting.py — `integrate_reporting_with_main_gui` fix (2025-06-26)

Error: `AttributeError: 'StudentManagementGUI' object has no attribute 'reporting_integration'`

Root cause: `integrate_reporting_with_main_gui()` was defined inside the
`StudentManagementGUI` class at an incorrect indentation level, making it a class method
rather than a module-level function. But `main.py` was importing it as:
```python
from enhanced_reporting import integrate_reporting_with_main_gui
```

Fix: The function was extracted from the class and defined at module level:
```python
def integrate_reporting_with_main_gui(main_gui_instance):
    """Integrate enhanced reporting with the main GUI - MODULE LEVEL FUNCTION"""
    try:
        if not hasattr(main_gui_instance, 'reporting_integration'):
            main_gui_instance.reporting_integration = EnhancedReportingIntegration(
                main_gui_instance, main_gui_instance.auth)
        return main_gui_instance.reporting_integration
    except Exception as e:
        logging.error(f"Failed to integrate reporting: {e}")
        return None
```

#### finance_reporting.py — display_advanced_finance_menu
Added as a module-level function (was missing, main.py expected it):
```python
def display_advanced_finance_menu(auth):
    """Display enhanced finance reporting menu"""
    try:
        root = tk.Toplevel() if tk._default_root else tk.Tk()
        app = FinanceReportingGUI(root, auth)
        if not tk._default_root:
            root.mainloop()
    except Exception as e:
        logging.error(f"Finance reporting GUI failed: {e}")
        _finance_reporting_cli_menu(auth)
```

#### finance_reporting.py — missing report functions added

**`generate_financial_forecasting(auth, periods=4)`:**
Uses GPA-based fee model: projects next `periods` terms' tuition fee revenue based on
current student count and average fees. Returns dict of period → projected revenue.

**`generate_budget_variance_report(auth, academic_year=None)`:**
Compares `budget_items.amount` against actual `expense_records.amount` for each budget
category. Returns variance per category (positive = under budget, negative = over budget).

**`financial_dashboard(auth)`:**
Opens a Toplevel window with 4 summary charts:
- Monthly revenue bar chart (last 12 months from `payments` table).
- Outstanding balances pie chart (by fee type).
- Scholarship distribution pie chart.
- Payment method breakdown bar chart.

---

## Module Scheduling — Technical Reference


### Entry point fix (v0.0.2)

`module_scheduling.py` had the main execution block at the wrong indentation:
```python
# Before (indented inside class body — never executed as __main__):
class ModuleScheduler:
    def __init__(self):
        ...
    if __name__ == '__main__':
        scheduler = ModuleScheduler()
        scheduler.display_menu()

# After (correct module-level placement):
class ModuleScheduler:
    def __init__(self):
        ...

if __name__ == '__main__':
    scheduler = ModuleScheduler()
    scheduler.display_menu()
```

### Integration with modules.py (v0.0.2)

`modules.py` defined module objects as named instances:
```python
compulsory_module_1 = Module('CS101', 'Introduction to Programming', 20, 30)
compulsory_module_2 = Module('CS102', 'Data Structures', 20, 30)
# etc.
```

`module_scheduling.py` was importing individual function names that didn't exist:
```python
# Before (broken):
from modules import get_all_modules, get_module_by_code, list_available_modules

# After (correct):
from modules import (
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2,
    optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2,
    CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2,
    DS_optional_module_3, DS_optional_module_4
)

ALL_MODULES = [
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2,
    optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2,
    CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2,
    DS_optional_module_3, DS_optional_module_4,
]

def get_all_modules():
    return ALL_MODULES

def get_module_by_code(code):
    return next((m for m in ALL_MODULES if m.code == code), None)
```

---

## DatabaseManager Class — Technical Reference (v0.0.9)


### `DatabaseManager` class — new (previously connection code was scattered)

```python
class DatabaseManager:
    """Centralised database connection and migration manager"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path=None):
        """Singleton pattern — only one instance per database path"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path=None):
        if self._initialized:
            return
        self.db_path = db_path or self._resolve_db_path()
        self.connections = {}  # thread_id → connection
        self._init_schema()
        self._run_migrations()
        self._initialized = True

    def _resolve_db_path(self):
        """Resolve database path relative to project root"""
        _this = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(_this)))
        db_dir = os.path.join(project_root, 'refactored', 'db_files')
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, 'student_records.db')

    def get_connection(self):
        """Get a thread-local connection"""
        thread_id = threading.get_ident()
        if thread_id not in self.connections:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA foreign_keys=ON')
            self.connections[thread_id] = conn
        return self.connections[thread_id]

    def execute(self, query, params=(), fetch='none'):
        """Execute a query with automatic connection management"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'all':
                return cursor.fetchall()
            elif fetch == 'lastrowid':
                conn.commit()
                return cursor.lastrowid
            else:
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            conn.rollback()
            logging.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
            raise

    def close_all(self):
        """Close all thread connections (called at shutdown)"""
        for conn in self.connections.values():
            try:
                conn.close()
            except Exception:
                pass
        self.connections.clear()
```

### graceful_import pattern (v0.0.9)

All library imports throughout the project standardised to:
```python
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
```

Anywhere these libraries are used:
```python
if PANDAS_AVAILABLE:
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
else:
    import csv
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
```

### MFA validation (v0.0.9)

```python
def validate_mfa_code(self, user_id, code):
    """Validate a TOTP MFA code"""
    try:
        import pyotp
        PYOTP_AVAILABLE = True
    except ImportError:
        PYOTP_AVAILABLE = False

    if not PYOTP_AVAILABLE:
        logging.warning("pyotp not available — MFA validation skipped")
        return True  # Graceful degradation

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT mfa_secret FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row['mfa_secret']:
        return False

    totp = pyotp.TOTP(row['mfa_secret'])
    # Valid within ±1 time window (30 seconds each)
    return totp.verify(code, valid_window=1)
```

---

## main.py — Attribute Error Fixes (2025-06-23)


Several class methods were accidentally defined outside the `StudentManagementGUI` class
due to wrong indentation. The class body ended at column 4 but the following method
definitions were also at column 4, making them module-level functions instead of methods.

This meant that when these "methods" tried to use `self`, they would receive the wrong
argument and fail with `AttributeError`.

Full list of methods that were re-indented back inside the class:
- `setup_authenticated_buttons(self)` — Sets up the sidebar buttons after login.
- `open_module_management(self)` — Opens the module management dialog.
- `open_grade_tracking(self)` — Opens grade tracking.
- `open_course_management(self)` — Opens course management.
- `open_academic_calendar(self)` — Opens academic calendar.
- `open_parent_portal(self)` — Opens parent portal.
- `open_helpdesk(self)` — Opens helpdesk.
- `open_internship_portal(self)` — Opens internship portal.
- `open_student_analytics(self)` — Opens student analytics dashboard.
- `open_batch_operations(self)` — Opens batch operations.
- `open_export_menu(self)` — Opens export menu.
- `open_ai_detector_gui(self)` — Opens AI detector.
- `open_advanced_search(self)` — Opens advanced search.
- `open_log_management(self)` — Opens log management.
- `update_button_states(self)` — Updates button enabled/disabled states.
- `on_login_success(self, user_data)` — Handles post-login state update.
- `on_logout(self)` — Handles logout and state reset.
- `run(self)` — Calls `self.root.mainloop()`.

All were moved from module level to inside `class StudentManagementGUI` by adding one
level of indentation (4 spaces).

---

## simple_activity_logger.py — Technical Reference


### Functions provided

All functions accept `(user_id, details='', metadata=None)` signature.

**`log_activity(user_id, action, details='', metadata=None)`**
Generic activity logger. Maps to `activity_logs` table.

**`log_create(user_id, entity_type, entity_id, details='')`**
Specialised for CREATE operations. Sets `action = f'CREATE_{entity_type.upper()}'`.

**`log_read(user_id, entity_type, entity_id, details='')`**
For READ/VIEW operations. Action: `VIEW_{entity_type.upper()}`.

**`log_update(user_id, entity_type, entity_id, old_data=None, new_data=None, details='')`**
For UPDATE operations. Stores diff between `old_data` and `new_data` as JSON in `metadata`.

**`log_delete(user_id, entity_type, entity_id, details='')`**
For DELETE operations. Action: `DELETE_{entity_type.upper()}`.

**`log_search(user_id, search_query, results_count, details='')`**
For search operations. Stores the search query terms.

**`log_export(user_id, export_type, record_count, file_path='')`**
For data export operations.

**`log_menu_navigation(user_id, from_menu, to_menu)`**
For menu navigation tracking.

**`log_dynamic_activity(user_id, action, **kwargs)`**
Flexible logger accepting arbitrary keyword arguments stored as JSON metadata.

### `activity_logs` table schema:
```sql
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details TEXT,
    metadata TEXT,
    ip_address TEXT,
    session_id TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    success INTEGER DEFAULT 1
)
```

### Index optimisations:
```sql
CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_action ON activity_logs(action);
CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON activity_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, entity_id);
```

---

## database_utils.py — Technical Reference


### `cleanup_database_connections()`
```python
def cleanup_database_connections():
    """Close all stale SQLite connections across all modules"""
    cleaned_count = 0
    # Close DatabaseManager singleton connections
    try:
        db = DatabaseManager()
        conn_count = len(db.connections)
        db.close_all()
        cleaned_count += conn_count
        logging.info(f"Closed {conn_count} DatabaseManager connections")
    except Exception as e:
        logging.warning(f"DatabaseManager cleanup failed: {e}")

    # Force garbage collection to close any lingering connections
    import gc
    gc.collect()

    logging.info(f"Database cleanup completed. {cleaned_count} connections closed.")
    return cleaned_count
```

### `validate_database_integrity(db_path=None)`
```python
def validate_database_integrity(db_path=None):
    """Run PRAGMA integrity_check and foreign_key_check"""
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    issues = []

    cursor.execute('PRAGMA integrity_check')
    result = cursor.fetchone()
    if result[0] != 'ok':
        issues.append(f"Integrity check failed: {result[0]}")

    cursor.execute('PRAGMA foreign_key_check')
    fk_violations = cursor.fetchall()
    for v in fk_violations:
        issues.append(f"FK violation: table={v[0]}, rowid={v[1]}, "
                      f"parent={v[2]}, fkid={v[3]}")

    conn.close()
    if issues:
        logging.warning(f"Database integrity issues found: {issues}")
        return False, issues
    logging.info("Database integrity check passed — no issues found")
    return True, []
```

### `backup_before_operation(operation_name, db_path=None)`
```python
def backup_before_operation(operation_name, db_path=None):
    """Create automatic backup before potentially destructive operations"""
    db_path = db_path or get_db_path()
    backup_dir = os.path.join(os.path.dirname(db_path), 'auto_backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_op_name = re.sub(r'[^a-zA-Z0-9_]', '_', operation_name)
    backup_name = f"pre_{safe_op_name}_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_name)

    shutil.copy2(db_path, backup_path)
    logging.info(f"Auto-backup created before {operation_name}: {backup_path}")

    # Keep only last 10 auto-backups
    backups = sorted(glob.glob(os.path.join(backup_dir, 'pre_*.db')))
    for old_backup in backups[:-10]:
        os.remove(old_backup)

    return backup_path
```

---

## Integration — Calendar System


### Academic Calendar auth integration (2025-06-09)

`CalendarAuthIntegration` class was not being initialised in `main.py`:
```python
# Added to init_auth_for_modules():
try:
    calendar_integration = CalendarAuthIntegration(auth)
    calendar_integration.setup()
    set_calendar_auth(auth)
    ensure_calendar_permissions()
    logging.info("Calendar auth integration configured")
except Exception as e:
    logging.warning(f"Calendar auth integration failed: {e}")
```

`ensure_calendar_permissions()` — creates calendar permissions if missing:
```python
def ensure_calendar_permissions():
    permissions_needed = [
        ('manage_calendar', 'Manage calendar events and settings'),
        ('view_calendar', 'View calendar events'),
        ('create_events', 'Create calendar events'),
        ('edit_own_events', 'Edit own calendar events'),
        ('delete_own_events', 'Delete own calendar events'),
        ('view_academic_calendar', 'View academic calendar'),
        ('manage_academic_calendar', 'Manage academic calendar entries'),
    ]
    conn = get_connection()
    cursor = conn.cursor()
    for name, desc in permissions_needed:
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description) VALUES (?, ?)',
            (name, desc))
    conn.commit()
    conn.close()
```

`setup_calendar_authentication(auth)` — sets auth context for calendar module-level
functions that were using a `global auth` variable that wasn't being set:
```python
_calendar_auth = None

def setup_calendar_authentication(auth_instance):
    global _calendar_auth
    _calendar_auth = auth_instance
    logging.info("Calendar authentication configured")

def set_auth(auth_instance):
    """Alias for setup_calendar_authentication for backwards compatibility"""
    setup_calendar_authentication(auth_instance)
```

### calendar_integration_fixed.py — SafeCalendarWindow

The original `CalendarWindow` from `academic_calendar.py` had a crash on certain
platforms when trying to set the window icon. A wrapper was created:

```python
class SafeCalendarWindow:
    """Safe wrapper around CalendarWindow that handles initialisation errors"""

    def __init__(self, parent, auth=None, on_close=None):
        self.parent = parent
        self.auth = auth
        self.on_close = on_close
        self._window = None
        self._create_window()

    def _create_window(self):
        try:
            from academic_calendar import AdvancedCalendarWindow
            self._window = AdvancedCalendarWindow(
                parent=self.parent,
                auth=self.auth
            )
        except Exception as e:
            logging.warning(f"Full calendar window failed: {e}. Using basic version.")
            self._create_basic_calendar()

    def _create_basic_calendar(self):
        """Fallback minimal calendar display"""
        top = tk.Toplevel(self.parent)
        top.title("Academic Calendar (Basic Mode)")
        top.geometry("600x400")
        ttk.Label(top, text="Academic Calendar",
                  font=('Arial', 16, 'bold')).pack(pady=20)
        ttk.Label(top, text="Full calendar unavailable. See calendar data below.",
                  foreground='orange').pack()
        # Show next 5 events in a simple tree
        tree = ttk.Treeview(top, columns=('date', 'title', 'type'), show='headings')
        tree.heading('date', text='Date')
        tree.heading('title', text='Event')
        tree.heading('type', text='Type')
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        self._load_basic_events(tree)
        self._window = top

    def _load_basic_events(self, tree):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT event_date, title, event_type
            FROM calendar_events
            WHERE event_date >= date('now')
            ORDER BY event_date
            LIMIT 20
        ''')
        for row in cursor.fetchall():
            tree.insert('', 'end', values=(row[0], row[1], row[2]))
        conn.close()
```

---

## Reporting Module — Integration Pattern Reference


### `create_default_report_templates()`
```python
def create_default_report_templates():
    """Create default report templates if none exist"""
    conn = get_connection()
    cursor = conn.cursor()

    templates = [
        ('student_overview', 'Student Overview Report',
         'Summary of all student records with GPA and enrollment status',
         'students', 'standard'),
        ('grade_distribution', 'Grade Distribution Report',
         'Distribution of grades across all modules', 'grades', 'chart'),
        ('attendance_summary', 'Attendance Summary Report',
         'Module-level attendance rates', 'attendance', 'standard'),
        ('financial_overview', 'Financial Overview Report',
         'Fee collection and outstanding balance summary', 'finance', 'standard'),
        ('at_risk_students', 'At-Risk Students Report',
         'Students with GPA below 2.0 or attendance below 75%',
         'students', 'alert'),
    ]

    for template_id, name, desc, category, report_type in templates:
        cursor.execute('''
            INSERT OR IGNORE INTO report_templates
            (template_id, name, description, category, report_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (template_id, name, desc, category, report_type,
              datetime.now().strftime('%Y-%m-%d')))

    conn.commit()
    conn.close()
    logging.info("Default report templates created/verified")
```

### `verify_reporting_integration(main_gui)`
```python
def verify_reporting_integration(main_gui):
    """Verify that the reporting system is properly integrated"""
    checks = {
        'auth_available': main_gui.auth is not None,
        'auth_logged_in': main_gui.auth.current_user is not None if main_gui.auth else False,
        'reporting_attr': hasattr(main_gui, 'reporting_integration'),
        'templates_exist': False,
        'db_accessible': False
    }

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM report_templates')
        count = cursor.fetchone()[0]
        checks['templates_exist'] = count > 0
        checks['db_accessible'] = True
        conn.close()
    except Exception as e:
        logging.warning(f"Reporting DB check failed: {e}")

    all_pass = all(checks.values())
    if not all_pass:
        failed = [k for k, v in checks.items() if not v]
        logging.warning(f"Reporting integration check failed: {failed}")
    return all_pass, checks
```

---

## System-Wide Error Handling Patterns


### `@handle_exception` decorator
Used throughout the project to prevent unhandled exceptions from crashing the system:
```python
def handle_exception(func):
    """Decorator for consistent exception handling and logging"""
    import functools
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            logging.error(f"Database operation failed in {func.__name__}: {e}")
            if 'no such table' in str(e).lower():
                logging.error("Missing table detected — running migration...")
                try:
                    run_schema_migration()
                    return func(*args, **kwargs)  # Retry after migration
                except Exception as retry_e:
                    logging.error(f"Retry failed: {retry_e}")
            return None
        except sqlite3.IntegrityError as e:
            logging.error(f"Integrity constraint failed in {func.__name__}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}")
            logging.error(traceback.format_exc())
            return None
    return wrapper
```

### Tkinter widget destruction safety pattern
GUI code that closes child windows without destroying parent:
```python
def safe_destroy(widget):
    """Safely destroy a Tkinter widget, ignoring errors if already destroyed"""
    try:
        if widget and widget.winfo_exists():
            widget.destroy()
    except tk.TclError:
        pass  # Widget already destroyed
    except Exception as e:
        logging.warning(f"Widget destruction error (non-fatal): {e}")
```

All Toplevel window close handlers use:
```python
self.root.protocol("WM_DELETE_WINDOW", lambda: safe_destroy(self.root))
```

### Thread-safe GUI update pattern
All database operations in GUI run in threads; updates posted back via `root.after()`:
```python
def load_data_async(self):
    """Load data in background thread, update GUI on main thread"""
    def background_task():
        try:
            data = self.fetch_data_from_db()
            # Post result to main thread
            self.root.after(0, self.update_display, data)
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, self.show_error, error_msg)

    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()

def update_display(self, data):
    """Called on main thread to update the Treeview"""
    # Clear existing rows
    for item in self.tree.get_children():
        self.tree.delete(item)
    # Insert new data
    for row in data:
        self.tree.insert('', 'end', values=tuple(row))

def show_error(self, error_msg):
    """Called on main thread to show an error dialog"""
    messagebox.showerror("Error", error_msg)
```

---

## alumni_management.py — 20+ New Tables Reference (v0.0.1)


Full list of tables added in the initial enhancement:

| Table | Purpose |
|---|---|
| `alumni_events` | Events organised for alumni |
| `alumni_event_registrations` | RSVP and attendance tracking |
| `alumni_mentorship` | Mentorship program pairings |
| `alumni_stories` | Success stories and testimonials |
| `photo_gallery` | Alumni photo and video gallery |
| `networking_connections` | LinkedIn-style connection graph |
| `business_directory` | Alumni-owned businesses |
| `fundraising_campaigns` | Fundraising campaigns metadata |
| `donor_recognition` | Donation records and recognition tiers |
| `alumni_achievements` | Awards and milestones |
| `class_reunions` | Reunion events by graduation year |
| `career_counseling` | Career guidance session bookings |
| `system_integrations` | External system integration config |
| `regional_chapters` | Geographic alumni chapter data |
| `alumni_points` | Points balance per alumni member |
| `alumni_badges` | Badge definitions |
| `alumni_badge_awards` | Badge award records per member |
| `mentorship_programs` | Mentorship program definitions |
| `mentorship_matches` | Mentor-mentee pairing records |
| `job_postings` | Alumni-posted job opportunities |
| `job_applications` | Applications for alumni job postings |
| `event_check_ins` | In-person event check-in records |
| `waitlist` | Event waitlist management |

---

## library.py — 15+ New Tables Reference (v0.0.3)


Full list of tables added in the library enhancement:

| Table | Purpose |
|---|---|
| `reading_lists` | Named reading lists created by users |
| `reading_list_items` | Books within reading lists |
| `book_reviews` | Student-written reviews and ratings |
| `book_tags` | Tagging system for books |
| `book_recommendations` | System-generated book recommendations |
| `digital_resources` | E-books, databases, online journals |
| `resource_access_log` | Log of digital resource accesses |
| `reading_challenges` | Reading challenges and participation |
| `inter_library_loans` | ILL requests and tracking |
| `library_announcements` | Library news and announcements |
| `subject_guides` | Curated resource lists by subject |
| `book_clubs` | Book club registration and meetings |
| `notification_preferences` | Per-user notification settings |
| `overdue_notifications` | Log of overdue reminder notifications |
| `fine_payment_records` | Fine payment history |

---

*End of Extended Module Reference*

---

## CHANGE LOG — MINOR FIXES AND MAINTENANCE


The following lists minor fixes applied across the project that do not warrant a
full version entry but are recorded for completeness.

### Typo and variable name fixes

- `accomodation` → `accommodation` in 14 variable names across `accommodation.py`.
- `stuednt_id` → `student_id` in 3 places in `grade_tracking.py`.
- `resturant` → `restaurant` in 8 places in `restaurant_management.py`.
- `libary` → `library` in 2 import aliases in `main.py`.
- `permision` → `permission` in `user_authentication.py` at lines 445, 449, 463.
- `authenication` → `authentication` in docstring of `setup_calendar_authentication`.

### String formatting fixes

- `f"Student {student.name}"` → `f"Student {student['first_name']} {student['last_name']}"` 
  in 7 places where `students` was an `sqlite3.Row`, not a class with `.name` attribute.
- `f"Error: {error}"` → `f"Error: {str(error)}"` in 23 exception handlers where `error`
  could be a non-string exception type.

### Missing `conn.close()` fixes

- `library.py` — `checkout_book()`: connection not closed on error path.
- `parking_management.py` — `generate_permit_report()`: connection not closed after
  result set iteration.
- `restaurant_management.py` — `view_order_history()`: connection not closed if an
  empty result was returned early.
- `email_manager.py` — `get_inbox()`: connection left open when recipient had zero messages.
- `finance.py` — `get_student_financial_summary()`: connection not closed on exception.

All fixed by wrapping database operations in `try/finally` with `conn.close()` in the
`finally` block, or using the `DatabaseManager.execute()` context manager.

### SQL injection prevention

The following queries were identified as using string formatting and converted to
parameterised queries:

- `accommodation.py`: `f"SELECT * FROM accommodations WHERE student_id = '{student_id}'"` →
  `'SELECT * FROM accommodations WHERE student_id = ?', (student_id,)`
- `restaurant_management.py`: `f"SELECT * FROM restaurant_customers WHERE name LIKE '%{name}%'"` →
  `'SELECT * FROM restaurant_customers WHERE name LIKE ?', (f'%{name}%',)`
- `library.py`: `f"SELECT * FROM books WHERE isbn = '{isbn}'"` →
  `'SELECT * FROM books WHERE isbn = ?', (isbn,)`
- `student_support.py`: `f"UPDATE support_tickets SET status = '{status}' WHERE id = {ticket_id}"` →
  `'UPDATE support_tickets SET status = ? WHERE id = ?', (status, ticket_id)`

### Unicode and encoding fixes

- All `open()` calls updated to `open(..., encoding='utf-8')` to prevent
  `UnicodeDecodeError` on Windows systems.
- CSV exports updated: `csv.writer(f)` → `csv.writer(f, encoding='utf-8-sig')` to
  ensure Excel can open exported files without garbling accented characters.

### Deprecated API fixes

- `datetime.utcnow()` → `datetime.now(timezone.utc)` in 8 places
  (`datetime.utcnow()` is deprecated since Python 3.12).
- `sqlite3.connect(db_path, isolation_level=None)` → `sqlite3.connect(db_path)` with
  explicit `conn.commit()` calls. `isolation_level=None` (autocommit) was causing issues
  with multi-step transactions.

---

*End of Minor Fixes and Maintenance Section*

---

## SUMMARY STATISTICS


| Category | Count |
|---|---|
| Total versions documented | 45+ |
| Python source files covered | 85+ |
| Database tables documented | 210+ |
| Permissions defined | 120+ |
| Bug fixes documented | 180+ |
| New features added | 95+ |
| New GUI classes created | 22 |
| New dialog classes created | 35+ |
| Integration fixes | 40+ |
| SQL injection fixes | 12 |
| Missing function implementations | 65+ |

### Development timeline

| Period | Focus |
|---|---|
| June 2025 | Initial integrations, import error fixes, database consolidation |
| July 2025 | Feature enhancements, library/alumni expansions, analytics |
| August 2025 | GUI conversions for all major modules |
| September 2025 | System testing, data management tools, document management |
| October 2025 — January 2026 | AcademicAffairs, new module integrations, consolidation |
| January 2026 | Documentation consolidation (53 files → 2 files) |
| February — March 2026 | Final bug fixes, changelog expansion |

---

*End of CHANGELOG*
*University Student Management System*
*Full development history: June 2025 — March 2026*
*Total documentation: ~10,000 lines*

---

## COMPLETE FUNCTION SIGNATURE REFERENCE


The following section provides a complete alphabetical listing of all significant
functions and methods across the project, with their signatures, return types, and
module locations. This is intended as a quick-reference API index.

---

### A

**`academic_calendar.py`**
- `AcademicCalendarManager.__init__(self, db_path=None)` → None
- `AcademicCalendarManager.add_event(self, title, event_type, start_date, end_date=None, description='', location='', is_recurring=False)` → str (event_id)
- `AcademicCalendarManager.update_event(self, event_id, **kwargs)` → bool
- `AcademicCalendarManager.delete_event(self, event_id)` → bool
- `AcademicCalendarManager.get_events_in_range(self, start_date, end_date)` → List[dict]
- `AcademicCalendarManager.get_upcoming_events(self, days=30, limit=10)` → List[dict]
- `AcademicCalendarManager.get_events_by_type(self, event_type)` → List[dict]
- `CalendarApp.__init__(self, root, auth=None)` → None
- `CalendarApp.create_widgets(self)` → None
- `CalendarApp.load_month(self, year, month)` → None
- `CalendarApp.show_event_details(self, event_id)` → None
- `CalendarApp.add_event_dialog(self)` → None
- `CalendarApp.export_to_ics(self, output_path)` → bool
- `CalendarAuthIntegration.__init__(self, auth)` → None
- `CalendarAuthIntegration.setup(self)` → bool
- `create_calendar_app_with_auth(root, auth)` → CalendarApp
- `display_academic_calendar_menu(auth)` → None
- `ensure_calendar_permissions()` → None
- `set_auth(auth_instance)` → None
- `setup_calendar_authentication(auth_instance)` → None

**`accommodation.py`**
- `set_auth(auth_instance)` → None
- `init_accommodation_db()` → bool
- `migrate_audit_log_schema()` → None
- `fix_accommodation_db_schema()` → None
- `create_accommodation_request(student_id, accommodation_type, reason, supporting_docs=None)` → str
- `view_accommodation_request(request_id)` → dict
- `approve_accommodation_request(request_id, approved_by, notes='')` → bool
- `reject_accommodation_request(request_id, rejected_by, reason)` → bool
- `list_accommodation_requests(status=None, student_id=None)` → List[dict]
- `generate_accommodation_report()` → dict
- `log_accommodation_action(action, request_id, user_id, details='')` → None

**`AcademicAffairs.py`**
- `AcademicAffairsManager.__init__(self, db_path=None)` → None
- `AcademicAffairsManager._create_tables(self)` → None
- `AcademicAffairsManager.add_transfer_credits(self, student_id, source_institution, module_code, credits, grade, notes='')` → str
- `AcademicAffairsManager.view_transfer_credits(self, student_id=None)` → List[dict]
- `AcademicAffairsManager.approve_transfer_credits(self, record_id, approved_by)` → bool
- `AcademicAffairsManager.reject_transfer_credits(self, record_id, rejected_by, reason)` → bool
- `AcademicAffairsManager.add_committee(self, name, description)` → str
- `AcademicAffairsManager.add_committee_member(self, committee_id, member_name, role='member')` → str
- `AcademicAffairsManager.schedule_meeting(self, committee_id, date, time, location, agenda)` → str
- `AcademicAffairsManager.record_meeting_minutes(self, meeting_id, minutes_text, recorded_by)` → str
- `AcademicAffairsManager.create_portfolio(self, student_id, title, description)` → str
- `AcademicAffairsManager.add_portfolio_artifact(self, portfolio_id, title, description, file_path, artifact_type)` → str
- `AcademicAffairsManager.get_student_portfolio(self, student_id)` → dict
- `display_academic_affairs_menu(manager, auth)` → None

**`advanced_search.py`**
- `AdvancedSearchGUI.__init__(self, parent, auth)` → None
- `AdvancedSearchGUI.build_filter_row(self, label, filter_key, filter_type)` → tk.Frame
- `AdvancedSearchGUI.build_results_table(self, columns)` → ttk.Treeview
- `AdvancedSearchGUI.execute_search(self)` → None
- `AdvancedSearchGUI.export_results(self, format='csv')` → bool
- `AdvancedSearchGUI.save_search_template(self)` → None
- `AdvancedSearchGUI.load_search_template(self, template_name)` → None
- `AdvancedSearchGUI.build_search_query(self, filters)` → Tuple[str, list]
- `display_advanced_search_menu(auth)` → None
- `integrate_advanced_search_with_main()` → bool
- `open_advanced_search_gui(auth, parent=None)` → AdvancedSearchGUI
- `add_advanced_search_menu_item(menu_widget, auth)` → None
- `create_advanced_search_button(parent, auth)` → ttk.Button

**`ai_detector.py`**
- `AIDetector.__init__(self)` → None
- `AIDetector._init_db(self)` → None
- `AIDetector.set_auth(self, auth_instance)` → None
- `AIDetector.analyze_text(self, text)` → dict
- `AIDetector.calculate_perplexity(self, text)` → float
- `AIDetector.check_sentence_patterns(self, text)` → dict
- `AIDetector.generate_report(self, analysis_result)` → str
- `AIDetector.get_statistics(self)` → dict
- `AIDetector._offline_detection_fallback(self, text)` → dict
- `AIDetector._compute_perplexity(self, text)` → float
- `AIDetector.format_report(self, analysis_result)` → str
- `AIDetector.save_analysis(self, text, result, file_path)` → bool
- `create_minimal_ai_detector()` → AIDetector
- `integrate_ai_detector_with_main()` → bool

**`alumni_management.py`**
- `init_alumni_db()` → bool
- `setup_alumni_permissions()` → None
- `set_auth(auth_instance)` → None
- `display_alumni_menu(auth)` → None
- `AlumniSystemGUI.__init__(self, root, auth=None)` → None
- `AlumniSystemGUI.create_tabs(self)` → None
- `AlumniSystemGUI.load_alumni_list(self)` → None
- `AlumniSystemGUI.add_alumni_dialog(self)` → None
- `AlumniSystemGUI.view_alumni_profile(self, alumni_id)` → None
- `AlumniSystemGUI.send_newsletter(self, recipient_filter)` → bool
- `AlumniSystemGUI.generate_alumni_report(self, report_type)` → None
- `add_alumni(student_id, graduation_year, degree, major, current_employer='', current_role='', email='', linkedin_url='')` → str
- `update_alumni(alumni_id, **kwargs)` → bool
- `search_alumni(query, filters=None)` → List[dict]
- `create_alumni_event(title, date, location, description, capacity=None)` → str
- `register_for_alumni_event(alumni_id, event_id)` → bool
- `record_donation(alumni_id, amount, campaign_id=None, payment_method='')` → str
- `award_alumni_badge(alumni_id, badge_name)` → bool
- `get_alumni_points(alumni_id)` → int
- `add_alumni_points(alumni_id, points, reason)` → bool

**`assignment_submission.py`**
- `AssignmentSubmission.__init__(self, auth=None)` → None
- `AssignmentSubmission.init_db(self)` → bool
- `AssignmentSubmission.create_assignment(self, module_code, name, description, due_date, max_points, allowed_formats, max_file_size_mb)` → str
- `AssignmentSubmission.get_assignments_for_student(self, student_id)` → List[dict]
- `AssignmentSubmission.get_all_assignments(self, filters=None)` → List[dict]
- `AssignmentSubmission.submit_assignment(self, assignment_id, student_id, file_path)` → dict
- `AssignmentSubmission.grade_submission(self, submission_id, grade, feedback)` → bool
- `AssignmentSubmission.get_submissions_for_assignment(self, assignment_id)` → List[dict]
- `AssignmentSubmission.check_late_submission(self, assignment_id)` → bool
- `init_assignment_system()` → bool
- `add_assignment_permissions()` → List[str]
- `display_assignment_menu(auth)` → None
- `display_assignment_menu_gui(auth)` → None

**`attendance_tracker.py`**
- `AttendanceTrackerGUI.__init__(self, root, auth=None)` → None
- `init_attendance_db()` → bool
- `set_auth(auth_instance)` → None
- `setup_attendance_permissions()` → None
- `display_attendance_menu(auth)` → None
- `create_attendance_session(module_code, session_date, session_type, location='')` → str
- `record_attendance(session_id, student_id, status, notes='', check_in_method='manual')` → bool
- `get_student_attendance_summary(student_id, module_code=None)` → dict
- `get_module_attendance_stats(module_code)` → dict
- `get_at_risk_students(threshold=0.75)` → List[dict]
- `generate_attendance_report(filters=None, output_path=None)` → bool
- `generate_qr_token(session_id)` → str
- `validate_qr_checkin(session_id, token, student_id)` → bool
- `start_gui()` → None
- `start_cli()` → None

---

### B

**`batch_operations.py`**
- `display_batch_menu(auth)` → None
- `find_duplicate_students()` → List[dict]
- `merge_duplicate_students(primary_id, duplicate_id, confirm=False)` → bool
- `validate_and_clean_data()` → dict
- `data_quality_dashboard()` → None
- `export_students_to_file(format='csv', filter_criteria=None, output_path=None)` → bool
- `export_enrollment_statistics(output_path=None)` → bool
- `generate_import_template(import_type, format='csv', output_path=None)` → str
- `import_history()` → List[dict]
- `create_database_backup()` → str
- `bulk_enroll_students(csv_path)` → dict
- `bulk_update_grades(csv_path)` → dict
- `bulk_send_notifications(template_id, filter_criteria)` → int
- `archive_graduated_students(graduation_year)` → int

---

### C

**`course_management.py`**
- `display_course_management_menu(auth)` → None
- `add_course(name, code, department, credits, description='', prerequisites=None)` → str
- `update_course(course_id, **kwargs)` → bool
- `delete_course(course_id)` → bool
- `get_all_courses(active_only=True)` → List[dict]
- `get_course_by_code(code)` → dict
- `enroll_student_in_module(student_id, module_code, academic_year)` → bool
- `unenroll_student(student_id, module_code)` → bool
- `get_module_enrollment(module_code)` → List[dict]
- `get_student_modules(student_id)` → List[dict]
- `add_grade_for_student(student_id, module_code, assessment_id, score, submitted_date, feedback='')` → bool
- `calculate_student_gpa(student_id)` → float
- `generate_course_report(module_code)` → dict

---

### D

**`data_backup.py`**
- `display_backup_menu(auth)` → None
- `create_backup(backup_dir=None, backup_type='full')` → str
- `restore_from_backup(backup_path)` → bool
- `restore_partial_tables(backup_path, table_names)` → bool
- `create_differential_backup(last_full_backup_path)` → str
- `generate_backup_statistics()` → dict
- `view_backup_history()` → None
- `start_backup_scheduler()` → None
- `stop_backup_scheduler()` → None
- `test_scheduler()` → bool
- `export_backup_schedule_template(filepath)` → bool
- `import_backup_schedule_template(filepath)` → bool
- `backup_before_operation(operation_name, db_path=None)` → str

**`database_utils.py`**
- `get_db_path()` → str
- `get_connection()` → sqlite3.Connection
- `cleanup_database_connections()` → int
- `validate_database_integrity(db_path=None)` → Tuple[bool, List[str]]
- `backup_before_operation(operation_name, db_path=None)` → str
- `run_schema_migration()` → None
- `DatabaseManager.__new__(cls, db_path=None)` → DatabaseManager
- `DatabaseManager.__init__(self, db_path=None)` → None
- `DatabaseManager.get_connection(self)` → sqlite3.Connection
- `DatabaseManager.execute(self, query, params=(), fetch='none')` → Any
- `DatabaseManager.close_all(self)` → None

**`document_manager.py`**
- `display_document_management_menu(auth)` → None
- `store_document(student_id, document_type, file_path, issue_date=None, expiry_date=None, notes='')` → str
- `retrieve_document(doc_id, requesting_user_id)` → dict
- `update_document_status(doc_id, new_status, notes='')` → bool
- `check_document_expiry()` → List[dict]
- `view_document_details(doc_id)` → dict
- `search_documents(query, search_fields=None)` → List[dict]
- `get_document_statistics()` → dict
- `archive_document(doc_id, reason)` → bool
- `restore_document(doc_id)` → bool
- `remove_orphaned_files()` → int
- `bulk_document_download(doc_ids, output_dir)` → Tuple[int, List[str]]
- `bulk_notification_send(student_ids, notification_type, message)` → int
- `bulk_tag_assignment(doc_ids, tags)` → None
- `bulk_expiry_update(doc_ids, new_expiry_date)` → None
- `generate_status_report(filters=None)` → dict
- `generate_expiry_report(days_ahead=30)` → List[dict]
- `generate_student_progress_report(student_id)` → dict
- `generate_department_analysis()` → List[dict]
- `generate_monthly_summary(year, month)` → dict
- `import_from_excel(filepath)` → Tuple[int, List[str]]
- `export_all_documents(output_path, format='csv')` → bool
- `export_compliance_data(output_path)` → bool
- `export_activity_log(output_path, date_from=None, date_to=None)` → bool
- `download_import_template()` → str
- `batch_ocr_processing(doc_ids)` → dict
- `archive_old_versions(doc_id, keep_latest=1)` → int
- `version_analytics()` → dict
- `document_type_management()` → None
- `notification_templates()` → None
- `bulk_notification_campaign(template_id, recipient_filter)` → int
- `schedule_automatic_backup(interval_hours, backup_dir)` → None
- `view_backup_history()` → None

---

### E

**`email_manager.py`**
- `CommunicationDashboard.__init__(self, auth=None)` → None
- `CommunicationDashboard._init_communication_tables(self)` → None
- `CommunicationDashboard.send_message(self, sender_id, recipient_id, subject, body, attachment_path=None)` → bool
- `CommunicationDashboard.get_inbox(self, user_id, include_archived=False)` → List[dict]
- `CommunicationDashboard.get_sent_messages(self, user_id)` → List[dict]
- `CommunicationDashboard.reply_to_message(self, original_msg_id, sender_id, body)` → bool
- `CommunicationDashboard.mark_as_read(self, message_id, user_id)` → bool
- `CommunicationDashboard.archive_message(self, message_id, user_id)` → bool
- `CommunicationDashboard.delete_message(self, message_id, user_id, by_sender=False)` → bool
- `CommunicationDashboard.send_announcement(self, sender_id, title, content, target_audience, priority='normal')` → str
- `CommunicationDashboard.get_announcements(self, user_id, role)` → List[dict]
- `CommunicationDashboard.create_chat_room(self, name, created_by, room_type='group')` → str
- `CommunicationDashboard.send_chat_message(self, room_id, sender_id, content)` → bool
- `CommunicationDashboard.get_chat_messages(self, room_id, limit=50, before_id=None)` → List[dict]
- `send_message(sender_id, recipient_id, subject, body, attachment_path=None, auth=None)` → bool
- `send_email(recipient_email, subject, body, html_body=None, attachments=None)` → bool
- `send_registration_confirmation(student_data, auth=None)` → bool
- `send_update_confirmation(student_data, changes, auth=None)` → bool
- `send_appointment_confirmation(appointment_data, auth=None)` → bool
- `send_health_notification(student_id, notification_type, content, auth=None)` → bool
- `get_student_info(student_id)` → dict
- `load_email_template(template_name)` → dict
- `set_communication_auth(auth_instance)` → None
- `log_event(level, message)` → None

---

### F

**`finance.py`**
- `FinanceGUI.__init__(self, root, auth=None)` → None
- `FinanceGUI.create_tabs(self)` → None
- `FinanceGUI.search_students(self, query)` → List[dict]
- `FinanceGUI.get_student_financial_summary(self, student_id)` → dict
- `init_enhanced_finance_db()` → bool
- `set_finance_auth(auth_instance)` → None
- `add_finance_permissions()` → List[str]
- `display_enhanced_finance_menu(auth)` → None
- `create_integrated_finance_gui(root, auth)` → FinanceGUI
- `assign_fees_to_student(student_id, fee_type, amount, due_date, academic_year, description='')` → str
- `record_payment(student_id, fee_id, amount, payment_method, reference='', notes='')` → str
- `view_student_financial_statement(student_id)` → dict
- `generate_invoice(student_id, include_paid=False)` → str
- `manage_scholarships(auth)` → None
- `generate_financial_reports(auth, report_type='all')` → None
- `fix_database_schema()` → None

**`finance_reporting.py`**
- `display_advanced_finance_menu(auth)` → None
- `FinanceReportingGUI.__init__(self, root, auth=None)` → None
- `generate_financial_forecasting(auth, periods=4)` → dict
- `generate_budget_variance_report(auth, academic_year=None)` → List[dict]
- `financial_dashboard(auth)` → None
- `integrate_reporting_with_main_gui(main_gui_instance)` → Any
- `verify_reporting_integration(main_gui)` → Tuple[bool, dict]
- `create_default_report_templates()` → None
- `initialize_reporting_integration(auth)` → bool

---

### G

**`grade_tracking.py` / `grade_tracking_gui.py`**
- `display_enhanced_grade_menu(auth)` → None
- `GradeTrackingGUI.__init__(self, root, auth=None)` → None
- `GradeTrackingGUI.create_tabs(self)` → None
- `GradeTrackingGUI.load_grades(self, filters=None)` → None
- `GradeTrackingGUI.edit_selected_grade(self)` → None
- `GradeTrackingGUI.add_grade_dialog(self)` → None
- `GradeTrackingGUI.delete_grade(self)` → None
- `GradeTrackingGUI.generate_report(self)` → None
- `GradeDialog.__init__(self, parent, title, cursor)` → None
- `GradeDialog._update_max_points(self, event=None)` → None
- `GradeDialog._update_grade_preview(self, event=None)` → None
- `GradeDialog._save(self)` → None
- `RiskAssessmentDialog.__init__(self, parent, auth)` → None
- `RiskAssessmentDialog.load_at_risk_students(self)` → None
- `RiskAssessmentDialog.generate_intervention(self)` → None
- `PredictiveAnalyticsDialog.__init__(self, parent, auth)` → None
- `PredictiveAnalyticsDialog.run_predictions(self)` → None
- `PredictiveAnalyticsDialog.export_predictions(self)` → None
- `ModulePerformanceDialog.__init__(self, parent, auth)` → None
- `AssessmentAnalysisDialog.__init__(self, parent, auth)` → None
- `GradeDistributionDialog.__init__(self, parent, auth)` → None
- `TrendAnalysisDialog.__init__(self, parent, auth)` → None
- `record_grade(student_id, assessment_id, score, submitted_date, feedback='', late_penalty=0.0)` → str
- `get_student_grades(student_id, module_code=None)` → List[dict]
- `calculate_module_gpa(student_id, module_code)` → float
- `calculate_overall_gpa(student_id)` → float
- `get_grade_distribution(module_code=None)` → dict
- `export_module_performance(output_path)` → bool
- `analyze_by_assessment_type()` → List[dict]
- `analyze_all_assessments()` → List[dict]
- `analyze_distribution_by_course()` → dict
- `analyze_overall_distribution()` → dict
- `analyze_course_performance_trends(course_name, periods=4)` → List[tuple]
- `analyze_seasonal_trends()` → dict
- `forecast_course_performance(course_name, periods_ahead=2)` → List[float]
- `forecast_success_rates(cohort_filter)` → float
- `calculate_all_students_success_probability()` → dict
- `batch_grade_predictions()` → dict
- `build_at_risk_prediction_model()` → dict
- `analyze_dropout_risk_factors()` → List[tuple]
- `generate_dropout_interventions(student_id)` → List[str]
- `create_progress_visualization(student_id)` → str
- `create_dashboard_visualizations()` → None
- `generate_dashboard_report(output_path)` → bool
- `perform_statistical_test(group1_grades, group2_grades, test_type='t-test')` → dict
- `validate_grade_data_integrity()` → List[str]
- `percentage_to_letter(percentage)` → str
- `letter_to_gpa(letter)` → float

---

### H

**`health_portal.py`**
- `display_health_portal_menu(auth=None, parent=None)` → None
- `init_health_portal_db()` → bool
- `setup_health_permissions_integration()` → None
- `check_vaccination_expiry()` → List[dict]
- `send_overdue_vaccination_alerts()` → int
- `check_drug_interactions(medication_list)` → List[dict]
- `check_allergies_before_prescribing(student_id, medication)` → List[dict]
- `calculate_health_risk_score(student_id)` → Tuple[float, str]
- `get_vaccination_coverage_rate(vaccine_name=None)` → dict
- `get_common_conditions_report()` → List[dict]
- `get_appointment_utilisation_stats(period='month')` → dict
- `get_health_trend_analysis(metric, months=12)` → List[tuple]
- `get_provider_workload_stats()` → List[dict]
- `generate_custom_health_report(filters, fields, output_format='csv')` → Any
- `create_prescription(student_id, medication, dosage, frequency, duration_days)` → str
- `track_medication_adherence(student_id)` → dict
- `record_vital_signs(student_id, provider_id, readings)` → str
- `get_vital_signs_trend(student_id, metric, periods=6)` → List[tuple]
- `check_critical_vital_values(readings)` → List[dict]
- `create_care_plan(student_id, condition, goals, interventions, review_date)` → str
- `update_care_plan_progress(plan_id, goal_id, progress_notes, status)` → bool
- `record_communicable_disease_case(student_id, disease_name, onset_date, notification_required)` → str
- `run_outbreak_detection()` → List[dict]
- `contact_tracing(case_id)` → List[dict]
- `encrypt_field(value, key)` → str
- `decrypt_field(value, key)` → str
- `log_health_audit(action, record_id, user_id, old_value=None, new_value=None)` → None
- `apply_retention_policy()` → None

**`helpdesk.py`**
- `display_helpdesk_menu(auth)` → None
- `init_helpdesk_db()` → bool
- `create_ticket(user_id, subject, description, category, priority='medium', attachment_path=None)` → str
- `add_ticket_response(ticket_id, responder_id, response_text, is_public=True)` → str
- `update_ticket_status(ticket_id, new_status, updated_by)` → bool
- `escalate_ticket(ticket_id, escalated_to, reason)` → bool
- `close_ticket(ticket_id, closed_by, resolution_notes='')` → bool
- `get_all_tickets(filters=None, page=1, per_page=20)` → Tuple[List[dict], int]
- `get_tickets_for_user(user_id)` → List[dict]
- `get_ticket_detail(ticket_id)` → dict
- `search_knowledge_base(query)` → List[dict]
- `create_kb_article(title, content, category_id, created_by)` → str
- `calculate_sla_due_date(priority, created_at)` → str
- `view_all_tickets_enhanced(support, auth, page=1, per_page=20)` → None

**`housing_accommodation.py`**
- `display_housing_accommodation_menu(auth)` → None
- `init_housing_db()` → bool
- `set_auth(auth_instance)` → None
- `HousingGUI.__init__(self, auth_instance=None)` → None
- `HousingGUI.create_main_interface(self)` → None
- `HousingGUI.on_close(self)` → None
- `create_building(name, address, total_floors, amenities='')` → str
- `view_building(building_id)` → dict
- `update_building(building_id, **kwargs)` → bool
- `delete_building(building_id)` → bool
- `create_application(student_id, room_type_preference, move_in_date, notes='')` → str
- `process_application(application_id, approved_by, room_id=None)` → bool
- `view_application(application_id)` → dict
- `view_assignment(student_id)` → dict
- `update_assignment_status(assignment_id, new_status)` → bool
- `create_maintenance_request(student_id, room_id, issue_type, description)` → str
- `view_maintenance_requests(status=None, room_id=None)` → List[dict]
- `update_maintenance_request(request_id, status, notes='')` → bool
- `record_payment(student_id, amount, payment_type, reference='')` → str
- `view_payment_history(student_id)` → List[dict]
- `manage_inventory(building_id)` → None
- `create_inspection(room_id, inspector_id, inspection_date, notes='')` → str
- `view_inspections(room_id=None, building_id=None)` → List[dict]
- `generate_occupancy_report()` → dict
- `generate_financial_report(date_from=None, date_to=None)` → dict
- `export_housing_data(format='csv', output_path=None)` → bool
- `search_housing_records(query, record_type='all')` → List[dict]
- `check_room_availability(room_type=None, building_id=None)` → List[dict]
- `maintenance_summary()` → dict
- `upcoming_moveouts_report(days_ahead=30)` → List[dict]

---

### I

**`internship_management.py`**
- `display_internship_menu(auth)` → None
- `init_internship_db()` → bool
- `setup_internship_permissions()` → None
- `set_auth(auth_instance)` → None
- `migrate_internship_schema()` → None
- `create_internship_listing(company_id, title, description, requirements, duration_weeks, start_date, deadline, remote_option=False)` → str
- `apply_for_internship(student_id, listing_id, cover_letter='', cv_path=None)` → str
- `review_application(application_id, reviewer_id, decision, feedback='')` → bool
- `get_internship_listings(active_only=True, filters=None)` → List[dict]
- `get_applications_for_student(student_id)` → List[dict]
- `get_applications_for_listing(listing_id)` → List[dict]
- `create_company(company_name, industry, website='', contact_email='', contact_name='', location='')` → str
- `get_companies()` → List[dict]
- `record_placement(student_id, listing_id, start_date, end_date, supervisor='')` → str
- `record_internship_feedback(placement_id, student_rating, supervisor_rating, feedback_text='')` → bool

---

### L

**`library.py`**
- `init_library_db()` → bool
- `init_enhanced_library_db()` → bool
- `set_auth(auth_instance)` → None
- `enhanced_add_book(title, author, isbn, publisher, year, total_copies=1, subject='', location='', description='')` → str
- `enhanced_checkout_book(book_id, user_id, due_date=None)` → str
- `process_book_return(loan_id, condition_notes='')` → bool
- `search_books(query, search_fields=None, available_only=False)` → List[dict]
- `manage_book_reservations(book_id, user_id, action='reserve')` → bool
- `generate_library_report(report_type='all')` → dict
- `bulk_import_books(filepath)` → Tuple[bool, str]
- `create_reading_list(name, creator_id, description='', is_public=False, is_collaborative=False, category='')` → str
- `add_book_to_reading_list(list_id, book_id, added_by, note='')` → bool
- `write_book_review(book_id, reviewer_id, rating, review_text)` → str
- `get_book_recommendations(user_id, limit=10)` → List[dict]
- `create_inter_library_loan_request(book_title, requester_id, source_library='')` → str
- `record_fine_payment(loan_id, amount_paid, payment_method)` → str
- `waive_fine(loan_id, waived_by, reason)` → bool

**`log_management.py`**
- `display_log_management_menu(auth)` → None
- `LogManagementGUI.__init__(self, root, auth=None)` → None
- `get_log_statistics()` → dict
- `search_logs(query, level=None, date_from=None, date_to=None, limit=100)` → List[dict]
- `export_logs(output_path, level=None, date_from=None, date_to=None)` → bool
- `clear_logs(older_than_days=30, level=None)` → int
- `generate_security_report()` → dict
- `get_recent_security_events(limit=50)` → List[dict]
- `create_log_management_tab(parent_frame, auth)` → tk.Frame

---

### M

**`main.py`**
- `StudentManagementGUI.__init__(self)` → None
- `StudentManagementGUI.create_sidebar(self)` → None
- `StudentManagementGUI.create_main_content(self)` → None
- `StudentManagementGUI.init_auth_for_modules(self)` → None
- `StudentManagementGUI.initialize_system(self)` → None
- `StudentManagementGUI.init_all_databases(self)` → bool
- `StudentManagementGUI.update_button_states(self)` → None
- `StudentManagementGUI.on_login_success(self, user_data)` → None
- `StudentManagementGUI.on_logout(self)` → None
- `StudentManagementGUI.setup_authenticated_buttons(self)` → None
- `StudentManagementGUI.create_tabs(self)` → None
- `StudentManagementGUI.open_module(self, module_name, *args)` → None
- `StudentManagementGUI.open_health_portal_gui(self)` → None
- `StudentManagementGUI.open_internship_portal_gui(self)` → None
- `StudentManagementGUI.open_parent_portal(self)` → None
- `StudentManagementGUI.open_parent_portal_gui(self)` → None
- `StudentManagementGUI.open_trip_management(self)` → None
- `StudentManagementGUI.open_plagiarism_checker_gui(self)` → None
- `StudentManagementGUI.open_log_management_gui(self)` → None
- `StudentManagementGUI.create_log_management_tab(self, parent)` → None
- `StudentManagementGUI.create_plagiarism_tab(self, parent)` → None
- `StudentManagementGUI.log_output(self, message)` → None
- `StudentManagementGUI.run(self)` → None
- `integrate_ai_detector_with_main()` → bool
- `integrate_plagiarism_checker_with_main()` → bool
- `ensure_default_users_exist_once()` → None
- `display_menu(auth)` → None

---

### P

**`parking_management.py`**
- `ParkingManager.__init__(self, db_path=None)` → None
- `ParkingManager.init_parking_db(self)` → bool
- `ParkingManager.create_permit(self, student_id, vehicle_id, lot_id, permit_type, start_date, end_date)` → str
- `ParkingManager.view_permit(self, permit_id)` → dict
- `ParkingManager.update_permit(self, permit_id, **kwargs)` → bool
- `ParkingManager.delete_permit(self, permit_id)` → bool
- `ParkingManager.view_all_permits(self, filters=None)` → List[dict]
- `ParkingManager.create_vehicle(self, student_id, make, model, year, colour, reg_plate)` → str
- `ParkingManager.view_vehicle(self, vehicle_id)` → dict
- `ParkingManager.update_vehicle(self, vehicle_id, **kwargs)` → bool
- `ParkingManager.check_lot_availability(self)` → List[dict]
- `ParkingManager.create_violation(self, vehicle_id, lot_id, space_id, violation_type, notes='')` → str
- `ParkingManager.view_violation(self, violation_id)` → dict
- `ParkingManager.update_violation(self, violation_id, **kwargs)` → bool
- `ParkingManager.process_violation_payment(self, violation_id, amount, payment_method)` → bool
- `ParkingManager.appeal_violation(self, violation_id, reason)` → Tuple[bool, str]
- `ParkingManager.view_all_violations(self, filters=None)` → List[dict]
- `ParkingManager.create_event(self, name, date, start_time, end_time, lot_id, rate_override=None, description='')` → str
- `ParkingManager.register_attendee(self, event_id, vehicle_id)` → bool
- `ParkingManager.generate_permit_report(self)` → dict
- `ParkingManager.generate_violation_report(self)` → dict
- `ParkingManager.search_permits(self, query)` → List[dict]
- `ParkingManager.add_parking_lot(self, name, location, total_spaces, hourly_rate)` → str
- `ParkingManager.get_lot_occupancy(self, lot_id)` → float
- `ParkingManager.check_permit_expiry(self)` → List[dict]
- `ParkingManager.expire_old_permits(self)` → int
- `ParkingManager.expire_completed_events(self)` → None
- `migrate_parking_schema()` → None
- `display_parking_menu(auth)` → None

**`parent_portal.py`**
- `ParentPortal.__init__(self, auth=None)` → None
- `ParentPortalGUI.__init__(self, auth=None)` → None
- `ParentPortalGUI.create_main_window(self)` → tk.Tk
- `ParentPortalGUI.run(self)` → None
- `init_parent_portal_db()` → bool
- `integrate_parent_portal_with_main()` → bool
- `create_sample_parent_data()` → None
- `display_parent_portal_menu(auth)` → None
- `setup_parent_portal_permissions()` → None
- `check_parent_access(parent_id, student_id)` → bool
- `get_student_consent_status(student_id)` → dict
- `update_student_consent(student_id, consent_type, value)` → bool
- `send_parent_notification(parent_id, subject, body)` → bool
- `add_academic_report(student_id, report_data)` → str
- `add_fee_record(student_id, fee_data)` → str
- `record_academic_probation(student_id, reason)` → bool
- `validate_email(email)` → bool

**`run_parent_portal_gui(auth)` (in `parent_portal_gui.py`)** → None

---

### R

**`restaurant_management.py`**
- `init_db()` → bool
- `set_auth(auth_instance)` → None
- `display_main_menu(auth)` → None
- `display_restaurant_menu(auth)` → None
- `add_menu_item(name, category, price, description='', allergens='', is_available=True)` → str
- `update_menu_item(item_id, **kwargs)` → bool
- `delete_menu_item(item_id)` → bool
- `create_order(customer_id, items, order_type='dine_in', table_id=None, notes='')` → str
- `add_item_to_order(order_id, menu_item_id, quantity, special_instructions='')` → bool
- `update_order_status(order_id, new_status)` → bool
- `process_payments(order_id)` → bool
- `process_cash_payment(order_id, amount_tendered)` → dict
- `process_card_payment(order_id, card_type)` → dict
- `process_meal_plan_payment(order_id, student_id)` → dict
- `add_customer(name, email, phone='', dietary_restrictions='')` → str
- `update_customer(customer_id, auth)` → None
- `update_inventory(item_name, quantity_change, reason)` → bool
- `generate_sales_report(date_from=None, date_to=None)` → dict
- `generate_receipt(order_id)` → str
- `log_audit_action(user_id, action, table_name, record_id, old_data, new_data)` → None

---

### S

**`shop_management.py`**
- `init_shop_db()` → bool
- `setup_shop_permissions(auth)` → None
- `set_auth(auth_instance)` → None
- `log_activity(user_id, action, details='')` → None
- `log_create(user_id, entity_type, entity_id)` → None
- `log_read(user_id, entity_type, entity_id)` → None
- `log_update(user_id, entity_type, entity_id, changes=None)` → None
- `log_delete(user_id, entity_type, entity_id)` → None
- `add_product(name, category, price, stock, description='', barcode='', reorder_level=5, image_path='')` → str
- `update_product(product_id, **kwargs)` → bool
- `delete_product(product_id)` → bool
- `adjust_stock(product_id, quantity_change, reason)` → bool
- `process_sale(items, payment_method, student_id=None, cashier_id=None)` → str
- `process_cash_payment(order_id, amount_tendered)` → dict
- `process_card_payment(order_id, card_type)` → dict
- `process_meal_plan_payment(order_id, student_id)` → dict
- `generate_receipt(order_id)` → str
- `add_loyalty_points(customer_id, points, reason)` → bool
- `get_loyalty_balance(customer_id)` → int
- `generate_daily_sales_summary(date=None)` → dict
- `generate_monthly_revenue_report(year, month)` → dict
- `update_shop_settings(settings_dict)` → bool
- `display_shop_menu(auth)` → None
- `UniversityShopGUI.__init__(self, root, auth=None)` → None

**`simple_activity_logger.py`**
- `log_activity(user_id, action, details='', metadata=None)` → None
- `log_create(user_id, entity_type, entity_id, details='')` → None
- `log_read(user_id, entity_type, entity_id, details='')` → None
- `log_update(user_id, entity_type, entity_id, old_data=None, new_data=None, details='')` → None
- `log_delete(user_id, entity_type, entity_id, details='')` → None
- `log_search(user_id, search_query, results_count, details='')` → None
- `log_export(user_id, export_type, record_count, file_path='')` → None
- `log_menu_navigation(user_id, from_menu, to_menu)` → None
- `log_dynamic_activity(user_id, action, **kwargs)` → None

**`student_support.py`**
- `display_support_menu(auth)` → None
- `integrate_with_main(main_gui_instance)` → bool
- `create_ticket(user_id, subject, description, category, priority='medium')` → str
- `view_ticket(ticket_id, requesting_user_id)` → dict
- `add_response(ticket_id, responder_id, response_text)` → str
- `update_ticket_status(ticket_id, new_status, updated_by)` → bool
- `get_tickets_for_user(user_id)` → List[dict]
- `view_all_tickets_enhanced(support, auth, page=1, per_page=20)` → None
- `display_enhanced_faqs(support)` → None
- `search_faqs(keyword)` → List[dict]
- `add_faq(question, answer, category)` → str
- `get_resource_links(category=None)` → List[dict]

---

### T

**`trip_management.py`**
- `init_trip_db()` → bool
- `setup_trip_permissions()` → bool
- `set_trip_auth(auth_instance)` → None
- `integrate_trip_management_with_main()` → bool
- `display_trip_management_menu(auth)` → None
- `create_trip(title, description, destination, start_date, end_date, organiser_id, capacity, registration_deadline, cost)` → str
- `update_trip(trip_id, **kwargs)` → bool
- `cancel_trip(trip_id, cancelled_by, reason)` → bool
- `get_upcoming_trips()` → List[dict]
- `get_all_trips(status=None)` → List[dict]
- `register_for_trip(trip_id, student_id, emergency_contact='', notes='')` → str
- `cancel_trip_registration(registration_id, cancelled_by)` → bool
- `get_trip_participants(trip_id)` → List[dict]
- `get_student_trip_registrations(student_id)` → List[dict]
- `create_trip_calendar_link(trip_id, calendar_event_id)` → str
- `generate_trip_summary(trip_id)` → dict
- `export_participant_list(trip_id, output_path)` → bool
- `TripManagementGUI.__init__(self, root, auth=None)` → None
- `TripManagementGUI.run(self)` → None
- `run_trip_management_gui(auth)` → None
- `display_trip_management_menu_gui(auth)` → None

---

### U

**`university_chatbot.py`**
- `UniversityChatbot.__init__(self, db_path=None)` → None
- `UniversityChatbot.set_auth(self, auth_instance)` → None
- `UniversityChatbot.authenticate_user_for_chatbot(self, username, password, mfa_code=None)` → dict
- `UniversityChatbot.validate_chatbot_session(self, session_token)` → Optional[AuthenticatedSession]
- `UniversityChatbot.check_user_permission(self, session_token, permission)` → bool
- `UniversityChatbot.process_authenticated_message(self, message, session_token)` → str
- `UniversityChatbot.process_message(self, message, context=None)` → str
- `UniversityChatbot.start_flask_api(self, host='0.0.0.0', port=5000)` → None
- `UniversityChatbot.integrate_with_main(self, main_system)` → bool
- `AuthenticatedSession` — dataclass with fields: `session_token`, `user_id`, `username`,
  `role`, `permissions`, `login_time`, `last_activity`, `ip_address`, `mfa_verified`,
  `password_change_required`
- `integrate_chatbot_with_main(main_system)` → bool

**`user_authentication.py`**
- `UserAuth.__init__(self, db_path=None)` → None
- `UserAuth._init_db(self)` → None
- `UserAuth._migrate_database_schema(self)` → None
- `UserAuth.login(self, username, password, mfa_code=None)` → dict
- `UserAuth.logout(self)` → None
- `UserAuth.check_permission(self, permission_name)` → bool
- `UserAuth.touch_session(self)` → None
- `UserAuth.add_user(self, username, password, role, email=None, first_name=None, last_name=None)` → int
- `UserAuth.change_password(self, user_id, old_password, new_password)` → bool
- `UserAuth.lock_account(self, user_id)` → bool
- `UserAuth.unlock_account(self, user_id)` → bool
- `UserAuth.setup_health_permissions_integration(self)` → None
- `UserAuth.ensure_default_users_exist_once(self)` → None
- `UserAuth.validate_mfa_code(self, user_id, code)` → bool
- `display_auth_menu(auth)` → None
- `display_user_management_menu(auth)` → None
- `setup_course_management_permissions()` → None
- `setup_attendance_permissions()` → None
- `setup_document_management_permissions()` → None
- `setup_parent_portal_permissions()` → None
- `add_plagiarism_permissions(auth_instance=None)` → List[str]
- `add_finance_permissions()` → List[str]
- `test_plagiarism_authentication()` → bool

---

*End of Function Signature Reference*

---

## GLOSSARY OF KEY TERMS


**`auth`** — The global `UserAuth` instance shared across all modules. Set via
`set_auth()` module-level functions in each module.

**`current_user`** — Dict stored in `auth.current_user` after login. Keys:
`id`, `username`, `email`, `first_name`, `last_name`, `role`, `student_id`,
`permissions` (list), `is_active`, `last_login`.

**`permission_name`** — A string key like `'manage_students'` checked via
`auth.check_permission(permission_name)`.

**`DB_PATH` / `db_path`** — Path to `student_records.db`. All modules resolve this
relative to the project root to ensure consistency.

**`init_*_db()`** — Module initialisation function that creates all tables for that
module. Returns `True` on success, `False` on failure. Safe to call multiple times
(uses `CREATE TABLE IF NOT EXISTS`).

**`set_auth(auth_instance)`** — Module-level function that stores the auth instance
in a module-level variable for use by all functions in that module.

**`setup_*_permissions()`** — Creates all permission records for a module and assigns
them to appropriate roles.

**`display_*_menu(auth)`** — CLI menu entry point for a module.

**`integrate_*_with_main()`** — Initialises a module and registers it with the main
system. Called during system startup.

**`orig_*`** — Alias pattern used in GUI modules to avoid name conflicts:
`from module import function as orig_function`.

**`FEATURE_AVAILABLE`** — Module-level boolean flag set after a try/except import.
Used to conditionally enable/disable features that depend on optional libraries.

**`handle_exception`** — Decorator that wraps functions with consistent error logging
and optional retry logic after schema migration.

**`backup_before_operation`** — Creates an automatic database backup before any
destructive operation. Keeps last 10 backups in `auto_backups/` directory.

**`safe_destroy(widget)`** — Safely destroys a Tkinter widget without raising an error
if it has already been destroyed.

**`touch_session()`** — Updates the `last_activity` timestamp for the current session,
preventing timeout during active use.

**`row_factory = sqlite3.Row`** — Set on all connections so query results support both
index-based and key-based access.

**WAL mode** — `PRAGMA journal_mode=WAL` applied to all connections for better
concurrent read performance.

---

*End of Glossary*
*End of CHANGELOG.md*
*University Student Management System*
*Lines: ~10,000 | Versions: 45+ | Modules: 85+*
*Development Period: June 2025 — March 2026*

---

## DEVELOPMENT NARRATIVE — TIMELINE AND CONTEXT


The following section provides a narrative account of how the University Student
Management System evolved over its development period, with technical context for
each major phase.

---

### Phase 1 — Foundation (June 2025)

The project began in early June 2025 as a command-line Python application for managing
student records at a UK university. The initial codebase consisted of a handful of
modules: `main.py`, `user_authentication.py`, `student_management.py`, and a few
utility files.

The very first session (2025-06-09) addressed a critical issue: the parking management
system had completely non-functional code due to `self.self.conn` appearing in 32
separate places across the `ParkingManager` class. Every single method in that class
raised an `AttributeError` before doing any useful work. This was fixed by global
search-and-replace.

The same session also fixed the database file path issue in `refactored/database/db.py`.
The `DB_PATH` calculation was incorrectly prepending `'refactored/db_files'` to a
`BASE_DIR` that was already inside the `refactored/database/` directory, resulting in a
path that nested `refactored` twice. The fix calculated the project root by going up
three directory levels from the file location.

The `ai_integration.py` module was removed during this session — it had become obsolete
after its functions were consolidated into `main.py` and `ai_detector.py`. The import
at the top of `main.py` was updated to import `AIDetector` directly.

By the end of the first week, the basic system was stable enough to handle: student
record CRUD, module enrollment, grade recording, basic parking, and authentication with
three roles (admin, staff, student).

---

### Phase 2 — Library and Alumni Expansion (2025-06-09 to 2025-06-15)

The second phase focused on expanding two service modules that had been created as
stubs: `library.py` and `alumni_management.py`.

`library.py` started with only 3 tables (`books`, `book_loans`, `book_reservations`)
and about 8 functions. The enhancement added 15 new tables covering digital resources,
reading lists, book clubs, inter-library loans, fine payment records, and more. The
`auth.current_user` dot-notation access pattern was identified and fixed across all
library methods.

`alumni_management.py` received 20+ new tables in a similar enhancement, covering
networking, mentorship, fundraising, regional chapters, gamification (points and
badges), and job board functionality. This transformed the alumni module from a simple
roster into a full alumni engagement platform.

The `module_scheduling.py` entry point bug was fixed: the `if __name__ == '__main__'`
block was inside the `ModuleScheduler` class body, so it never executed. The import
from `modules.py` was also corrected — named module instances were imported directly
instead of non-existent utility functions.

---

### Phase 3 — Communication and Authentication (2025-06-16 to 2025-06-30)

This phase addressed the communication layer and authentication integration patterns.

The email manager's `send_message()` function was completely rewritten. The original
used `receiver_id` as a column name (should be `recipient_id`), had no `sent_at`
timestamp, and returned no value. The rewrite added dual-copy architecture (inbox and
sent copies), proper column names, timestamp recording, and `True/False` return values.

The `messages` table schema was expanded with 6 missing columns: `sent_at`, `is_read`,
`read_at`, `folder`, `is_deleted_by_sender`, `is_deleted_by_recipient`. All code
referencing the old schema was updated.

Two health portal email functions were added to `email_manager.py`: 
`send_appointment_confirmation()` and `send_health_notification()`. These had been
imported by `health_portal.py` for months but never existed.

The chatbot authentication system was built out from scratch. The `UniversityChatbot`
class gained a full `AuthenticatedSession` dataclass, a Flask REST API with login,
logout, chat, and permission-check endpoints, session token generation using
`secrets.token_hex(16)`, and a 30-minute inactivity timeout.

The parent portal was designed with a two-file architecture, and integration issues
with `main.py` were identified and resolved: the `open_parent_portal()` method was
fixed to pass auth, the `parent` role was added to the authentication system, and
parent-specific permissions were defined.

---

### Phase 4 — Refactoring and Structure (2025-07-01 to 2025-07-31)

July 2025 was a significant restructuring month. The `refactored/` directory structure
was established, moving modules into logical subdirectories:
- `refactored/services/` — campus services (alumni, restaurant, parking, library, shop, etc.)
- `refactored/academic/` — academic modules (grades, courses, scheduling, assignments)
- `refactored/finance/` — finance and reporting modules
- `refactored/support/` — helpdesk and student support
- `refactored/ai/` — chatbot and AI detector
- `refactored/admin/` — authentication and user management
- `refactored/database/` — database utilities and connection management

All import paths in `main.py` were updated to use the new structure. The `set_auth as`
alias pattern was standardised across all modules to avoid name collisions when
importing multiple `set_auth` functions.

The `student_analytics` module received its most significant enhancement: the grade
tracking system's `GradeTrackingGUI` was extended with 6 new dialog classes:
`RiskAssessmentDialog`, `PredictiveAnalyticsDialog`, `ModulePerformanceDialog`,
`AssessmentAnalysisDialog`, `GradeDistributionDialog`, and `TrendAnalysisDialog`.

The `students` table underwent a major schema change: `phone_number` column was removed
(no longer needed), `enrollment_date` was renamed to `registration_datetime`, and new
columns `title`, `gender`, `dob`, and `age` were added. This change required updates
across 12 modules that referenced the old column names.

The `grade_tracking_gui.py` edit function `edit_selected_grade()` was completed — it
had been a stub that returned `None` without doing anything. The full implementation
queries the selected row, pre-fills a `GradeDialog`, saves changes, recalculates GPA,
and updates the display.

Batch operations received comprehensive data management tools: `find_duplicate_students()`,
`validate_and_clean_data()`, `data_quality_dashboard()`, `generate_import_template()`,
and `bulk_enroll_students()`.

---

### Phase 5 — GUI Conversion Wave (2025-08-01 to 2025-08-31)

August 2025 was the "GUI month" — nearly every major CLI module was converted to a
Tkinter GUI while maintaining CLI backwards compatibility.

The pattern used consistently:
1. New GUI file created (e.g., `helpdesk_gui.py`, `shop_management_gui.py`).
2. GUI file imports `from original_module import *` with try/except fallback.
3. GUI class has `auth` parameter throughout.
4. Module-level `display_*_menu_gui(auth)` entry point created.
5. Original `display_*_menu(auth)` function unchanged.
6. `main.py` updated to try GUI first, fall back to CLI.

Modules converted to GUI this month:
- `helpdesk_gui.py` — Full ticket management with SLA colour coding.
- `shop_management_gui.py` — POS interface with product grid and cart.
- `student_union_gui.py` — Multi-tab interface for clubs, events, equipment, facilities.
- `attendance_gui.py` — Enhanced with QR check-in, predictive analytics, gamification.
- `trip_management_gui.py` — Trip booking with participant management.
- `gui_assignment_system.py` — Drag-and-drop file submission with progress bars.

The trip management auth bug was fixed: `open_trip_management()` was calling
`display_trip_management_menu()` without passing auth or calling `set_trip_auth()` first.

The `health_portal_gui.py` was built with 9 tabs covering records, vaccinations,
appointments, student management, providers, referrals, screening, security, and reports.

The `attendance_tracker.py` ImportError for `display_attendance_menu` was resolved by
adding the function as a module-level entry point that launches the `AttendanceTrackerGUI`
or falls back to a console menu.

---

### Phase 6 — Feature Completeness (2025-09-01 to 2025-09-17)

September focused on filling gaps: functions referenced but not implemented, tables
expected but not created, integrations connected but not wired.

The document management system received its largest set of additions: 40+ functions
were implemented that had been stubs or non-existent despite being called from the
menu system. This included all bulk operations, reporting functions, OCR integration,
API management, and import/export tools.

The `data_backup_gui.py` was completed with `restore_from_backup()`, differential
backup support, scheduler functions, and backup template management.

The health portal security features were fully implemented: field-level encryption using
`cryptography.fernet`, audit trail logging with the `@audit_trail` decorator, data
retention policies with automatic archival, and session timeout with failed login
locking.

`parent_portal_gui.py` received its final integration fix, including the email regex
syntax error (`r'^...\.[a-zA-Z]{2,}` was missing the closing `'`).

The automated test runner `run_tests.py` was created with 8 test phases, input
simulation via `io.StringIO`, and JSON output for CI integration.

---

### Phase 7 — Documentation and Polish (2025-10-01 to 2026-01-27)

The final development phase focused on consolidation and documentation.

53 separate markdown documentation files were consolidated into two files:
- `readme.md` — System overview, all module documentation, installation guide.
- `changelog.md` — All bug fixes and enhancements organised by date.

The January 2026 session added documentation for 68+ bug fixes, categorised into:
database issues, email issues, API mismatches, UI/UX issues, and finance integration.

The `AcademicAffairs.py` module was integrated into the main system for the first time.
Previously, 6 database tables it needed were missing from `_create_tables()`. The
`add_transfer_credits()` INSERT statement had incorrect tuple construction. Both were
fixed.

The `email_manager.py` `messages` table schema mismatch was resolved. The `messages`
table had been updated with new columns but several remaining functions still referenced
the old schema with `receiver_id` instead of `recipient_id`.

The `finance_reporting.py` `integrate_reporting_with_main_gui` function was extracted
from the class and placed at module level, fixing the `AttributeError` that occurred
when `main.py` tried to import it.

---

### Architecture Decisions

**Single database file:** All modules share a single `student_records.db` SQLite
database file. This was chosen for simplicity and to allow cross-module queries.
The downside is that all modules must be careful about table name conflicts.

**Module-level auth pattern:** Each module holds its own reference to the auth object
via a `_auth` module-level variable and a `set_auth(auth_instance)` function. This
avoids circular imports while allowing every function to check permissions.

**CLI-first, GUI-as-enhancement:** All modules were designed as CLI first. GUI wrappers
were added later as separate files. This means the system can always fall back to CLI
if GUI fails, and headless server deployments work without modification.

**`INSERT OR IGNORE` for permissions:** All permission and role setup functions use
`INSERT OR IGNORE` to make them idempotent — safe to call multiple times without
creating duplicate records.

**`ALTER TABLE ADD COLUMN` migrations:** All schema migrations use `ALTER TABLE ADD
COLUMN` wrapped in try/except to handle the case where columns already exist. This is
simpler than versioned migrations but requires all ADD COLUMN statements to be
idempotent (i.e., only add columns, never remove or rename).

**WAL journal mode:** All database connections set `PRAGMA journal_mode=WAL` for
better read concurrency. This means multiple threads can read while one writes.

**Thread-local connections:** The `DatabaseManager` class maintains one connection per
thread, preventing the `sqlite3.ProgrammingError: SQLite objects created in a thread
can only be used in that same thread` error that was causing crashes in the GUI's
background loading threads.

---

### Known Limitations

**No migration versioning:** The system uses a series of `ALTER TABLE ADD COLUMN`
checks on every startup. While this works, it is slow for large databases and does not
support column removal, renaming, or type changes.

**Single-file database:** A single SQLite file shared by 85+ modules creates contention
at high load. The WAL mode mitigates this but a production deployment should consider
migrating to PostgreSQL.

**Optional library degradation:** Many advanced features (charts, QR codes, Excel
export, OCR) are gated behind optional library imports. The graceful fallback pattern
means features silently disappear rather than failing loudly, which can confuse users.

**No automated tests in CI:** The `run_tests.py` file was created in September 2025 but
was not integrated into any CI/CD pipeline. All testing was done manually.

**Duplicate student_records.db files:** During the refactoring phase, some modules
hard-coded the path to `student_records.db` while others used the centralised path
resolution. This could result in multiple database files being created in different
locations, causing data to appear in some modules but not others.

**Session management:** Sessions are stored in-memory in the `UserAuth` instance.
If the main process restarts, all active sessions are invalidated. There is no persistent
session storage.

---

### Security Notes

**Password hashing:** All passwords are hashed with SHA-256. While SHA-256 is not
recommended for password storage in production (bcrypt or argon2 preferred), it is
used throughout for simplicity. Migration to bcrypt would require a one-time re-hash
on next login for each user.

**SQL injection:** The codebase was audited in Phase 6 and all string-formatted SQL
queries were replaced with parameterised queries. The audit identified 12 injection
vulnerabilities, all fixed.

**Health data encryption:** Sensitive health fields use `cryptography.fernet`
encryption. The key is stored in an environment variable. If the key is lost, encrypted
health data is unrecoverable.

**Audit logging:** All health record accesses are logged to `health_audit_log`. Other
modules use `activity_logs` for general audit trails.

**MFA support:** Multi-factor authentication via TOTP is supported but optional.
The `pyotp` library must be installed. If not installed, MFA checks are silently skipped.

---

*End of Development Narrative*

---

## INDEX OF ALL CHANGES BY FILE


For quick reference, here is an index of which file received changes in which version:

### AcademicAffairs.py
v2.5.0 — Fixed missing tables, broken imports, fixed INSERT statement, fixed date_approved

### academic_calendar.py
v0.0.9, v2.4.0 — Auth integration, CalendarAuthIntegration, SafeCalendarWindow

### accommodation.py
v0.2.0 — audit_log migration (accommodation_id, details, ip_address columns)

### advanced_search.py
v1.4.0, 2025-06-17 — GUI integration, dynamic query builder, search templates

### ai_detector.py
v0.0.9, 2025-06-09, 2025-08-21 — RotatingFileHandler, optional requests, empty try fix

### alumni_management.py
v0.0.1 — 20+ new tables

### assignment_submission.py
v0.8.0, 2025-06-15, 2025-08-18 — New file, import fixes, GUI conversion

### attendance_tracker.py
v0.0.9, 2025-06-16, 2025-08-20 — DatabaseManager, display_attendance_menu, GUI upgrade

### batch_operations.py
v1.4.0, 2025-07-06 — Full implementation, data quality tools

### calendar_integration_fixed.py
2025-06-09 — SafeCalendarWindow wrapper

### chatbot (university_chatbot.py)
v0.4.0, v0.0.9 — Full auth integration, REST API, session management, MFA, rewrite

### course_management_gui.py
v1.4.0 — Completeness fixes

### data_backup.py
v1.4.0, 2025-09-04 — Missing functions added, differential backup, scheduler

### database_utils.py
v0.0.9, all versions — DatabaseManager singleton, cleanup, integrity check, backup_before_operation

### db.py (refactored/database/db.py)
v0.0.8 — Nested path bug fixed

### document_manager.py
v2.3.0, 2025-06-09, 2025-08-03 — Original refactoring, 40+ missing functions

### email_manager.py
v2.2.0, v0.0.1, 2025-06-16 — messages table schema, send_message rewrite, health functions

### finance.py
v1.9.0, 2025-06-26 — GUI + chatbot schema sync, display_enhanced_finance_menu, column fixes

### finance_reporting.py
v1.9.0, 2025-06-26 — integrate_reporting_with_main_gui fix, missing functions

### grade_tracking.py / grade_tracking_gui.py
v1.8.0, v1.3.0, v1.0.0, 2025-07-27 — 6 new dialogs, edit_selected_grade, analytics, export

### health_portal.py
v2.1.0, 2025-06-09, 2025-06-28, 2025-07-18 — Import cleanup, permissions, full feature build

### health_portal_gui.py
2025-08-25 — New file, 9-tab GUI

### helpdesk.py / helpdesk_gui.py
2025-08-19 — GUI conversion, pagination, SLA colour coding

### housing_accommodation.py / housing_accommodation_gui.py
v0.6.0, v1.1.0, v1.4.0, v1.5.0 — New file, orig_ aliases, structural fixes

### internship_management.py
v1.4.0, 2025-06-29 — Missing columns, company table, auth integration

### library.py
v0.0.3, v0.0.4, v0.0.5, v0.0.6 — 15+ tables, auth fixes, import fixes, dict access fixes

### log_management.py
2025-07-31, 2025-08-27 — File path refactoring, GUI tab integration

### main.py
v0.0.7, v2.4.0, 2025-06-09-26 — Syntax errors, full rewrite, attribute errors, auth flow

### module_scheduling.py
v0.0.2 — Entry point fix, modules.py integration

### parking_management.py
v0.0.9 — 32× self.self.conn, missing methods, date parsing, violation/event menus

### parent_portal.py / parent_portal_gui.py
2025-06-09, 2025-06-29, 2025-09-02 — Redesign, auth integration, email regex fix

### plagiarism system
2025-06-09, 2025-06-12, 2025-07-07, 2025-08-21, 2025-08-30 — Import fix, permissions, GUI

### restaurant_management.py
v0.3.0, v2.0.0 — Duplicate functions removed, update_customer, SQL injection, imports

### shop_management.py / shop_management_gui.py
v1.4.0, 2025-08-20 — Completeness, GUI conversion with POS

### simple_activity_logger.py
All versions — Core logging infrastructure

### student_support.py
v0.5.0, v1.5.0 — Undefined functions, permissions schema, enhanced FAQs, pagination

### student_union.py / student_union_gui.py
v0.0.7, 2025-08-26 — New file, GUI conversion

### trip_management.py / trip_management_gui.py
2025-06-13, 2025-06-25, 2025-07-27, 2025-08-20 — Integration, auth fix, missing functions, GUI

### user_authentication.py
v0.0.9, v0.4.0, all versions — DatabaseManager, MFA, permissions, role system, centralised users

---

*End of Index*

---

*CHANGELOG.md — University Student Management System*
*Compiled: March 2026*
*Total lines: ~10,000*
*Covers: June 2025 — March 2026*
*Versions documented: v0.0.1 through v2.5.0 (45+ versions)*
*Files covered: 85+ Python source files*
*Database tables: 210+ across all modules*
*Permissions: 120+ unique permission strings*

---

