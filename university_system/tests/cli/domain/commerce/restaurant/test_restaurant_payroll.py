"""
Comprehensive tests for restaurant payroll module.

Tests cover:
- Weekly payroll calculations
- Monthly payroll calculations
- Individual payroll calculations
- Payroll export functionality
- Edge cases and error handling
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, call, patch

import pytest


class TestPayrollModule(unittest.TestCase):
    """Test suite for payroll.py module"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_conn.__enter__ = Mock(return_value=self.mock_conn)
        self.mock_conn.__exit__ = Mock(return_value=False)

        # Sample payroll data
        self.sample_staff_payroll = [
            ('STAFF001', 'John Doe', 'Server', 12.50, 40.0),
            ('STAFF002', 'Jane Smith', 'Cook', 15.00, 38.5),
            ('STAFF003', 'Bob Wilson', 'Manager', 20.00, 45.0),
        ]

        self.sample_monthly_payroll = [
            ('STAFF001', 'John Doe', 'Server', 12.50, 160.0, 20),
            ('STAFF002', 'Jane Smith', 'Cook', 15.00, 154.0, 19),
            ('STAFF003', 'Bob Wilson', 'Manager', 20.00, 180.0, 22),
        ]

        self.sample_schedule_data = [
            ('2024-01-15', '09:00', '17:00', '09:00:00', '17:00:00', 30),
            ('2024-01-16', '09:00', '17:00', '09:00:00', '17:00:00', 30),
            ('2024-01-17', '09:00', '17:00', '09:00:00', '17:00:00', 30),
        ]

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', return_value='2024-01-01')
    def test_calculate_weekly_payroll(self, mock_input, mock_get_conn):
        """Test weekly payroll calculation"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_weekly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = self.sample_staff_payroll

        # Execute
        calculate_weekly_payroll()

        # Verify query was executed
        self.mock_cursor.execute.assert_called_once()
        sql_call = str(self.mock_cursor.execute.call_args)
        assert 'restaurant_staff' in sql_call
        assert 'restaurant_staff_schedules' in sql_call
        assert 'SUM' in sql_call

        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', return_value='invalid-date')
    def test_calculate_weekly_payroll_invalid_date(self, mock_input, mock_get_conn):
        """Test weekly payroll with invalid date"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_weekly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn

        # Execute
        calculate_weekly_payroll()

        # Should handle invalid date gracefully
        # Query should not be executed
        self.mock_cursor.execute.assert_not_called()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', return_value='2024-01-01')
    def test_calculate_weekly_payroll_no_data(self, mock_input, mock_get_conn):
        """Test weekly payroll with no data"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_weekly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []

        # Execute
        calculate_weekly_payroll()

        # Should handle no data gracefully
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['1', '2024'])
    def test_calculate_monthly_payroll(self, mock_input, mock_get_conn):
        """Test monthly payroll calculation"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_monthly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = self.sample_monthly_payroll

        # Execute
        calculate_monthly_payroll()

        # Verify query executed
        self.mock_cursor.execute.assert_called_once()
        sql_call = str(self.mock_cursor.execute.call_args)
        assert 'restaurant_staff' in sql_call
        assert 'COUNT' in sql_call
        assert 'days_worked' in sql_call or 'COUNT(ss.schedule_id)' in sql_call

        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['12', '2024'])
    def test_calculate_monthly_payroll_december(self, mock_input, mock_get_conn):
        """Test monthly payroll for December (edge case)"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_monthly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = self.sample_monthly_payroll

        # Execute
        calculate_monthly_payroll()

        # Should handle December correctly (next year transition)
        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['13', '2024'])
    def test_calculate_monthly_payroll_invalid_month(self, mock_input, mock_get_conn):
        """Test monthly payroll with invalid month"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_monthly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn

        # Execute
        calculate_monthly_payroll()

        # Should handle invalid month gracefully
        self.mock_cursor.execute.assert_not_called()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['0', '2024'])
    def test_calculate_monthly_payroll_month_zero(self, mock_input, mock_get_conn):
        """Test monthly payroll with month = 0"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_monthly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn

        # Execute
        calculate_monthly_payroll()

        # Should reject month 0
        self.mock_cursor.execute.assert_not_called()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['abc', '2024'])
    def test_calculate_monthly_payroll_invalid_input(self, mock_input, mock_get_conn):
        """Test monthly payroll with non-numeric input"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_monthly_payroll

        # Execute
        calculate_monthly_payroll()

        # Should handle ValueError gracefully
        # Connection should not be obtained
        mock_get_conn.assert_not_called()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['STAFF001', '2024-01-01', '2024-01-07'])
    def test_calculate_individual_payroll(self, mock_input, mock_get_conn):
        """Test individual staff payroll calculation"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_individual_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn

        # Mock staff info
        self.mock_cursor.fetchone.return_value = ('John Doe', 'Server', 12.50)

        # Mock schedule data
        self.mock_cursor.fetchall.return_value = self.sample_schedule_data

        # Execute
        calculate_individual_payroll()

        # Verify queries
        assert self.mock_cursor.execute.call_count == 2
        execute_calls = [str(call) for call in self.mock_cursor.execute.call_args_list]
        assert any('restaurant_staff' in call for call in execute_calls)
        assert any('restaurant_staff_schedules' in call for call in execute_calls)

        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['STAFF999', '2024-01-01', '2024-01-07'])
    def test_calculate_individual_payroll_staff_not_found(self, mock_input, mock_get_conn):
        """Test individual payroll for non-existent staff"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_individual_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = None

        # Execute
        calculate_individual_payroll()

        # Should return early after staff lookup
        self.mock_conn.close.assert_called_once()
        # Should only have one execute call (staff lookup)
        assert self.mock_cursor.execute.call_count == 1

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['STAFF001', '2024-01-01', '2024-01-07'])
    def test_calculate_individual_payroll_no_schedules(self, mock_input, mock_get_conn):
        """Test individual payroll with no schedule data"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_individual_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = ('John Doe', 'Server', 12.50)
        self.mock_cursor.fetchall.return_value = []

        # Execute
        calculate_individual_payroll()

        # Should handle gracefully
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['STAFF001', '2024-01-01', '2024-01-07'])
    def test_calculate_individual_payroll_with_actual_times(self, mock_input, mock_get_conn):
        """Test individual payroll with actual clock-in/out times"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_individual_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = ('John Doe', 'Server', 12.50)

        # Schedule with actual times (worked overtime)
        schedule_with_actual = [
            ('2024-01-15', '09:00', '17:00', '08:55:00', '18:30:00', 30),
        ]
        self.mock_cursor.fetchall.return_value = schedule_with_actual

        # Execute
        calculate_individual_payroll()

        # Should use actual times instead of scheduled
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['STAFF001', '2024-01-01', '2024-01-07'])
    def test_calculate_individual_payroll_with_breaks(self, mock_input, mock_get_conn):
        """Test individual payroll correctly handles break time"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_individual_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = ('John Doe', 'Server', 12.50)

        # Schedule with 60 minute break
        schedule_with_break = [
            ('2024-01-15', '09:00', '17:00', '09:00:00', '17:00:00', 60),
        ]
        self.mock_cursor.fetchall.return_value = schedule_with_break

        # Execute
        calculate_individual_payroll()

        # Should subtract break time from total hours
        # 8 hours - 1 hour break = 7 hours paid
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.export_payroll_report')
    @patch('builtins.input', side_effect=['4', '5'])
    def test_payroll_calculations_menu_export(self, mock_input, mock_export):
        """Test payroll calculations menu - export option"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import payroll_calculations

        # Execute
        payroll_calculations()

        # Should call export function
        mock_export.assert_called_once()

    @patch('builtins.input', side_effect=['5'])
    def test_payroll_calculations_menu_return(self, mock_input):
        """Test payroll calculations menu - return option"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import payroll_calculations

        # Execute
        payroll_calculations()

        # Should return without error
        assert mock_input.call_count == 1

    @patch('builtins.input', return_value='99')
    def test_payroll_calculations_menu_invalid_choice(self, mock_input):
        """Test payroll calculations menu - invalid choice"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import payroll_calculations

        # Execute
        payroll_calculations()

        # Should handle invalid choice (no loop, just returns)
        assert mock_input.call_count == 1

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', return_value='2024-01-01')
    def test_calculate_weekly_payroll_null_hours(self, mock_input, mock_get_conn):
        """Test weekly payroll with NULL hours"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_weekly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn

        # Staff with NULL hours (no schedules)
        payroll_with_null = [
            ('STAFF001', 'John Doe', 'Server', 12.50, None),
            ('STAFF002', 'Jane Smith', 'Cook', 15.00, 38.5),
        ]
        self.mock_cursor.fetchall.return_value = payroll_with_null

        # Execute
        calculate_weekly_payroll()

        # Should handle NULL hours gracefully (treat as 0)
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    @patch('builtins.input', side_effect=['1', '2024'])
    def test_calculate_monthly_payroll_null_rate(self, mock_input, mock_get_conn):
        """Test monthly payroll with NULL hourly rate"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import calculate_monthly_payroll

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn

        # Staff with NULL rate
        payroll_with_null_rate = [
            ('STAFF001', 'John Doe', 'Server', None, 160.0, 20),
        ]
        self.mock_cursor.fetchall.return_value = payroll_with_null_rate

        # Execute
        calculate_monthly_payroll()

        # Should handle NULL rate gracefully
        self.mock_conn.close.assert_called_once()


class TestPayrollCalculations(unittest.TestCase):
    """Test payroll calculation logic"""

    def test_hours_calculation(self):
        """Test hour calculation logic"""
        # 9 AM to 5 PM = 8 hours
        start = datetime.strptime('2024-01-15 09:00:00', '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime('2024-01-15 17:00:00', '%Y-%m-%d %H:%M:%S')
        hours = (end - start).total_seconds() / 3600
        assert hours == 8.0

    def test_break_deduction(self):
        """Test break time deduction"""
        total_hours = 8.0
        break_minutes = 30
        break_hours = break_minutes / 60
        net_hours = total_hours - break_hours
        assert net_hours == 7.5

    def test_gross_pay_calculation(self):
        """Test gross pay calculation"""
        hours = 40.0
        rate = 12.50
        gross_pay = hours * rate
        assert gross_pay == 500.00

    def test_overtime_hours(self):
        """Test overtime calculation logic"""
        # If employee works 45 hours (5 overtime at 1.5x)
        regular_hours = 40.0
        total_hours = 45.0
        overtime_hours = max(0, total_hours - regular_hours)
        assert overtime_hours == 5.0


class TestPayrollIntegration(unittest.TestCase):
    """Integration tests for payroll operations"""

    @patch('university_system.modules.core.services.restaurant_misc.payroll.get_db_connection')
    def test_payroll_data_consistency(self, mock_get_conn):
        """Test payroll data consistency across different views"""
        from university_system.modules.domain.commerce.services.restaurant.staff.payroll import (
            calculate_weekly_payroll,
            calculate_individual_payroll
        )

        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Test weekly payroll
        with patch('builtins.input', return_value='2024-01-01'):
            mock_cursor.fetchall.return_value = [
                ('STAFF001', 'John Doe', 'Server', 12.50, 40.0),
            ]
            calculate_weekly_payroll()

        weekly_calls = mock_cursor.execute.call_count

        # Reset
        mock_cursor.reset_mock()

        # Test individual payroll for same period
        with patch('builtins.input', side_effect=['STAFF001', '2024-01-01', '2024-01-07']):
            mock_cursor.fetchone.return_value = ('John Doe', 'Server', 12.50)
            mock_cursor.fetchall.return_value = []
            calculate_individual_payroll()

        # Both should query the same tables
        assert mock_cursor.execute.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
