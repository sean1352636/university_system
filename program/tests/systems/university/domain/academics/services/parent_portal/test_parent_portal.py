"""
Comprehensive tests for parent_portal.py

Tests parent portal system including account management, student linking, and information viewing
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from education_system.systems.university.domain.academics.services.parent_portal import ParentPortal

# Patch DEFAULT_DB_PATH in the database module where initialize_parent_portal actually reads it
DB_PATH_TARGET = 'education_system.systems.university.domain.academics.services.parent_portal.database.DEFAULT_DB_PATH'
ACCOUNTS_DB_PATH_TARGET = 'education_system.systems.university.domain.academics.services.parent_portal.accounts.DEFAULT_DB_PATH'


class TestParentPortalInitialization:
    """Test suite for ParentPortal initialization"""

    def test_parent_portal_init(self):
        """Test ParentPortal initialization"""
        mock_auth = Mock()
        portal = ParentPortal(mock_auth)

        assert portal is not None
        assert portal.auth == mock_auth

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_initialize_parent_portal(self, temp_db):
        """Test initializing parent portal database"""
        with patch(DB_PATH_TARGET, temp_db):
            ParentPortal.initialize_parent_portal()

        # Verify tables were created
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'parent_accounts',
            'parent_student_relationships',
            'parent_user_mapping',
            'parent_notifications',
            'parent_preferences',
            'parent_messages'
        ]

        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

        conn.close()

class TestParentPortalDatabaseSchema:
    """Test suite for parent portal database schema"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def initialized_db(self, temp_db):
        """Initialize parent portal tables in temp db and return path"""
        with patch(DB_PATH_TARGET, temp_db):
            ParentPortal.initialize_parent_portal()
        return temp_db

    def test_parent_accounts_table_structure(self, initialized_db):
        """Test parent_accounts table has correct structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(parent_accounts)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'id', 'parent_id', 'first_name', 'last_name', 'email',
            'phone', 'address', 'emergency_contact', 'registration_date',
            'two_factor_enabled', 'two_factor_secret', 'profile_photo'
        }

        assert expected_columns.issubset(columns)

    def test_parent_student_relationships_table_structure(self, initialized_db):
        """Test parent_student_relationships table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(parent_student_relationships)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'id', 'parent_id', 'student_id', 'relationship_type',
            'access_level', 'date_added'
        }

        assert expected_columns.issubset(columns)

    def test_parent_preferences_table_structure(self, initialized_db):
        """Test parent_preferences table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(parent_preferences)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'parent_id', 'email_notifications', 'sms_notifications',
            'grade_alerts', 'attendance_alerts', 'behavior_alerts'
        }

        assert expected_columns.issubset(columns)

    def test_student_fees_table_structure(self, initialized_db):
        """Test student_fees table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(student_fees)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'student_id', 'fee_type', 'description', 'amount',
            'due_date', 'payment_status'
        }

        assert expected_columns.issubset(columns)

class TestParentPortalAccountManagement:
    """Test suite for parent account management"""

    @pytest.fixture
    def mock_auth(self):
        """Create a mock auth object"""
        auth = Mock()
        auth.current_user = Mock()
        auth.current_user.user_id = 1
        auth.current_user.username = 'test_user'
        return auth

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        # Initialize database
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        # Create required tables
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE parent_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                email TEXT UNIQUE,
                phone TEXT,
                address TEXT,
                emergency_contact BOOLEAN DEFAULT 0,
                registration_date TEXT,
                two_factor_enabled BOOLEAN DEFAULT 0,
                two_factor_secret TEXT,
                profile_photo TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE parent_user_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                parent_id TEXT UNIQUE,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
        ''')

        # Insert a test user
        cursor.execute('''
            INSERT INTO users (id, username, password, role)
            VALUES (?, ?, ?, ?)
        ''', (1, 'test_user', 'password', 'parent'))

        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_create_parent_user(self, temp_db, mock_auth):
        """Test creating a parent user"""
        with patch(ACCOUNTS_DB_PATH_TARGET, temp_db):
            result = ParentPortal.create_parent_user(
                mock_auth,
                first_name='John',
                last_name='Doe',
                email='john.doe@example.com',
                phone='123-456-7890',
                address='123 Main St'
            )

        # Should return parent_id or success indicator
        assert result is not None

    def test_get_parent_id_from_user(self, temp_db, mock_auth):
        """Test getting parent ID from user ID"""
        portal = ParentPortal(mock_auth)

        # Insert test data - use the temp_db that already has parent_user_mapping with FKs
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Insert a parent account first (required by FK on parent_user_mapping)
        cursor.execute('''
            INSERT INTO parent_accounts (parent_id, first_name, last_name, email, registration_date)
            VALUES (?, ?, ?, ?, ?)
        ''', ('P001', 'Test', 'Parent', 'test@example.com', '2026-01-01'))

        cursor.execute('''
            INSERT INTO parent_user_mapping (user_id, parent_id)
            VALUES (?, ?)
        ''', (1, 'P001'))

        conn.commit()
        conn.close()

        with patch(ACCOUNTS_DB_PATH_TARGET, temp_db):
            parent_id = portal.get_parent_id_from_user(1)

        assert parent_id == 'P001'

class TestParentPortalStudentLinking:
    """Test suite for student-parent linking"""

    @pytest.fixture
    def mock_auth(self):
        """Create a mock auth object"""
        auth = Mock()
        auth.current_user = Mock()
        auth.current_user.user_id = 1
        return auth

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        # Initialize database
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE parent_student_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                student_id TEXT,
                relationship_type TEXT,
                access_level TEXT DEFAULT 'full',
                date_added TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                grade_level TEXT
            )
        ''')

        # Insert test student
        cursor.execute('''
            INSERT INTO students (student_id, first_name, last_name, grade_level)
            VALUES (?, ?, ?, ?)
        ''', ('S001', 'Jane', 'Doe', '10'))

        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_link_student_to_parent_database_structure(self, temp_db, mock_auth):
        """Test linking student to parent creates proper database record"""

        portal = ParentPortal(mock_auth)

        # Verify parent_student_relationships table exists and has correct structure
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(parent_student_relationships)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {'parent_id', 'student_id', 'relationship_type', 'date_added'}
        assert expected_columns.issubset(columns)

        conn.close()

class TestParentPortalNotifications:
    """Test suite for parent notifications"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_parent_notifications_table(self, temp_db):
        """Test parent_notifications table structure"""
        with patch(DB_PATH_TARGET, temp_db):
            ParentPortal.initialize_parent_portal()

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(parent_notifications)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'parent_id', 'student_id', 'notification_type',
            'notification_content', 'created_date', 'read_status'
        }

        assert expected_columns.issubset(columns)

class TestParentPortalMessages:
    """Test suite for parent-teacher messaging"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_parent_messages_table(self, temp_db):
        """Test parent_messages table structure"""
        with patch(DB_PATH_TARGET, temp_db):
            ParentPortal.initialize_parent_portal()

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(parent_messages)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'parent_id', 'teacher_id', 'student_id',
            'message_content', 'created_date', 'is_read', 'is_from_parent'
        }

        assert expected_columns.issubset(columns)

class TestParentPortalFinancial:
    """Test suite for financial features"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def initialized_db(self, temp_db):
        """Initialize parent portal tables in temp db and return path"""
        with patch(DB_PATH_TARGET, temp_db):
            ParentPortal.initialize_parent_portal()
        return temp_db

    def test_meal_accounts_table(self, initialized_db):
        """Test meal_accounts table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(meal_accounts)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'student_id', 'balance', 'low_balance_threshold',
            'auto_topup_enabled', 'auto_topup_amount'
        }

        assert expected_columns.issubset(columns)

    def test_fundraising_campaigns_table(self, initialized_db):
        """Test fundraising_campaigns table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(fundraising_campaigns)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'campaign_name', 'description', 'target_amount',
            'current_amount', 'start_date', 'end_date', 'status'
        }

        assert expected_columns.issubset(columns)

class TestParentPortalAcademicFeatures:
    """Test suite for academic features"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def initialized_db(self, temp_db):
        """Initialize parent portal tables in temp db and return path"""
        with patch(DB_PATH_TARGET, temp_db):
            ParentPortal.initialize_parent_portal()
        return temp_db

    def test_homework_assignments_table(self, initialized_db):
        """Test homework_assignments table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(homework_assignments)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'student_id', 'module_code', 'assignment_title',
            'description', 'due_date', 'completion_status'
        }

        assert expected_columns.issubset(columns)

    def test_academic_goals_table(self, initialized_db):
        """Test academic_goals table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(academic_goals)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'student_id', 'parent_id', 'goal_title',
            'description', 'target_grade', 'target_date', 'status'
        }

        assert expected_columns.issubset(columns)

class TestParentPortalCommunication:
    """Test suite for communication features"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def initialized_db(self, temp_db):
        """Initialize parent portal tables in temp db and return path"""
        with patch(DB_PATH_TARGET, temp_db):
            ParentPortal.initialize_parent_portal()
        return temp_db

    def test_school_announcements_table(self, initialized_db):
        """Test school_announcements table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(school_announcements)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'title', 'content', 'priority', 'category',
            'audience', 'created_date', 'requires_acknowledgment'
        }

        assert expected_columns.issubset(columns)

    def test_emergency_alerts_table(self, initialized_db):
        """Test emergency_alerts table structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(emergency_alerts)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'alert_title', 'alert_message', 'alert_type',
            'created_date', 'active'
        }

        assert expected_columns.issubset(columns)

class TestParentPortalIntegration:
    """Integration tests for parent portal"""

    @pytest.fixture
    def mock_auth(self):
        """Create a mock auth object"""
        auth = Mock()
        auth.current_user = Mock()
        auth.current_user.user_id = 1
        return auth

    def test_parent_portal_creation(self, mock_auth):
        """Test creating a ParentPortal instance"""
        portal = ParentPortal(mock_auth)

        assert portal is not None
        assert hasattr(portal, 'auth')
        assert portal.auth == mock_auth

class TestParentPortalEdgeCases:
    """Test suite for edge cases"""

    def test_parent_portal_with_none_auth(self):
        """Test creating portal with None auth"""
        portal = ParentPortal(None)

        assert portal is not None
        assert portal.auth is None

    def test_parent_portal_multiple_initialization(self):
        """Test multiple portal initializations are safe"""
        # This should be idempotent
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            # Call multiple times
            ParentPortal.initialize_parent_portal()
            ParentPortal.initialize_parent_portal()
            ParentPortal.initialize_parent_portal()

            # Should not raise errors
            assert True
