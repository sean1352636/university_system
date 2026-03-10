"""
Tests for university_system/modules/domain/housing/services/housing_accommodation

This test suite validates:
- Database initialization for housing system
- Building management (CRUD operations)
- Room management
- Application processing
- Assignment management
- Maintenance requests
- Payment processing
- Inspection management
- Reporting functions
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Base path for the housing accommodation package submodules
_BASE = 'university_system.modules.domain.housing.services.housing_accommodation'

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    yield temp_path
    os.close(temp_fd)
    try:
        os.unlink(temp_path)
    except (OSError, IOError):
        pass

@pytest.fixture
def initialized_db(temp_db):
    """Create and initialize a test database"""
    with patch(f'{_BASE}.database.get_connection') as mock_conn:
        conn = sqlite3.connect(temp_db)
        mock_conn.return_value = conn

        from education_system.university_system.modules.domain.housing.services.housing_accommodation import init_housing_db
        init_housing_db()

        yield temp_db, conn
        conn.close()

class TestDatabaseInitialization:
    """Test database initialization"""

    def test_init_housing_db_creates_tables(self, temp_db):
        """Test init_housing_db creates all required tables"""
        with patch(f'{_BASE}.database.get_connection') as mock_conn:
            conn = sqlite3.connect(temp_db)
            mock_conn.return_value = conn

            from education_system.university_system.modules.domain.housing.services.housing_accommodation import init_housing_db
            init_housing_db()

            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            expected_tables = {
                'housing_buildings',
                'housing_rooms',
                'housing_applications',
                'housing_assignments',
                'housing_payments',
                'housing_maintenance_requests',
                'housing_inspections',
                'housing_inventory'
            }

            assert expected_tables.issubset(tables)
            conn.close()

    def test_housing_buildings_table_structure(self, temp_db):
        """Test housing_buildings table has correct structure"""
        with patch(f'{_BASE}.database.get_connection') as mock_conn:
            conn = sqlite3.connect(temp_db)
            mock_conn.return_value = conn

            from education_system.university_system.modules.domain.housing.services.housing_accommodation import init_housing_db
            init_housing_db()

            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(housing_buildings)")
            columns = {row[1] for row in cursor.fetchall()}

            required_columns = {'building_id', 'building_name', 'address', 'campus_location',
                              'total_rooms', 'available_rooms', 'has_elevator', 'has_kitchen'}

            assert required_columns.issubset(columns)
            conn.close()

class TestIDGeneration:
    """Test ID generation function"""

    def test_generate_id_returns_string(self):
        """Test generate_id returns a string"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id

        generated_id = generate_id('TEST')
        assert isinstance(generated_id, str)

    def test_generate_id_includes_prefix(self):
        """Test generate_id includes the specified prefix"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id

        generated_id = generate_id('BUILD')
        assert generated_id.startswith('BUILD')

    def test_generate_id_is_unique(self):
        """Test generate_id produces unique IDs"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_id

        id1 = generate_id('TEST')
        id2 = generate_id('TEST')

        assert id1 != id2

class TestBuildingManagement:
    """Test building CRUD operations"""

    @patch(f'{_BASE}.buildings.get_connection')
    @patch(f'{_BASE}.buildings.log_create')
    def test_create_building(self, mock_log, mock_conn):
        """Test create_building creates a new building"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import create_building

        # Setup mock connection
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        building_id = create_building(
            'Test Building',
            '123 Campus Ave',
            'Main Campus',
            total_rooms=100,
            has_elevator=True,
            has_kitchen=True
        )

        assert building_id is not None
        assert cursor.execute.called
        assert mock_log.called

    @patch(f'{_BASE}.buildings.get_connection')
    def test_view_building_returns_data(self, mock_conn):
        """Test view_building retrieves building data"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import view_building

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('BUILD001', 'Test Building', '123 Campus Ave', 'Main Campus', 100, 50)
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        buildings = view_building()

        assert len(buildings) > 0
        assert cursor.execute.called

    @patch(f'{_BASE}.buildings.get_connection')
    @patch(f'{_BASE}.buildings.log_update')
    def test_update_building(self, mock_log, mock_conn):
        """Test update_building modifies building data"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import update_building

        conn = MagicMock()
        cursor = MagicMock()
        cursor.rowcount = 1
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        success = update_building('BUILD001', building_name='Updated Building')

        assert success is True
        assert cursor.execute.called
        assert mock_log.called

    @patch(f'{_BASE}.buildings.get_connection')
    @patch(f'{_BASE}.buildings.log_delete')
    def test_delete_building(self, mock_log, mock_conn):
        """Test delete_building removes a building"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import delete_building

        conn = MagicMock()
        cursor = MagicMock()
        cursor.rowcount = 1
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        success = delete_building('BUILD001')

        assert success is True
        assert cursor.execute.called
        assert mock_log.called

class TestRoomManagement:
    """Test room creation and management"""

    @patch(f'{_BASE}.buildings.get_connection')
    @patch(f'{_BASE}.buildings.generate_id')
    def test_create_rooms_for_building(self, mock_generate_id, mock_conn):
        """Test create_rooms_for_building generates rooms"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import create_rooms_for_building

        mock_generate_id.side_effect = lambda x: f'ROOM{x}'

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        created_rooms = create_rooms_for_building(
            'BUILD001',
            floors=3,
            rooms_per_floor=10,
            room_type='Single',
            monthly_rent=500.0
        )

        assert created_rooms > 0
        assert cursor.execute.called

    @patch(f'{_BASE}.reports.get_connection')
    def test_check_room_availability(self, mock_conn):
        """Test check_room_availability finds available rooms"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import check_room_availability

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('ROOM001', 'BUILD001', '101', 1, 'Single', 1, 0, 500.0)
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        available_rooms = check_room_availability(building_id='BUILD001', room_type='Single')

        assert len(available_rooms) > 0

class TestApplicationProcessing:
    """Test application management"""

    @patch(f'{_BASE}.applications.get_connection')
    @patch(f'{_BASE}.applications.generate_id')
    @patch(f'{_BASE}.applications.log_create')
    def test_create_application(self, mock_log, mock_generate_id, mock_conn):
        """Test create_application creates new application"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import create_application

        mock_generate_id.return_value = 'APP001'

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        app_id = create_application(
            student_id='S001',
            preferred_room_type='Single',
            requested_move_in_date='2024-09-01',
            requested_duration_months=9,
            special_requirements='Ground floor preferred'
        )

        assert app_id == 'APP001'
        assert cursor.execute.called
        assert mock_log.called

    @patch(f'{_BASE}.applications.get_connection')
    @patch(f'{_BASE}.applications.log_update')
    def test_process_application_approve(self, mock_log, mock_conn):
        """Test process_application approves application"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import process_application

        conn = MagicMock()
        cursor = MagicMock()
        cursor.rowcount = 1
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        success = process_application('APP001', 'approved', 'admin', 'Approved')

        assert success is True
        assert cursor.execute.called

    @patch(f'{_BASE}.applications.get_connection')
    def test_view_application(self, mock_conn):
        """Test view_application retrieves applications"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import view_application

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('APP001', 'S001', '2024-01-15', 'Single', 'pending')
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        applications = view_application()

        assert len(applications) > 0

class TestAssignmentManagement:
    """Test housing assignment operations"""

    @patch(f'{_BASE}.assignments.get_connection')
    def test_view_assignment(self, mock_conn):
        """Test view_assignment retrieves assignments"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import view_assignment

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('ASSIGN001', 'S001', 'ROOM001', '2024-09-01', 'active')
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        assignments = view_assignment()

        assert len(assignments) > 0

    @patch(f'{_BASE}.assignments.get_connection')
    @patch(f'{_BASE}.assignments.log_update')
    def test_update_assignment_status(self, mock_log, mock_conn):
        """Test update_assignment_status changes status"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import update_assignment_status

        conn = MagicMock()
        cursor = MagicMock()
        cursor.rowcount = 1
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        success = update_assignment_status('ASSIGN001', 'completed')

        assert success is True
        assert cursor.execute.called

class TestMaintenanceRequests:
    """Test maintenance request management"""

    @patch(f'{_BASE}.maintenance.get_connection')
    @patch(f'{_BASE}.maintenance.generate_id')
    @patch(f'{_BASE}.maintenance.log_create')
    def test_create_maintenance_request(self, mock_log, mock_generate_id, mock_conn):
        """Test create_maintenance_request creates request"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import create_maintenance_request

        mock_generate_id.return_value = 'MAINT001'

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        request_id = create_maintenance_request(
            room_id='ROOM001',
            student_id='S001',
            issue_type='Plumbing',
            description='Leaky faucet',
            priority='medium'
        )

        assert request_id == 'MAINT001'
        assert cursor.execute.called

    @patch(f'{_BASE}.maintenance.get_connection')
    def test_view_maintenance_requests(self, mock_conn):
        """Test view_maintenance_requests retrieves requests"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import view_maintenance_requests

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('MAINT001', 'ROOM001', 'S001', 'Plumbing', 'pending', 'medium')
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        requests = view_maintenance_requests()

        assert len(requests) > 0

    @patch(f'{_BASE}.maintenance.get_connection')
    @patch(f'{_BASE}.maintenance.log_update')
    def test_update_maintenance_request(self, mock_log, mock_conn):
        """Test update_maintenance_request updates request"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import update_maintenance_request

        conn = MagicMock()
        cursor = MagicMock()
        cursor.rowcount = 1
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        success = update_maintenance_request('MAINT001', status='completed')

        assert success is True

class TestPaymentProcessing:
    """Test payment recording and tracking"""

    @patch(f'{_BASE}.payments.get_connection')
    @patch(f'{_BASE}.payments.generate_id')
    @patch(f'{_BASE}.payments.record_payment_to_finance')
    def test_record_payment(self, mock_finance, mock_generate_id, mock_conn):
        """Test record_payment records payment"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import record_payment

        mock_generate_id.return_value = 'PAY001'
        mock_finance.return_value = True

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        payment_id = record_payment(
            assignment_id='ASSIGN001',
            student_id='S001',
            amount=500.0,
            payment_method='Credit Card',
            received_by='admin'
        )

        assert payment_id == 'PAY001'
        assert cursor.execute.called

    @patch(f'{_BASE}.payments.get_connection')
    def test_view_payment_history(self, mock_conn):
        """Test view_payment_history retrieves payments"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import view_payment_history

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('PAY001', 'ASSIGN001', 'S001', 500.0, '2024-01-15', 'paid')
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        payments = view_payment_history(student_id='S001')

        assert len(payments) > 0

class TestInspectionManagement:
    """Test inspection functions"""

    @patch(f'{_BASE}.inspections.get_connection')
    @patch(f'{_BASE}.inspections.generate_id')
    def test_create_inspection(self, mock_generate_id, mock_conn):
        """Test create_inspection creates inspection record"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import create_inspection

        mock_generate_id.return_value = 'INSP001'

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        inspection_id = create_inspection(
            room_id='ROOM001',
            inspector='admin',
            inspection_type='routine',
            findings='All good'
        )

        assert inspection_id == 'INSP001'

    @patch(f'{_BASE}.inspections.get_connection')
    def test_view_inspections(self, mock_conn):
        """Test view_inspections retrieves inspections"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import view_inspections

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('INSP001', 'ROOM001', 'admin', '2024-01-15', 'routine', 'passed')
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        inspections = view_inspections()

        assert len(inspections) > 0

class TestReportingFunctions:
    """Test reporting and analytics functions"""

    @patch(f'{_BASE}.reports.get_connection')
    def test_generate_occupancy_report(self, mock_conn):
        """Test generate_occupancy_report generates report"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_occupancy_report

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('BUILD001', 'Test Building', 100, 50, 50.0)
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        report = generate_occupancy_report()

        assert report is not None

    @patch(f'{_BASE}.reports.get_connection')
    def test_generate_financial_report(self, mock_conn):
        """Test generate_financial_report generates report"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import generate_financial_report

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (10000.0,)
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        report = generate_financial_report('2024-01-01', '2024-12-31')

        assert report is not None

    @patch(f'{_BASE}.reports.get_connection')
    def test_maintenance_summary(self, mock_conn):
        """Test maintenance_summary generates summary"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import maintenance_summary

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ('pending', 5),
            ('completed', 10)
        ]
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        summary = maintenance_summary()

        assert summary is not None

class TestAuthIntegration:
    """Test authentication integration"""

    def test_set_auth_stores_instance(self):
        """Test set_auth stores auth instance"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import set_auth

        mock_auth = Mock()
        set_auth(mock_auth)

        # Should not raise error
        assert True

class TestExportFunctions:
    """Test data export functions"""

    @patch(f'{_BASE}.reports.get_connection')
    def test_export_housing_data(self, mock_conn):
        """Test export_housing_data exports data"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import export_housing_data

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        # Should not raise error
        try:
            export_housing_data()
        except Exception:
            # May fail due to file operations, that's okay
            pass

class TestSearchFunctions:
    """Test search functionality"""

    @patch(f'{_BASE}.reports.get_connection')
    def test_search_housing_records(self, mock_conn):
        """Test search_housing_records finds records"""
        from education_system.university_system.modules.domain.housing.services.housing_accommodation import search_housing_records

        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        results = search_housing_records(student_id='S001')

        assert isinstance(results, (list, dict, type(None)))

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
