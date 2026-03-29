"""
Pytest configuration and fixtures for the University System test suite.

This module provides:
- Authentication initialization before test collection
- Common fixtures for database, authentication, and GUI testing
- Test configuration and markers
"""

import atexit
import os
import sys
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def pytest_configure(config):
    """Configure pytest before test collection begins."""
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "security: Security-related tests")
    config.addinivalue_line("markers", "gui: GUI tests requiring tkinter")
    config.addinivalue_line("markers", "database: Database tests")

    # Mock tkinter ONCE, centrally, before any test module imports.
    # We use the real tkinter classes (so spec= works) but replace Tk()
    # instantiation with a MagicMock (so no windows open).
    _setup_headless_tkinter()

    # Initialize authentication system before any imports that might need it
    _initialize_test_auth()


def _setup_headless_tkinter():
    """Make tkinter importable without opening windows.

    Import the real tkinter module so that ``Mock(spec=tk.Frame)`` etc.
    resolve to real classes, then neuter ``Tk.__init__`` so that no
    display connection is attempted.
    """
    try:
        import tkinter as tk
        from unittest.mock import MagicMock

        # Save the real Tk.__init__ and replace it with a no-op so that
        # ``tk.Tk()`` never tries to connect to a display server.
        _real_tk_init = tk.Tk.__init__

        def _mock_tk_init(self, *args, **kwargs):
            # Initialise just enough for widget code to not crash
            self.tk = MagicMock()
            self.children = {}
            self._tclCommands = None
            self._w = '.'
            self.master = None

        tk.Tk.__init__ = _mock_tk_init
        tk.Tk.mainloop = MagicMock()

        # Create a default root so that tk.StringVar() etc. work at
        # module level without raising "Too early to create variable".
        _default_root = tk.Tk()
        tk._default_root = _default_root
        tk.Tk.destroy = MagicMock()
        tk.Tk.update = MagicMock()
        tk.Tk.update_idletasks = MagicMock()
        tk.Tk.winfo_screenwidth = MagicMock(return_value=1920)
        tk.Tk.winfo_screenheight = MagicMock(return_value=1080)
        tk.Tk.winfo_exists = MagicMock(return_value=True)
        tk.Tk.withdraw = MagicMock()
        tk.Tk.deiconify = MagicMock()
        tk.Tk.title = MagicMock()
        tk.Tk.geometry = MagicMock()
        tk.Tk.protocol = MagicMock()
        tk.Tk.after = MagicMock()
        tk.Tk.configure = MagicMock()
        tk.Tk.config = MagicMock()
    except (ImportError, Exception):
        # If tkinter genuinely isn't installed, fall back to MagicMock
        from unittest.mock import MagicMock
        mock_tk = MagicMock()
        mock_tk.TclError = Exception
        sys.modules.setdefault('tkinter', mock_tk)
        sys.modules.setdefault('tkinter.ttk', MagicMock())
        sys.modules.setdefault('tkinter.messagebox', MagicMock())
        sys.modules.setdefault('tkinter.simpledialog', MagicMock())
        sys.modules.setdefault('tkinter.filedialog', MagicMock())
        sys.modules.setdefault('tkinter.font', MagicMock())
        sys.modules.setdefault('tkinter.scrolledtext', MagicMock())

def _initialize_test_auth():
    """Initialize the authentication system for test collection.

    This prevents AuthenticationNotInitializedError during module imports.
    Uses a lightweight mock instead of the real UserAuth to avoid the ~19s
    cold-start penalty from importing AI/chatbot/voice modules.
    """
    try:
        from education_system.university_system.infrastructure.shared_context import (
            is_auth_initialized,
            set_auth,
        )
        import education_system.university_system.infrastructure.shared_context as _ctx

        if not is_auth_initialized():
            # Create a mock that satisfies all auth checks without
            # importing the heavy UserAuth class or its dependencies.
            mock_auth = MagicMock()
            mock_auth.is_logged_in.return_value = False
            mock_auth.current_user = None
            mock_auth.check_permission.return_value = True
            mock_auth.get_current_user.return_value = None
            mock_auth.has_permission.return_value = True
            mock_auth.db_path = ":memory:"

            set_auth(mock_auth)
            # Mark as initialized so other code doesn't try again
            _ctx._auth_initialized = True

    except Exception as e:
        print(f"Warning: Could not initialize test auth: {e}")

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def _template_db():
    """Create a seeded template DB once per session (schema + permissions)."""
    temp_dir = tempfile.mkdtemp(prefix="university_test_template_")
    db_path = os.path.join(temp_dir, "template.db")
    _create_test_database(db_path)
    yield db_path
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture(scope="session")
def test_db_path(_template_db):
    """Create a temporary database for the entire test session."""
    temp_dir = tempfile.mkdtemp(prefix="university_test_session_")
    db_path = os.path.join(temp_dir, "test_session.db")
    shutil.copy2(_template_db, db_path)
    yield db_path
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


class _UnclosableConnection:
    """Wrapper around sqlite3.Connection that makes close() a no-op.

    Production code calls conn.close() at the end of each service method.
    Tests that patch get_connection to return a real connection need to
    query it *after* the service call to verify results.  This wrapper
    makes close() a no-op so the connection stays open; the underlying
    connection will be closed when the object is garbage-collected.

    Note: sqlite3.Connection is a C type in Python 3.11+ and does not
    allow setting arbitrary attributes, so we use delegation instead.
    """
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    def close(self):
        pass  # no-op

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *args):
        return self._conn.__exit__(*args)


def unclosable_connect(db_path):
    """Create a sqlite3 connection whose close() is a no-op."""
    return _UnclosableConnection(db_path)


@pytest.fixture(autouse=True)
def _isolate_db(_template_db, monkeypatch):
    """Automatically isolate every test from the production database.

    Creates a fresh copy of the template DB and patches DEFAULT_DB_PATH /
    DEFAULT_DB_NAME in the db module so that get_connection() and transaction()
    calls without an explicit db_path use this temporary database.

    This fixture is autouse so that *all* tests — even those that never
    mention temp_db — run against an isolated throw-away database.
    """
    temp_dir = tempfile.mkdtemp(prefix="university_test_")
    db_path = os.path.join(temp_dir, "test.db")
    shutil.copy2(_template_db, db_path)

    import education_system.university_system.infrastructure.database.db as _db_mod
    monkeypatch.setattr(_db_mod, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(_db_mod, "DEFAULT_DB_NAME", os.path.basename(db_path))

    yield db_path
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture
def temp_db(_isolate_db):
    """Provide the path to the isolated temporary database.

    This is a convenience alias — the actual DB creation and monkeypatching
    is handled by the autouse _isolate_db fixture.  Tests that need the
    path (e.g. to open a direct sqlite3 connection) can request this fixture.
    """
    return _isolate_db

@pytest.fixture
def db_connection(temp_db):
    """Provide a database connection for tests."""
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()

def _create_test_database(db_path):
    """Create a test database with full schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Core user tables (legacy + shared auth compatible)
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            role TEXT DEFAULT 'student',
            student_id TEXT,
            department TEXT,
            password_hash TEXT,
            legacy_salt TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS user_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            user_id INTEGER,
            is_active INTEGER DEFAULT 1,
            failed_login_attempts INTEGER DEFAULT 0,
            last_login TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_token TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            system_key TEXT NOT NULL,
            role TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, system_key)
        );

        CREATE TABLE IF NOT EXISTS mfa_secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            secret TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permission_name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles (id),
            FOREIGN KEY (permission_id) REFERENCES permissions (id),
            UNIQUE(role_id, permission_id)
        );

        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            granted INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (permission_id) REFERENCES permissions (id),
            UNIQUE(user_id, permission_id)
        );

        -- Student tables
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            email_address TEXT,
            phone TEXT,
            phone_number TEXT,
            gender TEXT,
            date_of_birth TEXT,
            dob TEXT,
            age INTEGER,
            enrollment_date TEXT,
            graduation_date TEXT,
            major TEXT,
            course TEXT,
            minor TEXT,
            gpa REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            address TEXT,
            emergency_contact TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- Course tables
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT UNIQUE,
            course_id TEXT UNIQUE,
            course_name TEXT NOT NULL,
            description TEXT,
            credits INTEGER DEFAULT 3,
            credit_hours REAL DEFAULT 3.0,
            duration INTEGER,
            level TEXT,
            department TEXT,
            instructor_id INTEGER,
            max_enrollment INTEGER DEFAULT 30,
            current_enrollment INTEGER DEFAULT 0,
            semester TEXT,
            year INTEGER,
            schedule TEXT,
            location TEXT,
            status TEXT DEFAULT 'active',
            course_type TEXT DEFAULT 'Core',
            lab_required BOOLEAN DEFAULT 0,
            online_available BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (instructor_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            enrollment_date TEXT,
            status TEXT DEFAULT 'enrolled',
            grade TEXT,
            grade_points REAL,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(student_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_id TEXT,
            assessment_id INTEGER,
            assignment_name TEXT,
            assignment_type TEXT,
            score REAL,
            grade REAL,
            max_score REAL DEFAULT 100,
            weight REAL DEFAULT 1.0,
            letter_grade TEXT,
            grade_date TEXT,
            submission_date TEXT,
            semester TEXT,
            comments TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        -- Modules and related tables for grading tests
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT UNIQUE NOT NULL,
            module_name TEXT NOT NULL,
            credits INTEGER DEFAULT 10,
            module_type TEXT,
            course_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            enrollment_date TEXT,
            grade TEXT,
            UNIQUE(student_id, module_code)
        );

        CREATE TABLE IF NOT EXISTS module_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            final_score REAL,
            final_grade TEXT
        );

        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            assessment_name TEXT NOT NULL,
            assessment_type TEXT,
            max_points REAL,
            due_date TEXT
        );

        -- Activity log
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- MFA tables
        CREATE TABLE IF NOT EXISTS mfa_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            mfa_enabled INTEGER DEFAULT 0,
            mfa_secret TEXT,
            backup_codes TEXT,
            preferred_method TEXT DEFAULT 'totp',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- Insert default permissions
        INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES
            ('all', 'Full access', datetime('now')),
            ('view_students', 'View student records', datetime('now')),
            ('edit_students', 'Edit student records', datetime('now')),
            ('delete_students', 'Delete student records', datetime('now')),
            ('view_courses', 'View courses', datetime('now')),
            ('edit_courses', 'Edit courses', datetime('now')),
            ('view_grades', 'View grades', datetime('now')),
            ('edit_grades', 'Edit grades', datetime('now')),
            ('manage_users', 'Manage users', datetime('now')),
            ('view_own_grades', 'View own grades', datetime('now'));

        -- Instructors
        CREATE TABLE IF NOT EXISTS instructors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id TEXT UNIQUE,
            first_name TEXT NOT NULL DEFAULT '',
            last_name TEXT NOT NULL DEFAULT '',
            email TEXT UNIQUE NOT NULL DEFAULT '',
            department TEXT,
            specialization TEXT,
            max_courses_per_semester INTEGER DEFAULT 4,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Document management
        CREATE TABLE IF NOT EXISTS document_types (
            type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT NOT NULL,
            description TEXT,
            has_expiry BOOLEAN DEFAULT 0,
            requires_approval BOOLEAN DEFAULT 1,
            category TEXT,
            is_active BOOLEAN DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS student_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            document_type_id INTEGER,
            file_name TEXT,
            file_path TEXT,
            upload_date TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'Pending',
            verified_by TEXT,
            verification_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT DEFAULT 'general',
            owner_id TEXT,
            document_type TEXT,
            document_name TEXT,
            file_path TEXT,
            file_size INTEGER,
            upload_date TEXT,
            status TEXT DEFAULT 'active',
            version_number INTEGER DEFAULT 1,
            tags TEXT,
            notes TEXT,
            uploaded_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS document_workflow (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            step_name TEXT,
            step_order INTEGER,
            assigned_to TEXT,
            status TEXT,
            comments TEXT,
            completed_date TEXT,
            completed_by TEXT
        );

        CREATE TABLE IF NOT EXISTS document_tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT UNIQUE,
            tag_color TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS course_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT,
            program TEXT,
            type_id INTEGER,
            is_mandatory BOOLEAN DEFAULT 1,
            deadline_days INTEGER
        );

        -- Notifications
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            recipient_id TEXT,
            title TEXT,
            message TEXT,
            notification_type TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_date TEXT,
            priority TEXT DEFAULT 'normal',
            related_document_id INTEGER
        );

        -- Audit log
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        );

        -- System settings
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE,
            setting_value TEXT,
            description TEXT,
            updated_by TEXT,
            updated_date TEXT
        );

        -- LMS
        CREATE TABLE IF NOT EXISTS lms_courses (
            lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT,
            instructor_id TEXT,
            course_description TEXT,
            syllabus_url TEXT,
            start_date TEXT,
            end_date TEXT,
            is_published BOOLEAN DEFAULT 0,
            enrollment_limit INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Evaluation
        CREATE TABLE IF NOT EXISTS evaluation_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            template_type TEXT NOT NULL,
            description TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );

        -- Learning outcomes
        CREATE TABLE IF NOT EXISTS learning_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT,
            outcome_code TEXT,
            description TEXT,
            category TEXT,
            importance INTEGER
        );

        -- Accommodations
        CREATE TABLE IF NOT EXISTS accommodations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            accommodation_type TEXT,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            approved_by TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );

        -- Library
        CREATE TABLE IF NOT EXISTS books (
            book_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT UNIQUE,
            publisher TEXT,
            category TEXT,
            year_published INTEGER,
            description TEXT,
            location TEXT,
            status TEXT DEFAULT 'available',
            added_date TEXT
        );

        CREATE TABLE IF NOT EXISTS book_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT,
            user_id TEXT,
            rating INTEGER,
            review_text TEXT,
            review_date TEXT,
            status TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS library_settings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            description TEXT,
            setting_type TEXT DEFAULT 'string'
        );

        -- Restaurant
        CREATE TABLE IF NOT EXISTS restaurant_orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_price REAL,
            tax_amount REAL,
            status TEXT DEFAULT 'Pending',
            payment_method TEXT
        );

        -- Health
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            email TEXT,
            last_checkup TEXT,
            screening_type TEXT,
            next_screening_due TEXT
        );

        -- Email
        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            subject TEXT,
            body TEXT,
            created_by TEXT,
            is_shared INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Contract alerts
        CREATE TABLE IF NOT EXISTS contract_renewal_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT,
            contract_end_date TEXT,
            alert_date TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT
        );

        -- Integration marketplace
        CREATE TABLE IF NOT EXISTS integration_catalog (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            integration_type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            version TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS installed_integrations (
            install_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            installed_by TEXT NOT NULL,
            installation_date TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            is_enabled BOOLEAN DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS integration_credentials (
            credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            credential_type TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            endpoint_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS integration_sync_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            sync_start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            sync_end_time TEXT,
            sync_status TEXT NOT NULL,
            records_synced INTEGER DEFAULT 0,
            errors_encountered INTEGER DEFAULT 0,
            error_details TEXT
        );

        CREATE TABLE IF NOT EXISTS integration_data_mappings (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            source_field TEXT NOT NULL,
            target_field TEXT NOT NULL,
            transformation_rule TEXT,
            is_active BOOLEAN DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS integration_webhooks (
            webhook_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            webhook_url TEXT NOT NULL,
            event_type TEXT NOT NULL,
            secret_key TEXT,
            is_active BOOLEAN DEFAULT 1,
            last_triggered_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()

@pytest.fixture
def mock_auth():
    """Provide a mock authentication object."""
    auth = MagicMock()
    auth.current_user = {
        'id': 1,
        'user_id': 1,
        'username': 'test_admin',
        'email': 'admin@test.edu',
        'role': 'admin',
        'first_name': 'Test',
        'last_name': 'Admin'
    }
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    auth.get_current_user.return_value = auth.current_user
    auth.has_permission.return_value = True
    return auth

@pytest.fixture
def mock_student_auth():
    """Provide a mock authentication object for a student."""
    auth = MagicMock()
    auth.current_user = {
        'id': 2,
        'user_id': 2,
        'username': 'test_student',
        'email': 'student@test.edu',
        'role': 'student',
        'first_name': 'Test',
        'last_name': 'Student'
    }
    auth.is_logged_in.return_value = True
    auth.check_permission.side_effect = lambda p: p in ['view_own_grades', 'view_courses']
    auth.get_current_user.return_value = auth.current_user
    return auth

@pytest.fixture
def mock_instructor_auth():
    """Provide a mock authentication object for an instructor."""
    auth = MagicMock()
    auth.current_user = {
        'id': 3,
        'user_id': 3,
        'username': 'test_instructor',
        'email': 'instructor@test.edu',
        'role': 'instructor',
        'first_name': 'Test',
        'last_name': 'Instructor'
    }
    auth.is_logged_in.return_value = True
    auth.check_permission.side_effect = lambda p: p in [
        'view_students', 'view_courses', 'edit_grades', 'view_grades'
    ]
    auth.get_current_user.return_value = auth.current_user
    return auth

@pytest.fixture
def mock_tk():
    """Mock tkinter modules for GUI tests."""
    with patch.dict(
        "sys.modules",
        {
            "tkinter": MagicMock(),
            "tkinter.ttk": MagicMock(),
            "tkinter.filedialog": MagicMock(),
            "tkinter.messagebox": MagicMock(),
            "tkinter.simpledialog": MagicMock(),
            "tkinter.colorchooser": MagicMock(),
            "tkinter.font": MagicMock(),
        },
    ):
        yield

@pytest.fixture
def mock_root():
    """Create a mock Tk root window."""
    root = MagicMock()
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    root.winfo_exists.return_value = True
    root.title = MagicMock()
    root.geometry = MagicMock()
    root.protocol = MagicMock()
    root.mainloop = MagicMock()
    root.destroy = MagicMock()
    root.withdraw = MagicMock()
    root.deiconify = MagicMock()
    root.update = MagicMock()
    root.after = MagicMock()
    return root

@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    path = tempfile.mkdtemp()
    yield path
    try:
        shutil.rmtree(path)
    except Exception:
        pass

@pytest.fixture
def sample_student_data():
    """Provide sample student data for testing."""
    return {
        'student_id': 'STU001',
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john.doe@test.edu',
        'phone': '555-0100',
        'date_of_birth': '2000-01-15',
        'enrollment_date': '2023-09-01',
        'major': 'Computer Science',
        'status': 'active'
    }

@pytest.fixture
def sample_course_data():
    """Provide sample course data for testing."""
    return {
        'course_code': 'CS101',
        'course_name': 'Introduction to Programming',
        'description': 'Basic programming concepts',
        'credits': 3,
        'department': 'Computer Science',
        'max_enrollment': 30,
        'semester': 'Fall',
        'year': 2024,
        'status': 'active'
    }

@pytest.fixture
def sample_grade_data():
    """Provide sample grade data for testing."""
    return {
        'assignment_name': 'Midterm Exam',
        'assignment_type': 'exam',
        'score': 85.5,
        'max_score': 100,
        'weight': 0.3,
        'comments': 'Good work'
    }

# ============================================================================
# Test helpers
# ============================================================================

def insert_test_student(conn, student_data):
    """Helper to insert a test student."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email, phone,
                            date_of_birth, enrollment_date, major, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        student_data['student_id'],
        student_data['first_name'],
        student_data['last_name'],
        student_data['email'],
        student_data.get('phone', ''),
        student_data.get('date_of_birth', ''),
        student_data.get('enrollment_date', ''),
        student_data.get('major', ''),
        student_data.get('status', 'active')
    ))
    conn.commit()
    return cursor.lastrowid

def insert_test_course(conn, course_data):
    """Helper to insert a test course."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO courses (course_code, course_name, description, credits,
                           department, max_enrollment, semester, year, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        course_data['course_code'],
        course_data['course_name'],
        course_data.get('description', ''),
        course_data.get('credits', 3),
        course_data.get('department', ''),
        course_data.get('max_enrollment', 30),
        course_data.get('semester', ''),
        course_data.get('year', 2024),
        course_data.get('status', 'active')
    ))
    conn.commit()
    return cursor.lastrowid

def insert_test_user(conn, user_data, password='TestPassword123'):
    """Helper to insert a test user with both legacy and shared auth entries."""
    import hashlib
    import secrets
    from datetime import datetime

    try:
        import bcrypt
        has_bcrypt = True
    except ImportError:
        has_bcrypt = False

    cursor = conn.cursor()
    role = user_data.get('role', 'student')

    # Create bcrypt hash for shared auth (primary), fall back to PBKDF2
    # Use minimal rounds/iterations for test speed — not security-relevant
    if has_bcrypt:
        bcrypt_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
        legacy_salt = None
    else:
        salt = secrets.token_hex(16)
        bcrypt_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), 1000
        ).hex()
        legacy_salt = salt

    # Insert user with shared auth fields
    cursor.execute("""
        INSERT INTO users (username, first_name, last_name, email, role,
                          password_hash, legacy_salt, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_data['username'],
        user_data.get('first_name', 'Test'),
        user_data.get('last_name', 'User'),
        user_data.get('email', f"{user_data['username']}@test.edu"),
        role,
        bcrypt_hash,
        legacy_salt,
        datetime.now().isoformat()
    ))
    user_id = cursor.lastrowid

    # Insert legacy account for backward compatibility
    legacy_salt_val = legacy_salt or secrets.token_hex(16)
    legacy_hash = hashlib.pbkdf2_hmac(
        'sha256', password.encode(), legacy_salt_val.encode(), 1000
    ).hex()
    cursor.execute("""
        INSERT INTO user_accounts (username, password_hash, salt, user_id, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
    """, (
        user_data['username'],
        legacy_hash,
        legacy_salt_val,
        user_id,
        datetime.now().isoformat()
    ))

    # Insert user_systems entry for shared auth
    cursor.execute("""
        INSERT OR IGNORE INTO user_systems (user_id, system_key, role)
        VALUES (?, 'university', ?)
    """, (user_id, role))

    conn.commit()
    return user_id
