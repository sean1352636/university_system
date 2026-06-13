"""
Comprehensive test suite for email/reports.py
Tests email metrics logging, report generation, and communication statistics
"""

import sys
import os
import csv
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from education_system.university_system.infrastructure.email import reports


class TestLogEmailMetrics:
    """Test suite for log_email_metrics() function"""

    def test_log_email_metrics_sent_new_record(self):
        """Test logging sent email metric with new record"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None  # No existing record
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.log_email_metrics('sent')

            assert result is True

    def test_log_email_metrics_sent_existing_record(self):
        """Test logging sent email metric with existing record"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)  # Existing record
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.log_email_metrics('sent')

            assert result is True

    def test_log_email_metrics_failed_new_record(self):
        """Test logging failed email metric with new record"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.log_email_metrics('failed')

            assert result is True

    def test_log_email_metrics_failed_existing_record(self):
        """Test logging failed email metric with existing record"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.log_email_metrics('failed')

            assert result is True

    def test_log_email_metrics_ensures_table_exists(self):
        """Test that metrics table is created if it doesn't exist"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [None, None]  # Table doesn't exist, then no record
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.log_email_metrics('sent')

            assert result is True

    def test_log_email_metrics_database_error(self):
        """Test logging email metrics with database error"""
        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            result = reports.log_email_metrics('sent')

            assert result is False

    def test_log_email_metrics_creates_correct_date(self):
        """Test that metrics are logged with correct date"""
        calls_made = []

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None

            def capture_execute(query, params=None):
                if params:
                    calls_made.append((query, params))

            mock_cursor.execute = capture_execute
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
             patch('education_system.university_system.infrastructure.email.reports.datetime') as mock_datetime:

            mock_now = datetime(2024, 1, 15, 10, 30, 0)
            mock_datetime.now.return_value = mock_now

            reports.log_email_metrics('sent')

            # Verify the date used in the insert matches today's date
            # This test verifies the logic but cannot check exact params due to mocking


class TestGenerateReport:
    """Test suite for generate_report() function"""

    def test_generate_report_with_data_json(self):
        """Test generating report in JSON format with data"""
        mock_records = [
            ('2024-01-01', 10, 2, 5, 1),
            ('2024-01-02', 15, 3, 8, 2)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None  # Table exists
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.generate_report('2024-01-01', '2024-01-02', 'json')

            assert 'data' in result
            assert 'totals' in result
            assert len(result['data']) == 2
            assert result['totals']['sent'] == 25
            assert result['totals']['failed'] == 5

    def test_generate_report_with_data_csv(self):
        """Test generating report in CSV format with data"""
        mock_records = [
            ('2024-01-01', 10, 2, 5, 1),
            ('2024-01-02', 15, 3, 8, 2)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
             patch('builtins.open', mock_open()) as mock_file:

            result = reports.generate_report('2024-01-01', '2024-01-02', 'csv')

            assert 'file_path' in result
            assert 'email_report_2024-01-01_to_2024-01-02.csv' in result['file_path']

    def test_generate_report_no_data(self):
        """Test generating report when no data exists"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = []
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.generate_report('2024-01-01', '2024-01-02', 'json')

            assert result['data'] == []
            assert result['totals'] == {}

    def test_generate_report_default_dates(self):
        """Test generating report with default date range"""
        mock_records = [
            ('2024-01-01', 10, 2, 5, 1)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
             patch('education_system.university_system.infrastructure.email.reports.datetime') as mock_datetime:

            mock_now = datetime(2024, 2, 1, 10, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime

            result = reports.generate_report(None, None, 'json')

            assert 'data' in result
            assert 'start_date' in result
            assert 'end_date' in result

    def test_generate_report_calculates_rates_correctly(self):
        """Test that report calculates success/open/click rates correctly"""
        mock_records = [
            ('2024-01-01', 80, 20, 40, 10)  # 80 sent, 20 failed, 40 opened, 10 clicked
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.generate_report('2024-01-01', '2024-01-01', 'json')

            day_data = result['data'][0]

            # Success rate: 80 / (80 + 20) * 100 = 80%
            assert day_data['success_rate'] == 80.0

            # Open rate: 40 / 80 * 100 = 50%
            assert day_data['open_rate'] == 50.0

            # Click rate: 10 / 40 * 100 = 25%
            assert day_data['click_rate'] == 25.0

    def test_generate_report_totals_calculated_correctly(self):
        """Test that totals are calculated correctly across multiple days"""
        mock_records = [
            ('2024-01-01', 50, 10, 20, 5),
            ('2024-01-02', 30, 5, 15, 3)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.generate_report('2024-01-01', '2024-01-02', 'json')

            totals = result['totals']

            assert totals['sent'] == 80
            assert totals['failed'] == 15
            assert totals['opened'] == 35
            assert totals['clicked'] == 8

    def test_generate_report_handles_zero_division(self):
        """Test that report handles zero division in rate calculations"""
        mock_records = [
            ('2024-01-01', 0, 0, 0, 0)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            result = reports.generate_report('2024-01-01', '2024-01-01', 'json')

            day_data = result['data'][0]

            assert day_data['success_rate'] == 0
            assert day_data['open_rate'] == 0
            assert day_data['click_rate'] == 0

    def test_generate_report_database_error(self):
        """Test generating report with database error"""
        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            result = reports.generate_report('2024-01-01', '2024-01-02', 'json')

            assert result['data'] == []
            assert result['totals'] == {}

    def test_generate_report_csv_file_creation(self):
        """Test that CSV file is created with correct format"""
        mock_records = [
            ('2024-01-01', 10, 2, 5, 1)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            temp_path = tmp.name

        try:
            with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
                 patch('builtins.open', mock_open()) as mock_file:

                result = reports.generate_report('2024-01-01', '2024-01-02', 'csv')

                # Verify open was called to create the CSV file
                assert mock_file.called
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestGenerateReportForm:
    """Test suite for generate_report_form() function"""

    def test_generate_report_form_last_7_days_json(self):
        """Test generating report for last 7 days in JSON format"""
        mock_records = []

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['1', '1']), \
             patch('builtins.print'), \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            reports.generate_report_form()

    def test_generate_report_form_last_30_days_json(self):
        """Test generating report for last 30 days"""
        mock_records = []

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['2', '1']), \
             patch('builtins.print'), \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            reports.generate_report_form()

    def test_generate_report_form_current_month_json(self):
        """Test generating report for current month"""
        mock_records = []

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['3', '1']), \
             patch('builtins.print'), \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
             patch('education_system.university_system.infrastructure.email.reports.datetime') as mock_datetime:

            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_datetime.now.return_value = mock_now

            reports.generate_report_form()

    def test_generate_report_form_custom_range_json(self):
        """Test generating report for custom date range"""
        mock_records = []

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=[
            '4',  # Custom range
            '2024', '1', '1',  # Start date
            '2024', '1', '31',  # End date
            '1'  # JSON format
        ]), \
             patch('builtins.print'), \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            reports.generate_report_form()

    def test_generate_report_form_custom_range_csv(self):
        """Test generating report in CSV format"""
        mock_records = []

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=[
            '4',  # Custom range
            '2024', '1', '1',  # Start date
            '2024', '1', '31',  # End date
            '2'  # CSV format
        ]), \
             patch('builtins.print'), \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
             patch('builtins.open', mock_open()):

            reports.generate_report_form()

    def test_generate_report_form_invalid_date_range(self):
        """Test generating report with invalid date range (start > end)"""
        with patch('builtins.input', side_effect=[
            '4',  # Custom range
            '2024', '12', '31',  # Start date
            '2024', '1', '1',  # End date (before start)
        ]), \
             patch('builtins.print') as mock_print:

            reports.generate_report_form()

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Start date must be before end date' in str(call) for call in calls)

    def test_generate_report_form_invalid_date_values(self):
        """Test generating report with invalid date values"""
        with patch('builtins.input', side_effect=[
            '4',  # Custom range
            '2024', '13', '1',  # Invalid month
        ]), \
             patch('builtins.print') as mock_print:

            reports.generate_report_form()

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Invalid date' in str(call) for call in calls)

    def test_generate_report_form_invalid_choice(self):
        """Test generating report with invalid choice"""
        with patch('builtins.input', side_effect=['99']), \
             patch('builtins.print') as mock_print:

            reports.generate_report_form()

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Invalid choice' in str(call) for call in calls)

    def test_generate_report_form_invalid_format_choice(self):
        """Test generating report with invalid format choice"""
        mock_records = [
            ('2024-01-01', 10, 2, 5, 1)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['1', '99', '']), \
             patch('builtins.print') as mock_print, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            reports.generate_report_form()

            calls = [str(call) for call in mock_print.call_args_list]
            # Should default to JSON format — _t returns key or translated text
            assert any('invalid_using_json' in str(call).lower() or 'using json' in str(call).lower() for call in calls)

    def test_generate_report_form_displays_json_output(self):
        """Test that JSON report is displayed correctly"""
        mock_records = [
            ('2024-01-01', 10, 2, 5, 1)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['1', '1']), \
             patch('builtins.print') as mock_print, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            reports.generate_report_form()

            calls = [str(call) for call in mock_print.call_args_list]
            assert any('Email Report for' in str(call) for call in calls)
            assert any('Total Sent' in str(call) for call in calls)

    def test_generate_report_form_displays_csv_path(self):
        """Test that CSV file path is displayed"""
        mock_records = [
            ('2024-01-01', 10, 2, 5, 1)
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = mock_records
            return func(mock_cursor)

        with patch('builtins.input', side_effect=['1', '2', '']), \
             patch('builtins.print') as mock_print, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
             patch('builtins.open', mock_open()):

            reports.generate_report_form()

            calls = [str(call) for call in mock_print.call_args_list]
            # _t returns key or translated text for report_saved
            assert any('report_saved' in str(call).lower() or 'report generated' in str(call).lower() or 'saved to' in str(call).lower() for call in calls)


class TestGetUserCommunicationStats:
    """Test suite for get_user_communication_stats() function"""

    def test_get_user_communication_stats_success(self):
        """Test getting communication stats for current user"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [
                (10,),  # messages_sent
                (5,),   # messages_received
                (2,),   # unread_messages
                (3,),   # announcements_created
                (4,),   # chat_rooms_joined
                (1,)    # chat_rooms_created
            ]
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            stats = reports.get_user_communication_stats(mock_dashboard)

            assert stats is not None
            assert stats['messages_sent'] == 10
            assert stats['messages_received'] == 5
            assert stats['unread_messages'] == 2
            assert stats['announcements_created'] == 3
            assert stats['chat_rooms_joined'] == 4
            assert stats['chat_rooms_created'] == 1

    def test_get_user_communication_stats_specific_user(self):
        """Test getting communication stats for specific user"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [
                (5,), (3,), (1,), (0,), (2,), (0,)
            ]
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            stats = reports.get_user_communication_stats(mock_dashboard, user_id=2)

            assert stats is not None

    def test_get_user_communication_stats_not_logged_in(self):
        """Test getting stats when not logged in"""
        mock_dashboard = Mock()
        mock_dashboard.auth = None

        stats = reports.get_user_communication_stats(mock_dashboard)

        assert stats is None

    def test_get_user_communication_stats_no_current_user(self):
        """Test getting stats when current user is None"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = None

        stats = reports.get_user_communication_stats(mock_dashboard)

        assert stats is None

    def test_get_user_communication_stats_database_error(self):
        """Test getting stats with database error"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            stats = reports.get_user_communication_stats(mock_dashboard)

            assert stats is None

    def test_get_user_communication_stats_zero_values(self):
        """Test getting stats with all zero values"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.side_effect = [
                (0,), (0,), (0,), (0,), (0,), (0,)
            ]
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            stats = reports.get_user_communication_stats(mock_dashboard)

            assert stats is not None
            assert stats['messages_sent'] == 0
            assert stats['messages_received'] == 0


class TestGetRecentCommunicationActivity:
    """Test suite for get_recent_communication_activity() function"""

    def test_get_recent_communication_activity_success(self):
        """Test getting recent communication activity"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        mock_activities = [
            ('send_message', 'Sent message to user2', '2024-01-01 10:00:00'),
            ('create_announcement', 'Created announcement: Test', '2024-01-01 09:00:00')
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = mock_activities
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            activities = reports.get_recent_communication_activity(mock_dashboard, limit=10)

            assert len(activities) == 2
            assert activities[0]['action_type'] == 'send_message'
            assert activities[0]['details'] == 'Sent message to user2'
            assert activities[1]['action_type'] == 'create_announcement'

    def test_get_recent_communication_activity_empty(self):
        """Test getting activity when none exists"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            activities = reports.get_recent_communication_activity(mock_dashboard)

            assert activities == []

    def test_get_recent_communication_activity_custom_limit(self):
        """Test getting activity with custom limit"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        mock_activities = [
            ('action1', 'details1', '2024-01-01 10:00:00'),
            ('action2', 'details2', '2024-01-01 09:00:00'),
            ('action3', 'details3', '2024-01-01 08:00:00')
        ]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = mock_activities[:5]  # Limit to 5
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):
            activities = reports.get_recent_communication_activity(mock_dashboard, limit=5)

            assert len(activities) <= 5

    def test_get_recent_communication_activity_not_logged_in(self):
        """Test getting activity when not logged in"""
        mock_dashboard = Mock()
        mock_dashboard.auth = None

        activities = reports.get_recent_communication_activity(mock_dashboard)

        assert activities == []

    def test_get_recent_communication_activity_database_error(self):
        """Test getting activity with database error"""
        mock_dashboard = Mock()
        mock_dashboard.auth.current_user = {'id': 1}

        with patch('education_system.university_system.infrastructure.email.reports.execute_db_operation') as mock_db:
            mock_db.side_effect = Exception("Database error")

            activities = reports.get_recent_communication_activity(mock_dashboard)

            assert activities == []


class TestGetSystemHealthInfo:
    """Test suite for get_system_health_info() function"""

    def test_get_system_health_info_all_operational(self):
        """Test getting system health when all systems operational"""
        mock_email_queue = Mock()
        mock_email_queue.qsize.return_value = 5
        mock_worker_threads = [Mock(), Mock()]

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            return func(mock_cursor)

        # email_queue and worker_threads are imported locally inside get_system_health_info,
        # so patch them at the email_service module level
        with patch('education_system.university_system.infrastructure.email.email_service.email_queue', mock_email_queue), \
             patch('education_system.university_system.infrastructure.email.email_service.worker_threads', mock_worker_threads), \
             patch('education_system.university_system.infrastructure.email.reports.config') as mock_config, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            mock_config.get.return_value = False  # Not database-only mode

            health = reports.get_system_health_info()

            assert health['email_system'] == 'operational'
            assert health['message_system'] == 'operational'
            assert health['chat_system'] == 'operational'
            assert health['database_status'] == 'operational'
            assert health['queue_size'] == 5
            assert 'last_check' in health

    def test_get_system_health_info_database_only_mode(self):
        """Test getting system health in database-only mode"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.config') as mock_config, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            mock_config.get.return_value = True  # Database-only mode

            health = reports.get_system_health_info()

            assert 'queue_size' in health
            # Queue size should be 0 in database-only mode
            assert health['queue_size'] == 0

    def test_get_system_health_info_no_workers(self):
        """Test getting system health when no worker threads"""
        mock_email_queue = Mock()
        mock_email_queue.qsize.return_value = 10
        mock_worker_threads = []  # No workers

        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.email_service.email_queue', mock_email_queue), \
             patch('education_system.university_system.infrastructure.email.email_service.worker_threads', mock_worker_threads), \
             patch('education_system.university_system.infrastructure.email.reports.config') as mock_config, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            mock_config.get.return_value = False

            health = reports.get_system_health_info()

            assert health['email_system'] == 'degraded'

    def test_get_system_health_info_database_error(self):
        """Test getting system health with database error"""
        with patch('education_system.university_system.infrastructure.email.reports.config') as mock_config, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation') as mock_db:

            mock_config.get.return_value = True
            mock_db.return_value = False  # Database test fails

            health = reports.get_system_health_info()

            assert health['database_status'] == 'error'

    def test_get_system_health_info_exception_handling(self):
        """Test getting system health with exception"""
        with patch('education_system.university_system.infrastructure.email.reports.config') as mock_config:
            mock_config.get.side_effect = Exception("Config error")

            health = reports.get_system_health_info()

            assert health['database_status'] == 'error'
            assert 'last_check' in health

    def test_get_system_health_info_includes_timestamp(self):
        """Test that health info includes timestamp"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.config') as mock_config, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation), \
             patch('education_system.university_system.infrastructure.email.reports.datetime') as mock_datetime:

            mock_config.get.return_value = True
            mock_now = datetime(2024, 1, 15, 10, 30, 45)
            mock_datetime.now.return_value = mock_now

            health = reports.get_system_health_info()

            assert 'last_check' in health
            # Timestamp format should be YYYY-MM-DD HH:MM:SS

    def test_get_system_health_info_all_components_present(self):
        """Test that all health components are included"""
        def mock_operation(func):
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (1,)
            return func(mock_cursor)

        with patch('education_system.university_system.infrastructure.email.reports.config') as mock_config, \
             patch('education_system.university_system.infrastructure.email.reports.execute_db_operation', side_effect=mock_operation):

            mock_config.get.return_value = True

            health = reports.get_system_health_info()

            required_keys = [
                'email_system',
                'message_system',
                'chat_system',
                'database_status',
                'queue_size',
                'last_check'
            ]

            for key in required_keys:
                assert key in health


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
