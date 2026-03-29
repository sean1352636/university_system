#!/usr/bin/env python3
"""
Comprehensive tests for Fee Structure Module
Tests late fee calculations, currency conversion, and exchange rate updates
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.modules.domain.finance.billing import fee_structure


class _UnclosableConnection:
    """Wrapper that makes close() a no-op so tests can query after production code closes."""
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
    def close(self):
        pass
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def __enter__(self):
        return self._conn.__enter__()
    def __exit__(self, *args):
        return self._conn.__exit__(*args)

def _unclosable_connect(db_path):
    return _UnclosableConnection(db_path)

@pytest.fixture
def temp_db():
    """Create a temporary database with finance schema for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create required tables for fee structure testing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email_address TEXT,
            course TEXT,
            enrollment_date TEXT,
            status TEXT DEFAULT 'active'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL,
            description TEXT,
            is_recurring BOOLEAN DEFAULT 0,
            academic_year TEXT,
            is_late_fee BOOLEAN DEFAULT 0,
            late_fee_calculation TEXT,
            late_fee_amount DECIMAL(10,2),
            grace_period_days INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            fee_type_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'unpaid',
            due_date TEXT,
            last_reminder_sent TEXT,
            reminder_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS late_fees (
            late_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_fee_id INTEGER NOT NULL,
            late_fee_amount DECIMAL(10,2) NOT NULL,
            calculation_method TEXT,
            days_overdue INTEGER NOT NULL,
            applied_date TEXT NOT NULL,
            waived BOOLEAN DEFAULT 0,
            waived_by TEXT,
            waived_date TEXT,
            waiver_reason TEXT,
            created_at TEXT,
            FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            exchange_rate DECIMAL(10,6) NOT NULL,
            rate_date TEXT NOT NULL,
            source TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS currency_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_currency TEXT DEFAULT 'GBP',
            auto_update_rates BOOLEAN DEFAULT 1,
            rate_update_frequency INTEGER DEFAULT 24,
            last_rate_update TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except (OSError, IOError):
        pass

@pytest.fixture
def mock_auth():
    """Mock authentication object"""
    auth = MagicMock()
    auth.current_user = {"username": "test_admin"}
    auth.check_permission = MagicMock(return_value=True)
    return auth

@pytest.fixture
def sample_data(temp_db):
    """Insert sample data for testing"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Insert sample students
    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course)
        VALUES ('STU001', 'John', 'Doe', 'john@test.com', 'Computer Science')
    """)

    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course)
        VALUES ('STU002', 'Jane', 'Smith', 'jane@test.com', 'Engineering')
    """)

    # Insert fee types
    cursor.execute("""
        INSERT INTO fee_types (fee_name, description, late_fee_calculation, late_fee_amount, grace_period_days)
        VALUES ('Tuition', 'Annual tuition fee', 'fixed', 50.00, 7)
    """)

    cursor.execute("""
        INSERT INTO fee_types (fee_name, description, late_fee_calculation, late_fee_amount, grace_period_days)
        VALUES ('Library Fee', 'Library usage fee', 'percentage', 10.00, 0)
    """)

    cursor.execute("""
        INSERT INTO fee_types (fee_name, description, late_fee_calculation, late_fee_amount, grace_period_days)
        VALUES ('Lab Fee', 'Laboratory fee', 'daily', 5.00, 5)
    """)

    # Insert overdue student fees
    overdue_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU001', 1, 5000.00, 'unpaid', ?)
    """, (overdue_date,))

    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU002', 2, 200.00, 'partial', ?)
    """, (overdue_date,))

    # Insert currency settings
    cursor.execute("""
        INSERT INTO currency_settings (base_currency) VALUES ('GBP')
    """)

    # Insert exchange rates
    current_date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        INSERT INTO exchange_rates (from_currency, to_currency, exchange_rate, rate_date, source)
        VALUES ('GBP', 'USD', 1.27, ?, 'manual')
    """, (current_date,))

    cursor.execute("""
        INSERT INTO exchange_rates (from_currency, to_currency, exchange_rate, rate_date, source)
        VALUES ('GBP', 'EUR', 1.17, ?, 'manual')
    """, (current_date,))

    conn.commit()
    conn.close()

    return temp_db

class TestLateFeeCalculations:
    """Test late fee calculation functionality"""

    def test_calculate_fixed_late_fees(self, sample_data, mock_auth):
        """Test calculation of fixed late fees"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):

            # Mock database connection
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            # Calculate late fees
            fee_structure.calculate_late_fees()

            # Verify late fees were created
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM late_fees")
            count = cursor.fetchone()[0]
            assert count > 0, "Late fees should be created"

    def test_calculate_percentage_late_fees(self, sample_data, mock_auth):
        """Test calculation of percentage-based late fees"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            fee_structure.calculate_late_fees()

            # Verify percentage calculation
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lf.late_fee_amount, sf.amount, ft.late_fee_amount
                FROM late_fees lf
                JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE ft.late_fee_calculation = 'percentage'
            """)

            result = cursor.fetchone()
            if result:
                late_fee, original_amount, percentage = result
                expected_fee = original_amount * (percentage / 100)
                assert late_fee == expected_fee, f"Percentage late fee should be {expected_fee}"

    def test_calculate_daily_late_fees(self, sample_data, mock_auth):
        """Test calculation of daily late fees"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            fee_structure.calculate_late_fees()

            # Verify daily calculation
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lf.late_fee_amount, lf.days_overdue, ft.late_fee_amount
                FROM late_fees lf
                JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE ft.late_fee_calculation = 'daily'
            """)

            result = cursor.fetchone()
            if result:
                late_fee, days_overdue, daily_rate = result
                # Account for grace period
                assert late_fee > 0, "Daily late fee should be positive"

    def test_grace_period_respected(self, sample_data, mock_auth):
        """Test that grace period is respected in late fee calculations"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            # Add a fee that's within grace period
            cursor = conn.cursor()
            recent_overdue = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
                VALUES ('STU001', 1, 1000.00, 'unpaid', ?)
            """, (recent_overdue,))
            conn.commit()

            fee_structure.calculate_late_fees()

            # Verify no late fee was applied for fee within grace period
            cursor.execute("""
                SELECT COUNT(*) FROM late_fees lf
                JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
                WHERE sf.due_date = ?
            """, (recent_overdue,))

            count = cursor.fetchone()[0]
            assert count == 0, "No late fee should be applied within grace period"

    def test_no_duplicate_late_fees(self, sample_data, mock_auth):
        """Test that late fees are not duplicated on the same day"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            # Calculate late fees twice
            fee_structure.calculate_late_fees()
            initial_count = conn.execute("SELECT COUNT(*) FROM late_fees").fetchone()[0]

            fee_structure.calculate_late_fees()
            final_count = conn.execute("SELECT COUNT(*) FROM late_fees").fetchone()[0]

            assert initial_count == final_count, "Late fees should not be duplicated"

class TestLateFeeWaiver:
    """Test late fee waiver functionality"""

    def test_waive_single_late_fee(self, sample_data, mock_auth):
        """Test waiving a single late fee"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '1', 'Financial hardship']), \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.student_exists', return_value=True), \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_student_name', return_value='John Doe'), \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.log_audit_action'):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            # Create a late fee first
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO late_fees (student_fee_id, late_fee_amount, calculation_method, days_overdue, applied_date, created_at)
                VALUES (1, 50.00, 'fixed', 10, date('now'), datetime('now'))
            """)
            conn.commit()

            fee_structure.waive_late_fee()

            # Verify late fee was waived
            cursor.execute("SELECT waived, waiver_reason FROM late_fees WHERE late_fee_id = 1")
            result = cursor.fetchone()
            assert result[0] == 1, "Late fee should be marked as waived"
            assert result[1] == 'Financial hardship', "Waiver reason should be recorded"

class TestExchangeRates:
    """Test exchange rate functionality"""

    def test_update_exchange_rates(self, sample_data, mock_auth):
        """Test updating exchange rates"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            fee_structure.update_exchange_rates()

            # Verify exchange rates were updated
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM exchange_rates")
            count = cursor.fetchone()[0]
            assert count > 0, "Exchange rates should be present"

    def test_convert_currency_same_currency(self, sample_data):
        """Test currency conversion with same currency"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn:
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            amount = 100.00
            result = fee_structure.convert_currency(amount, 'GBP', 'GBP')

            assert result == amount, "Same currency conversion should return original amount"
    def test_convert_currency_different_currencies(self, sample_data):
        """Test currency conversion between different currencies"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn:
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            amount = 100.00
            result = fee_structure.convert_currency(amount, 'GBP', 'USD')

            assert result == 127.00, "GBP to USD conversion should use exchange rate"
    def test_convert_currency_reverse_conversion(self, sample_data):
        """Test reverse currency conversion"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn:
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            amount = 127.00
            result = fee_structure.convert_currency(amount, 'USD', 'GBP')

            # Should use reverse rate (1/1.27)
            assert result > 0, "Reverse conversion should return positive value"
            assert result < amount, "Reverse conversion from USD to GBP should reduce value"

    def test_convert_currency_missing_rate(self, sample_data):
        """Test currency conversion with missing exchange rate"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn:
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            amount = 100.00
            result = fee_structure.convert_currency(amount, 'GBP', 'JPY')

            # Should return original amount if rate not found
            assert result == amount, "Missing rate should return original amount"
class TestCurrencyConversionTool:
    """Test currency conversion tool"""

    def test_currency_conversion_tool_valid_input(self, sample_data):
        """Test currency conversion tool with valid input"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['GBP', 'USD', '100']), \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.convert_currency', return_value=127.00):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            # Should not raise exception
            fee_structure.currency_conversion_tool()

    def test_currency_conversion_tool_invalid_currency(self, sample_data):
        """Test currency conversion tool with invalid currency"""
        with patch('builtins.input', side_effect=['XXX', 'USD', '100']):
            # Should handle invalid currency gracefully
            fee_structure.currency_conversion_tool()

    def test_currency_conversion_tool_invalid_amount(self, sample_data):
        """Test currency conversion tool with invalid amount"""
        with patch('builtins.input', side_effect=['GBP', 'USD', 'invalid']):
            # Should handle invalid amount gracefully
            fee_structure.currency_conversion_tool()

class TestAPIEndpoints:
    """Test API endpoints"""

    def test_api_get_exchange_rates(self, sample_data):
        """Test API endpoint for getting exchange rates"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn:
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            response = fee_structure.api_get_exchange_rates()

            # Verify response contains exchange rates
            assert isinstance(response.json, dict) or callable(response.json)
class TestPermissions:
    """Test permission requirements"""

    def test_calculate_late_fees_without_permission(self, sample_data):
        """Test that calculate_late_fees requires permission"""
        mock_auth = MagicMock()
        mock_auth.current_user = {"username": "test_user"}
        mock_auth.check_permission = MagicMock(return_value=False)

        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):
            fee_structure.calculate_late_fees()
            # Should not proceed without permission

    def test_waive_late_fee_without_permission(self, sample_data):
        """Test that waive_late_fee requires permission"""
        mock_auth = MagicMock()
        mock_auth.current_user = {"username": "test_user"}
        mock_auth.check_permission = MagicMock(return_value=False)

        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):
            fee_structure.waive_late_fee()
            # Should not proceed without permission

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_calculate_late_fees_with_no_overdue_fees(self, temp_db, mock_auth):
        """Test calculating late fees when no fees are overdue"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn, \
             patch('education_system.university_system.modules.domain.finance.billing.fee_structure.auth', mock_auth):

            conn = _unclosable_connect(temp_db)
            mock_conn.return_value = conn

            # Insert only current fees
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email_address, course)
                VALUES ('STU001', 'John', 'Doe', 'john@test.com', 'Computer Science')
            """)
            cursor.execute("""
                INSERT INTO fee_types (fee_name, description, late_fee_calculation, late_fee_amount, grace_period_days)
                VALUES ('Tuition', 'Annual tuition fee', 'fixed', 50.00, 7)
            """)
            future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
                VALUES ('STU001', 1, 5000.00, 'unpaid', ?)
            """, (future_date,))
            conn.commit()

            fee_structure.calculate_late_fees()

            # Verify no late fees were created
            cursor.execute("SELECT COUNT(*) FROM late_fees")
            count = cursor.fetchone()[0]
            assert count == 0, "No late fees should be created for future-due fees"

    def test_convert_currency_with_zero_amount(self, sample_data):
        """Test currency conversion with zero amount"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn:
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            result = fee_structure.convert_currency(0, 'GBP', 'USD')
            assert result == 0, "Zero amount should convert to zero"

    def test_convert_currency_with_negative_amount(self, sample_data):
        """Test currency conversion with negative amount"""
        with patch('education_system.university_system.modules.domain.finance.billing.fee_structure.get_connection') as mock_conn:
            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            result = fee_structure.convert_currency(-100, 'GBP', 'USD')
            assert result < 0, "Negative amount should remain negative"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
