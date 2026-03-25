"""
Tests for the Commerce Reservation System module.
Tests table management, reservations, QR code generation, and analytics.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from education_system.university_system.modules.domain.commerce.services.restaurant.customer import reservation_system

@pytest.fixture
def mock_auth():
    """Create a mock authentication instance."""
    auth = Mock()
    auth.current_user = {
        'id': 'USER001',
        'username': 'testuser',
        'role': 'admin'
    }
    auth.check_permission = Mock(return_value=True)
    auth.is_logged_in = Mock(return_value=True)
    return auth

@pytest.fixture
def mock_db_connection(tmp_path):
    """Create a temporary in-memory database for testing."""
    db_path = tmp_path / "test_restaurant.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute('''
        CREATE TABLE restaurant_tables (
            table_id TEXT PRIMARY KEY,
            capacity INTEGER NOT NULL,
            status TEXT DEFAULT 'Available',
            current_order_id TEXT,
            location TEXT,
            table_type TEXT,
            created_date TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_reservations (
            reservation_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            table_id TEXT NOT NULL,
            reservation_date TEXT NOT NULL,
            reservation_time TEXT NOT NULL,
            party_size INTEGER NOT NULL,
            status TEXT DEFAULT 'Active',
            special_requests TEXT,
            created_at TEXT,
            FOREIGN KEY (table_id) REFERENCES restaurant_tables(table_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            dietary_restrictions TEXT,
            loyalty_points INTEGER DEFAULT 0,
            loyalty_tier TEXT DEFAULT 'Bronze',
            birthday TEXT,
            registration_date TEXT,
            last_visit TEXT,
            total_spent REAL DEFAULT 0,
            visit_count INTEGER DEFAULT 0,
            preferences TEXT,
            address TEXT,
            emergency_contact TEXT,
            notes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_qr_codes (
            qr_id TEXT PRIMARY KEY,
            table_id TEXT NOT NULL,
            qr_data TEXT NOT NULL,
            created_date TEXT,
            last_used TEXT,
            usage_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (table_id) REFERENCES restaurant_tables(table_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            table_id TEXT,
            order_time TEXT,
            total_price REAL,
            status TEXT,
            payment_method TEXT,
            notes TEXT
        )
    ''')

    conn.commit()
    return conn

class TestTableManagement:
    """Tests for table management functionality."""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    def test_view_all_tables(self, mock_get_conn, mock_db_connection, capsys):
        """Test viewing all tables."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test tables
        tables = [
            ('T001', 2, 'Available', None, 'Main Dining', 'Standard'),
            ('T002', 4, 'Occupied', 'ORD001', 'Main Dining', 'Standard'),
            ('T003', 6, 'Reserved', None, 'Patio', 'Outdoor'),
        ]

        for table in tables:
            cursor.execute('''
                INSERT INTO restaurant_tables
                (table_id, capacity, status, current_order_id, location, table_type, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (*table, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Execute
        reservation_system.view_all_tables()

        # Verify
        captured = capsys.readouterr()
        assert "TABLE STATUS" in captured.out
        assert "T001" in captured.out
        assert "T002" in captured.out
        assert "T003" in captured.out
        assert "Total tables: 3" in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.log_audit_action')
    @patch('builtins.input')
    def test_add_new_table(self, mock_input, mock_audit, mock_backup,
                          mock_get_conn, mock_db_connection, mock_auth):
        """Test adding a new table."""
        # Setup
        reservation_system.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection

        # Mock user inputs
        mock_input.side_effect = [
            '4',  # capacity
            'Main Dining',  # location
            '1'  # table type (Standard)
        ]

        # Execute
        reservation_system.add_new_table()

        # Verify
        cursor = mock_db_connection.cursor()
        cursor.execute("SELECT * FROM restaurant_tables WHERE table_id = 'T001'")
        table = cursor.fetchone()

        assert table is not None
        assert table[1] == 4  # capacity
        assert table[4] == 'Main Dining'  # location
        assert table[5] == 'Standard'  # table_type
        mock_audit.assert_called_once()

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.log_audit_action')
    @patch('builtins.input')
    def test_update_table_status(self, mock_input, mock_audit, mock_backup,
                                 mock_get_conn, mock_db_connection, mock_auth):
        """Test updating table status."""
        # Setup
        reservation_system.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test table
        cursor.execute('''
            INSERT INTO restaurant_tables
            (table_id, capacity, status, current_order_id, location, table_type, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('T001', 4, 'Available', None, 'Main Dining', 'Standard',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'T001',  # table_id
            '2',  # Update status
            '2'  # Occupied
        ]

        # Execute
        reservation_system.update_table()

        # Verify
        cursor.execute("SELECT status FROM restaurant_tables WHERE table_id = 'T001'")
        status = cursor.fetchone()[0]
        assert status == 'Occupied'

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.log_audit_action')
    @patch('builtins.input')
    def test_delete_table(self, mock_input, mock_audit, mock_backup,
                         mock_get_conn, mock_db_connection, mock_auth):
        """Test deleting a table."""
        # Setup
        reservation_system.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test table
        cursor.execute('''
            INSERT INTO restaurant_tables
            (table_id, capacity, status, current_order_id, location, table_type, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('T001', 4, 'Available', None, 'Main Dining', 'Standard',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'T001',  # table_id
            'DELETE'  # confirmation
        ]

        # Execute
        reservation_system.delete_table()

        # Verify
        cursor.execute("SELECT * FROM restaurant_tables WHERE table_id = 'T001'")
        table = cursor.fetchone()
        assert table is None
        mock_audit.assert_called_once()

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('builtins.input')
    def test_delete_occupied_table_fails(self, mock_input, mock_get_conn,
                                        mock_db_connection, mock_auth, capsys):
        """Test that deleting an occupied table fails."""
        # Setup
        reservation_system.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add occupied table
        cursor.execute('''
            INSERT INTO restaurant_tables
            (table_id, capacity, status, current_order_id, location, table_type, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('T001', 4, 'Occupied', 'ORD001', 'Main Dining', 'Standard',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = ['T001']

        # Execute
        reservation_system.delete_table()

        # Verify
        captured = capsys.readouterr()
        assert "Cannot delete occupied table" in captured.out

class TestReservationManagement:
    """Tests for reservation management functionality."""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.log_audit_action')
    @patch('builtins.input')
    def test_create_reservation(self, mock_input, mock_audit, mock_backup,
                                mock_get_conn, mock_db_connection, mock_auth):
        """Test creating a new reservation."""
        # Setup
        reservation_system.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test customer
        cursor.execute('''
            INSERT INTO restaurant_customers
            (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
             loyalty_tier, birthday, registration_date, last_visit, total_spent,
             visit_count, preferences, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('CUST000001', 'Test Customer', 'test@example.com', '1234567890',
              'None', 0, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              None, 0, 0, None, None, None, None))

        # Add test table
        cursor.execute('''
            INSERT INTO restaurant_tables
            (table_id, capacity, status, current_order_id, location, table_type, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('T001', 4, 'Available', None, 'Main Dining', 'Standard',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Mock user inputs
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        mock_input.side_effect = [
            'CUST000001',  # customer_id
            tomorrow,  # reservation_date
            '19:00',  # reservation_time
            '4',  # party_size
            '1',  # table choice
            'Window seat please'  # special_requests
        ]

        # Execute
        reservation_system.create_reservation()

        # Verify
        cursor.execute("SELECT * FROM restaurant_reservations")
        reservation = cursor.fetchone()

        assert reservation is not None
        assert reservation[1] == 'CUST000001'  # customer_id
        assert reservation[2] == 'T001'  # table_id
        assert reservation[5] == 4  # party_size

        # Check table status updated to Reserved
        cursor.execute("SELECT status FROM restaurant_tables WHERE table_id = 'T001'")
        status = cursor.fetchone()[0]
        assert status == 'Reserved'
        mock_audit.assert_called_once()

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.backup_before_operation')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.log_audit_action')
    @patch('builtins.input')
    def test_cancel_reservation(self, mock_input, mock_audit, mock_backup,
                                mock_get_conn, mock_db_connection, mock_auth):
        """Test cancelling a reservation."""
        # Setup
        reservation_system.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test customer
        cursor.execute('''
            INSERT INTO restaurant_customers
            (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
             loyalty_tier, birthday, registration_date, last_visit, total_spent,
             visit_count, preferences, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('CUST000001', 'Test Customer', 'test@example.com', '1234567890',
              'None', 0, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              None, 0, 0, None, None, None, None))

        # Add test table
        cursor.execute('''
            INSERT INTO restaurant_tables
            (table_id, capacity, status, current_order_id, location, table_type, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('T001', 4, 'Reserved', None, 'Main Dining', 'Standard',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # Add test reservation
        cursor.execute('''
            INSERT INTO restaurant_reservations
            (reservation_id, customer_id, table_id, reservation_date, reservation_time,
             party_size, status, special_requests, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('RES001', 'CUST000001', 'T001', '2025-12-01', '19:00', 4,
              'Active', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'RES001',  # reservation_id
            'y'  # confirmation
        ]

        # Execute
        reservation_system.cancel_reservation()

        # Verify
        cursor.execute("SELECT status FROM restaurant_reservations WHERE reservation_id = 'RES001'")
        status = cursor.fetchone()[0]
        assert status == 'Cancelled'

        # Check table status updated to Available
        cursor.execute("SELECT status FROM restaurant_tables WHERE table_id = 'T001'")
        table_status = cursor.fetchone()[0]
        assert table_status == 'Available'
        mock_audit.assert_called_once()

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('builtins.input')
    def test_view_table_reservations(self, mock_input, mock_get_conn,
                                    mock_db_connection, capsys):
        """Test viewing table reservations."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test customer
        cursor.execute('''
            INSERT INTO restaurant_customers
            (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
             loyalty_tier, birthday, registration_date, last_visit, total_spent,
             visit_count, preferences, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('CUST000001', 'John Doe', 'john@example.com', '1234567890',
              'None', 0, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              None, 0, 0, None, None, None, None))

        # Add test table
        cursor.execute('''
            INSERT INTO restaurant_tables
            (table_id, capacity, status, current_order_id, location, table_type, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('T001', 4, 'Reserved', None, 'Main Dining', 'Standard',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # Add test reservation
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO restaurant_reservations
            (reservation_id, customer_id, table_id, reservation_date, reservation_time,
             party_size, status, special_requests, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('RES001', 'CUST000001', 'T001', today, '19:00', 4,
              'Active', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Mock user input
        mock_input.side_effect = ['2']  # Today's reservations

        # Execute
        reservation_system.view_table_reservations()

        # Verify
        captured = capsys.readouterr()
        assert "RESERVATIONS" in captured.out
        assert "RES001" in captured.out
        assert "John Doe" in captured.out

class TestQRCodeManagement:
    """Tests for QR code generation and management."""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.QR_CODES_DIR')
    @patch('builtins.input')
    def test_generate_qr_codes_for_all_tables(self, mock_input, mock_qr_dir,
                                              mock_get_conn, mock_db_connection,
                                              mock_auth, tmp_path):
        """Test generating QR codes for all tables."""
        # Setup
        reservation_system.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        mock_qr_dir.return_value = tmp_path / "qr_codes"
        (tmp_path / "qr_codes").mkdir(parents=True, exist_ok=True)

        cursor = mock_db_connection.cursor()

        # Add test tables
        for i in range(1, 4):
            cursor.execute('''
                INSERT INTO restaurant_tables
                (table_id, capacity, status, current_order_id, location, table_type, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (f'T00{i}', 4, 'Available', None, 'Main Dining', 'Standard',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Mock user input
        mock_input.side_effect = ['1']  # Generate for all tables

        # Execute with QR_CODES_DIR patched
        with patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.QR_CODES_DIR', tmp_path / "qr_codes"):
            reservation_system.generate_qr_codes()

        # Verify QR code records in database
        cursor.execute("SELECT COUNT(*) FROM restaurant_qr_codes")
        count = cursor.fetchone()[0]
        assert count == 3

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    def test_scan_qr_code_usage(self, mock_get_conn, mock_db_connection):
        """Test scanning QR code and updating usage statistics."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test table
        cursor.execute('''
            INSERT INTO restaurant_tables
            (table_id, capacity, status, current_order_id, location, table_type, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('T001', 4, 'Available', None, 'Main Dining', 'Standard',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # Add test QR code
        cursor.execute('''
            INSERT INTO restaurant_qr_codes
            (qr_id, table_id, qr_data, created_date, last_used, usage_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('QR001', 'T001', 'https://restaurant.edu/menu?table=T001',
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None, 0, 'Active'))
        mock_db_connection.commit()

        # Mock user input
        with patch('builtins.input', return_value='T001'):
            # Execute
            reservation_system.scan_qr_code_usage()

        # Verify
        cursor.execute("SELECT usage_count FROM restaurant_qr_codes WHERE table_id = 'T001'")
        usage_count = cursor.fetchone()[0]
        assert usage_count == 1

class TestTableAnalytics:
    """Tests for table analytics functionality."""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.customer.reservation_system.get_db_connection')
    def test_table_analytics(self, mock_get_conn, mock_db_connection, capsys):
        """Test table analytics display."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test tables with different statuses
        tables = [
            ('T001', 2, 'Available', 'Main Dining', 'Standard'),
            ('T002', 4, 'Occupied', 'Main Dining', 'Standard'),
            ('T003', 6, 'Reserved', 'Patio', 'Outdoor'),
            ('T004', 4, 'Available', 'VIP Room', 'VIP'),
        ]

        for table_id, capacity, status, location, table_type in tables:
            cursor.execute('''
                INSERT INTO restaurant_tables
                (table_id, capacity, status, current_order_id, location, table_type, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (table_id, capacity, status, None, location, table_type,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # Add test reservations
        cursor.execute('''
            INSERT INTO restaurant_customers
            (customer_id, name, email, phone, dietary_restrictions, loyalty_points,
             loyalty_tier, birthday, registration_date, last_visit, total_spent,
             visit_count, preferences, address, emergency_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('CUST000001', 'Test Customer', 'test@example.com', '1234567890',
              'None', 0, 'Bronze', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              None, 0, 0, None, None, None, None))

        cursor.execute('''
            INSERT INTO restaurant_reservations
            (reservation_id, customer_id, table_id, reservation_date, reservation_time,
             party_size, status, special_requests, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('RES001', 'CUST000001', 'T001', datetime.now().strftime('%Y-%m-%d'),
              '19:00', 2, 'Active', None, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        mock_db_connection.commit()

        # Execute
        reservation_system.table_analytics()

        # Verify
        captured = capsys.readouterr()
        assert "TABLE ANALYTICS" in captured.out
        assert "Total Tables: 4" in captured.out
        assert "Total Capacity: 16" in captured.out
        assert "Available" in captured.out or "Occupied" in captured.out or "Reserved" in captured.out

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
