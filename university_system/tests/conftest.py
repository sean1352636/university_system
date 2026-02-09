"""
Pytest configuration and fixtures for the University System test suite.

This module provides:
- Authentication initialization before test collection
- Common fixtures for database, authentication, and GUI testing
- Test configuration and markers
"""

import os
import sys
import sqlite3
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

    # Initialize authentication system before any imports that might need it
    _initialize_test_auth()


def _initialize_test_auth():
    """Initialize the authentication system for test collection.

    This prevents AuthenticationNotInitializedError during module imports.
    """
    try:
        # Create a temporary database for auth initialization
        temp_dir = tempfile.mkdtemp(prefix="university_test_")
        temp_db = os.path.join(temp_dir, "test_auth.db")

        # Create minimal database schema for auth
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Create required tables
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                role TEXT DEFAULT 'student',
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
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_token TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT,
                expires_at TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                permission TEXT NOT NULL,
                UNIQUE(role, permission)
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                timestamp TEXT
            );
        """)
        conn.commit()
        conn.close()

        # Initialize auth with the temporary database
        from university_system.infrastructure.shared_context import (
            initialize_auth,
            is_auth_initialized,
            set_auth
        )

        if not is_auth_initialized():
            initialize_auth(temp_db)

    except Exception as e:
        # If initialization fails, create a mock auth
        print(f"Warning: Could not initialize test auth: {e}")
        _setup_mock_auth()


def _setup_mock_auth():
    """Set up a mock authentication system as fallback."""
    try:
        from university_system.infrastructure.shared_context import set_auth
        from university_system.infrastructure.auth import UserAuth

        # Create a mock UserAuth
        mock_auth = MagicMock(spec=UserAuth)
        mock_auth.is_logged_in.return_value = False
        mock_auth.current_user = None
        mock_auth.check_permission.return_value = True
        mock_auth.get_current_user.return_value = None

        set_auth(mock_auth)
    except Exception as e:
        print(f"Warning: Could not set up mock auth: {e}")


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary database for the entire test session."""
    temp_dir = tempfile.mkdtemp(prefix="university_test_session_")
    db_path = os.path.join(temp_dir, "test_session.db")

    # Create the database with required schema
    _create_test_database(db_path)

    yield db_path

    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture
def temp_db():
    """Create a temporary database for a single test."""
    temp_dir = tempfile.mkdtemp(prefix="university_test_")
    db_path = os.path.join(temp_dir, "test.db")

    _create_test_database(db_path)

    yield db_path

    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


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

    # Core user tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            role TEXT DEFAULT 'student',
            department TEXT,
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

        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            UNIQUE(role, permission)
        );

        -- Student tables
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            date_of_birth TEXT,
            enrollment_date TEXT,
            graduation_date TEXT,
            major TEXT,
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
            course_code TEXT UNIQUE NOT NULL,
            course_name TEXT NOT NULL,
            description TEXT,
            credits INTEGER DEFAULT 3,
            department TEXT,
            instructor_id INTEGER,
            max_enrollment INTEGER DEFAULT 30,
            current_enrollment INTEGER DEFAULT 0,
            semester TEXT,
            year INTEGER,
            schedule TEXT,
            location TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (instructor_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            enrollment_date TEXT,
            status TEXT DEFAULT 'enrolled',
            grade TEXT,
            grade_points REAL,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            UNIQUE(student_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            assignment_name TEXT,
            assignment_type TEXT,
            score REAL,
            max_score REAL DEFAULT 100,
            weight REAL DEFAULT 1.0,
            grade_date TEXT,
            comments TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
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
        INSERT OR IGNORE INTO permissions (role, permission) VALUES
            ('admin', 'all'),
            ('admin', 'view_students'),
            ('admin', 'edit_students'),
            ('admin', 'delete_students'),
            ('admin', 'view_courses'),
            ('admin', 'edit_courses'),
            ('admin', 'view_grades'),
            ('admin', 'edit_grades'),
            ('admin', 'manage_users'),
            ('instructor', 'view_students'),
            ('instructor', 'view_courses'),
            ('instructor', 'edit_grades'),
            ('instructor', 'view_grades'),
            ('staff', 'view_students'),
            ('staff', 'view_courses'),
            ('student', 'view_own_grades'),
            ('student', 'view_courses');
    """)

    conn.commit()
    conn.close()


@pytest.fixture
def mock_auth():
    """Provide a mock authentication object."""
    auth = MagicMock()
    auth.current_user = {
        'id': 1,
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
    """Helper to insert a test user with account."""
    import hashlib
    import secrets
    from datetime import datetime

    cursor = conn.cursor()

    # Insert user
    cursor.execute("""
        INSERT INTO users (username, first_name, last_name, email, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_data['username'],
        user_data.get('first_name', 'Test'),
        user_data.get('last_name', 'User'),
        user_data.get('email', f"{user_data['username']}@test.edu"),
        user_data.get('role', 'student'),
        datetime.now().isoformat()
    ))
    user_id = cursor.lastrowid

    # Create password hash
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        100000
    ).hex()

    # Insert account
    cursor.execute("""
        INSERT INTO user_accounts (username, password_hash, salt, user_id, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
    """, (
        user_data['username'],
        password_hash,
        salt,
        user_id,
        datetime.now().isoformat()
    ))

    conn.commit()
    return user_id
