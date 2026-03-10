"""
Tests for restaurant staff administration module.
Tests staff CRUD, schedules, performance tracking, and analytics.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile
import csv

# Import the module to test
from education_system.university_system.modules.domain.commerce.services.restaurant.staff import staff_administration

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute('''
        CREATE TABLE restaurant_staff (
            staff_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            hourly_rate REAL,
            email TEXT,
            phone TEXT,
            hire_date TEXT,
            status TEXT DEFAULT 'Active',
            emergency_contact TEXT,
            address TEXT,
            performance_score REAL DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_staff_schedules (
            schedule_id TEXT PRIMARY KEY,
            staff_id TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            break_duration INTEGER DEFAULT 30,
            status TEXT DEFAULT 'Scheduled',
            actual_start TEXT,
            actual_end TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            rating REAL DEFAULT 0,
            status TEXT DEFAULT 'Active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_purchase_orders (
            po_id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            order_date TEXT NOT NULL,
            expected_delivery TEXT,
            actual_delivery TEXT,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_audit_logs (
            log_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    # Insert test data
    today = datetime.now().strftime('%Y-%m-%d')

    cursor.execute('''
        INSERT INTO restaurant_staff VALUES
        ('STF001', 'John Doe', 'Chef', 15.50, 'john@example.com', '555-1234', ?, 'Active',
         'Jane Doe - 555-5678', '123 Main St', 8.5),
        ('STF002', 'Jane Smith', 'Server', 12.00, 'jane@example.com', '555-5555', ?, 'Active',
         'John Smith - 555-9999', '456 Oak Ave', 9.0)
    ''', (today, today))

    cursor.execute('''
        INSERT INTO restaurant_staff_schedules VALUES
        ('SCH001', 'STF001', ?, '09:00:00', '17:00:00', 30, 'Scheduled', NULL, NULL),
        ('SCH002', 'STF002', ?, '10:00:00', '18:00:00', 30, 'Completed', '10:00:00', '18:00:00')
    ''', (today, today))

    cursor.execute('''
        INSERT INTO restaurant_suppliers VALUES
        ('SUP001', 'Fresh Foods Ltd', 4.5, 'Active')
    ''')

    cursor.execute('''
        INSERT INTO restaurant_purchase_orders VALUES
        ('PO001', 'SUP001', ?, ?, ?, 100.00, 'Delivered')
    ''', (
        (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
        today,
        (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    ))

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {'id': 'user123', 'username': 'testuser', 'role': 'admin'}
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    return auth

class TestViewAllStaff:
    """Test viewing staff members"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_view_all_staff_all(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing all staff"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', return_value='1'):
            staff_administration.view_all_staff()

        captured = capsys.readouterr()
        assert 'STAFF MEMBERS' in captured.out
        assert 'John Doe' in captured.out
        assert 'Jane Smith' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_view_all_staff_by_role(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing staff filtered by role"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['3', 'Chef']):
            staff_administration.view_all_staff()

        captured = capsys.readouterr()
        assert 'John Doe' in captured.out

class TestAddNewStaff:
    """Test adding staff members"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_add_new_staff_success(self, mock_get_conn, mock_backup, mock_log, test_db, mock_auth, capsys):
        """Test successfully adding a new staff member"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        inputs = [
            'Bob Wilson',
            '2',  # Chef role
            '16.00',
            'bob@example.com',
            '555-7777',
            '789 Elm St',
            'Contact Person - 555-8888'
        ]

        with patch('builtins.input', side_effect=inputs):
            staff_administration.add_new_staff()

        captured = capsys.readouterr()
        assert 'Staff member added successfully' in captured.out
        assert 'Bob Wilson' in captured.out

    def test_add_new_staff_no_permission(self, mock_auth, capsys):
        """Test adding staff without permission"""
        mock_auth.check_permission.return_value = False
        staff_administration.set_auth(mock_auth)

        staff_administration.add_new_staff()

        captured = capsys.readouterr()
        assert "don't have permission" in captured.out

class TestUpdateStaffInfo:
    """Test updating staff information"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_update_staff_name(self, mock_get_conn, mock_backup, mock_log, test_db, mock_auth, capsys):
        """Test updating staff name"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['STF001', '1', 'John Updated']):
            staff_administration.update_staff_info()

        captured = capsys.readouterr()
        assert 'updated successfully' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_update_staff_not_found(self, mock_get_conn, mock_backup, test_db, mock_auth, capsys):
        """Test updating non-existent staff"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', return_value='STF999'):
            staff_administration.update_staff_info()

        captured = capsys.readouterr()
        assert 'not found' in captured.out

class TestDeleteStaff:
    """Test deleting/terminating staff"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_delete_staff_confirm(self, mock_get_conn, mock_backup, mock_log, test_db, mock_auth, capsys):
        """Test terminating staff with confirmation"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['STF001', 'DELETE']):
            staff_administration.delete_staff()

        captured = capsys.readouterr()
        assert 'terminated successfully' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_delete_staff_cancel(self, mock_get_conn, mock_backup, test_db, mock_auth, capsys):
        """Test cancelling staff deletion"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['STF001', 'cancel']):
            staff_administration.delete_staff()

        captured = capsys.readouterr()
        assert 'cancelled' in captured.out

class TestViewStaffSchedules:
    """Test viewing staff schedules"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_view_staff_schedules_today(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing today's schedules"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', return_value='1'):
            staff_administration.view_staff_schedules()

        captured = capsys.readouterr()
        assert 'STAFF SCHEDULES' in captured.out

class TestCreateStaffSchedule:
    """Test creating staff schedules"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_create_staff_schedule(self, mock_get_conn, mock_backup, mock_log, test_db, mock_auth, capsys):
        """Test creating a new schedule"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        inputs = [
            '1',  # Select first staff member
            tomorrow,
            '09:00',
            '17:00',
            '30'
        ]

        with patch('builtins.input', side_effect=inputs):
            staff_administration.create_staff_schedule()

        captured = capsys.readouterr()
        assert 'Schedule created successfully' in captured.out

class TestUpdateStaffSchedule:
    """Test updating staff schedules"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_update_schedule_start_time(self, mock_get_conn, mock_backup, mock_log, test_db, mock_auth, capsys):
        """Test updating schedule start time"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['SCH001', '1', '08:00']):
            staff_administration.update_staff_schedule()

        captured = capsys.readouterr()
        assert 'updated successfully' in captured.out

class TestDeleteStaffSchedule:
    """Test deleting staff schedules"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_delete_schedule_confirm(self, mock_get_conn, mock_backup, mock_log, test_db, mock_auth, capsys):
        """Test deleting schedule with confirmation"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['SCH001', 'DELETE']):
            staff_administration.delete_staff_schedule()

        captured = capsys.readouterr()
        assert 'deleted successfully' in captured.out

class TestViewScheduleConflicts:
    """Test viewing schedule conflicts"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_view_schedule_conflicts_none(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test when there are no conflicts"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        staff_administration.view_schedule_conflicts()

        captured = capsys.readouterr()
        assert 'SCHEDULE CONFLICTS' in captured.out

class TestPerformanceManagement:
    """Test performance tracking functions"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_view_performance_rankings(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing performance rankings"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        staff_administration.view_performance_rankings()

        captured = capsys.readouterr()
        assert 'PERFORMANCE RANKINGS' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_update_performance_scores(self, mock_get_conn, mock_backup, mock_log, test_db, mock_auth, capsys):
        """Test updating performance scores"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['STF001', '9.5', 'Great performance']):
            staff_administration.update_performance_scores()

        captured = capsys.readouterr()
        assert 'Performance score updated' in captured.out

class TestExportPerformanceReport:
    """Test performance report export"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_export_performance_report(self, mock_get_conn, test_db, mock_auth, capsys, tmp_path):
        """Test exporting performance report"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        os.chdir(tmp_path)

        staff_administration.export_performance_report()

        captured = capsys.readouterr()
        assert 'exported' in captured.out

        # Check CSV was created
        csv_files = list(tmp_path.glob('*.csv'))
        assert len(csv_files) > 0

class TestSupplierPerformance:
    """Test supplier performance tracking"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_supplier_performance(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing supplier performance"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        staff_administration.supplier_performance()

        captured = capsys.readouterr()
        assert 'SUPPLIER PERFORMANCE' in captured.out or 'performance' in captured.out.lower()

class TestStaffAnalytics:
    """Test staff analytics function"""

    def test_staff_analytics_available(self):
        """Test that staff_analytics function exists"""
        assert hasattr(staff_administration, 'staff_analytics')

class TestQueryPerformance:
    """Test query performance analysis"""

    @patch('university_system.modules.domain.commerce.services.restaurant.staff.staff_administration.get_db_connection')
    def test_analyze_query_performance(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test query performance analysis"""
        staff_administration.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        staff_administration.analyze_query_performance()

        captured = capsys.readouterr()
        assert 'QUERY PERFORMANCE' in captured.out or 'performance' in captured.out.lower()

class TestSetAuth:
    """Test authentication setup"""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance"""
        staff_administration.set_auth(mock_auth)
        assert staff_administration.auth == mock_auth

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
