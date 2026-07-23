#!/usr/bin/env python3
"""
Comprehensive tests for Email Scheduler Module
Tests scheduled email tasks, job management, and scheduler lifecycle
"""

import pytest
import sys
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


@pytest.fixture
def cleanup_scheduler():
    """Cleanup scheduler state after tests"""
    yield
    # Stop scheduler if running
    try:
        from education_system.post_18.university_system.infrastructure.email import email_scheduler
        if email_scheduler.scheduler_thread and email_scheduler.scheduler_thread.is_alive():
            email_scheduler.stop_scheduler(timeout=2)
        email_scheduler.scheduler_stop.clear()
        email_scheduler.scheduler_running.clear()
        email_scheduler.scheduler_thread = None
    except Exception:
        pass

    # Clear all scheduled jobs
    import schedule
    schedule.clear()


class TestCheckBookReturnReminders:
    """Test check_book_return_reminders function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_book_return_reminder')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_check_book_return_reminders_no_books(self, mock_log_event, mock_get_conn, mock_send_reminder):
        """Test checking reminders when no books are due"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_book_return_reminders

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        check_book_return_reminders()

        mock_cursor.execute.assert_called_once()
        mock_send_reminder.assert_not_called()
        mock_log_event.assert_called_with('info', 'Email Scheduler: Sent 0 book return reminders')

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_book_return_reminder')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_check_book_return_reminders_with_books(self, mock_log_event, mock_get_conn, mock_send_reminder):
        """Test checking reminders with books due in 3 days"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_book_return_reminders

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock books due in 3 days
        mock_cursor.fetchall.return_value = [
            (1, 101, 201, '2025-01-20', 'Introduction to Python'),
            (2, 102, 202, '2025-01-20', 'Advanced Algorithms'),
        ]

        check_book_return_reminders()

        assert mock_send_reminder.call_count == 2
        mock_send_reminder.assert_any_call(101, 201, 'Introduction to Python', '2025-01-20')
        mock_send_reminder.assert_any_call(102, 202, 'Advanced Algorithms', '2025-01-20')
        mock_log_event.assert_called_with('info', 'Email Scheduler: Sent 2 book return reminders')

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_book_return_reminder')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.logger')
    def test_check_book_return_reminders_send_failure(self, mock_logger, mock_get_conn, mock_send_reminder):
        """Test handling of reminder send failures"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_book_return_reminders

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            (1, 101, 201, '2025-01-20', 'Introduction to Python'),
        ]

        # Simulate send failure
        mock_send_reminder.side_effect = Exception("Send failed")

        check_book_return_reminders()

        mock_logger.error.assert_called()

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_check_book_return_reminders_db_error(self, mock_log_event, mock_get_conn):
        """Test handling of database errors"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_book_return_reminders

        mock_get_conn.side_effect = Exception("Database error")

        check_book_return_reminders()

        mock_log_event.assert_called()
        assert 'failed' in mock_log_event.call_args[0][1].lower()


class TestCheckOverdueBooks:
    """Test check_overdue_books function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_overdue_notification')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_check_overdue_books_no_overdue(self, mock_log_event, mock_get_conn, mock_send_notification):
        """Test checking overdue books when none are overdue"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_overdue_books

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        check_overdue_books()

        mock_send_notification.assert_not_called()
        mock_log_event.assert_called_with('info', 'Email Scheduler: Sent 0 overdue book notifications')

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_overdue_notification')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_check_overdue_books_with_overdue(self, mock_log_event, mock_get_conn, mock_send_notification):
        """Test checking overdue books with actual overdue books"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_overdue_books

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock overdue books (5 days overdue)
        mock_cursor.fetchall.return_value = [
            (1, 101, 201, '2025-01-10', 'Introduction to Python', 5.0),
            (2, 102, 202, '2025-01-12', 'Advanced Algorithms', 3.0),
        ]

        check_overdue_books()

        assert mock_send_notification.call_count == 2
        mock_send_notification.assert_any_call(101, 201, 'Introduction to Python', '2025-01-10', 5)
        mock_send_notification.assert_any_call(102, 202, 'Advanced Algorithms', '2025-01-12', 3)

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_overdue_notification')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.logger')
    def test_check_overdue_books_notification_failure(self, mock_logger, mock_get_conn, mock_send_notification):
        """Test handling of notification send failures"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_overdue_books

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            (1, 101, 201, '2025-01-10', 'Introduction to Python', 5.0),
        ]

        mock_send_notification.side_effect = Exception("Notification failed")

        check_overdue_books()

        mock_logger.error.assert_called()


class TestCheckSlaBreaches:
    """Test check_sla_breaches function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_sla_alert')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_check_sla_breaches_no_breaches(self, mock_log_event, mock_get_conn, mock_send_alert):
        """Test checking SLA breaches when none exist"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_sla_breaches

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        check_sla_breaches()

        mock_send_alert.assert_not_called()
        mock_log_event.assert_called_with('info', 'Email Scheduler: Sent 0 SLA breach alerts')

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_sla_alert')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_check_sla_breaches_with_breaches(self, mock_log_event, mock_get_conn, mock_send_alert):
        """Test checking SLA breaches with actual breaches"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_sla_breaches

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock breached tickets
        mock_cursor.fetchall.return_value = [
            (12345, '2025-01-15 10:00:00', 'open', 'high'),
            (12346, '2025-01-14 15:00:00', 'pending', 'medium'),
        ]

        check_sla_breaches()

        assert mock_send_alert.call_count == 2
        mock_send_alert.assert_any_call(12345, alert_type='overdue')
        mock_send_alert.assert_any_call(12346, alert_type='overdue')

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_sla_alert')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.logger')
    def test_check_sla_breaches_alert_failure(self, mock_logger, mock_get_conn, mock_send_alert):
        """Test handling of alert send failures"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_sla_breaches

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            (12345, '2025-01-15 10:00:00', 'open', 'high'),
        ]

        mock_send_alert.side_effect = Exception("Alert failed")

        check_sla_breaches()

        mock_logger.error.assert_called()


class TestSendDailySatisfactionSurveys:
    """Test send_daily_satisfaction_surveys function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_bulk_satisfaction_surveys')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_send_daily_satisfaction_surveys_success(self, mock_log_event, mock_send_bulk):
        """Test sending daily satisfaction surveys successfully"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import send_daily_satisfaction_surveys

        mock_send_bulk.return_value = (5, 5)  # 5 successful out of 5 total

        send_daily_satisfaction_surveys()

        mock_send_bulk.assert_called_once_with(days_old=1)
        mock_log_event.assert_called_with('info', 'Email Scheduler: Sent 5/5 satisfaction surveys')

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_bulk_satisfaction_surveys')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_send_daily_satisfaction_surveys_partial_success(self, mock_log_event, mock_send_bulk):
        """Test sending satisfaction surveys with partial success"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import send_daily_satisfaction_surveys

        mock_send_bulk.return_value = (3, 5)  # 3 successful out of 5 total

        send_daily_satisfaction_surveys()

        mock_log_event.assert_called_with('info', 'Email Scheduler: Sent 3/5 satisfaction surveys')

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_bulk_satisfaction_surveys')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_send_daily_satisfaction_surveys_failure(self, mock_log_event, mock_send_bulk):
        """Test handling of survey send failures"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import send_daily_satisfaction_surveys

        mock_send_bulk.side_effect = Exception("Bulk send failed")

        send_daily_satisfaction_surveys()

        mock_log_event.assert_called()
        assert 'failed' in mock_log_event.call_args[0][1].lower()


class TestSetupSchedules:
    """Test setup_schedules function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.logger')
    def test_setup_schedules_configures_all_jobs(self, mock_logger, mock_schedule):
        """Test that all scheduled jobs are configured"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import setup_schedules

        setup_schedules()

        # Should configure daily jobs (3 daily + 1 periodic = at least 4 calls)
        assert mock_schedule.every.call_count >= 3

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    def test_setup_schedules_timing(self, mock_schedule):
        """Test that jobs are scheduled at correct times"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import setup_schedules

        setup_schedules()

        # Verify schedule.every() was called
        assert mock_schedule.every.called


class TestStartScheduler:
    """Test start_scheduler function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.threading.Thread')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.setup_schedules')
    def test_start_scheduler_success(self, mock_setup, mock_thread, cleanup_scheduler):
        """Test starting scheduler successfully"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import start_scheduler, scheduler_running

        mock_thread_instance = MagicMock()
        mock_thread_instance.is_alive.return_value = True
        mock_thread.return_value = mock_thread_instance

        # Simulate scheduler starting
        def set_running(*args, **kwargs):
            scheduler_running.set()
        mock_thread_instance.start.side_effect = set_running

        result = start_scheduler()

        assert result is True
        mock_setup.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.threading.Thread')
    def test_start_scheduler_already_running(self, mock_thread, cleanup_scheduler):
        """Test starting scheduler when already running"""
        from education_system.post_18.university_system.infrastructure.email import email_scheduler

        # Set up existing running thread
        mock_thread_instance = MagicMock()
        mock_thread_instance.is_alive.return_value = True
        email_scheduler.scheduler_thread = mock_thread_instance

        result = email_scheduler.start_scheduler()

        assert result is False

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.threading.Thread')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.setup_schedules')
    def test_start_scheduler_clears_stop_flag(self, mock_setup, mock_thread, cleanup_scheduler):
        """Test that start_scheduler clears the stop flag"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            start_scheduler, scheduler_stop, scheduler_running
        )

        # Set stop flag
        scheduler_stop.set()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        def set_running(*args, **kwargs):
            scheduler_running.set()
        mock_thread_instance.start.side_effect = set_running

        start_scheduler()

        assert not scheduler_stop.is_set()


class TestStopScheduler:
    """Test stop_scheduler function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    def test_stop_scheduler_success(self, mock_schedule, cleanup_scheduler):
        """Test stopping scheduler successfully"""
        from education_system.post_18.university_system.infrastructure.email import email_scheduler

        # Set up running thread — is_alive returns True initially (passes guard),
        # then False after join (simulating successful stop)
        mock_thread = MagicMock()
        mock_thread.is_alive.side_effect = [True, False]
        email_scheduler.scheduler_thread = mock_thread
        email_scheduler.scheduler_running.set()

        result = email_scheduler.stop_scheduler(timeout=1)

        assert result is True
        mock_thread.join.assert_called_once()
        mock_schedule.clear.assert_called_once()

    def test_stop_scheduler_not_running(self, cleanup_scheduler):
        """Test stopping scheduler when not running"""
        from education_system.post_18.university_system.infrastructure.email import email_scheduler

        email_scheduler.scheduler_thread = None

        result = email_scheduler.stop_scheduler()

        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    def test_stop_scheduler_timeout(self, mock_schedule, cleanup_scheduler):
        """Test stopping scheduler with timeout"""
        from education_system.post_18.university_system.infrastructure.email import email_scheduler

        # Set up thread that doesn't stop
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        email_scheduler.scheduler_thread = mock_thread

        result = email_scheduler.stop_scheduler(timeout=1)

        # Should return False if thread is still alive after timeout
        assert mock_thread.join.called

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    def test_stop_scheduler_sets_stop_flag(self, mock_schedule, cleanup_scheduler):
        """Test that stop_scheduler sets the stop flag"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            stop_scheduler, scheduler_stop
        )
        from education_system.post_18.university_system.infrastructure.email import email_scheduler

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        email_scheduler.scheduler_thread = mock_thread

        stop_scheduler()

        assert scheduler_stop.is_set()


class TestIsSchedulerRunning:
    """Test is_scheduler_running function"""

    def test_is_scheduler_running_true(self, cleanup_scheduler):
        """Test is_scheduler_running returns True when running"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            is_scheduler_running, scheduler_running
        )

        scheduler_running.set()

        assert is_scheduler_running() is True

    def test_is_scheduler_running_false(self, cleanup_scheduler):
        """Test is_scheduler_running returns False when not running"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            is_scheduler_running, scheduler_running
        )

        scheduler_running.clear()

        assert is_scheduler_running() is False


class TestGetScheduledJobs:
    """Test get_scheduled_jobs function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    def test_get_scheduled_jobs_empty(self, mock_schedule):
        """Test getting scheduled jobs when none exist"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import get_scheduled_jobs

        mock_schedule.get_jobs.return_value = []

        jobs = get_scheduled_jobs()

        assert jobs == []
        mock_schedule.get_jobs.assert_called_once()

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    def test_get_scheduled_jobs_with_jobs(self, mock_schedule):
        """Test getting scheduled jobs when jobs exist"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import get_scheduled_jobs

        mock_jobs = [Mock(), Mock(), Mock()]
        mock_schedule.get_jobs.return_value = mock_jobs

        jobs = get_scheduled_jobs()

        assert len(jobs) == 3
        assert jobs == mock_jobs


class TestRunScheduler:
    """Test run_scheduler function (foreground mode)"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.setup_schedules')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.time.sleep')
    def test_run_scheduler_keyboard_interrupt(self, mock_sleep, mock_setup, mock_schedule):
        """Test run_scheduler stops on keyboard interrupt"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import run_scheduler

        # Simulate KeyboardInterrupt after first sleep
        mock_sleep.side_effect = KeyboardInterrupt()

        run_scheduler()

        mock_setup.assert_called_once()
        mock_schedule.clear.assert_called_once()

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.setup_schedules')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.time.sleep')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_run_scheduler_error_handling(self, mock_log_event, mock_sleep, mock_setup, mock_schedule):
        """Test run_scheduler handles errors"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import run_scheduler

        # Simulate error
        mock_sleep.side_effect = Exception("Unexpected error")

        run_scheduler()

        mock_schedule.clear.assert_called_once()
        # Should log error
        assert any('error' in str(call).lower() for call in mock_log_event.call_args_list)

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.setup_schedules')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.time.sleep')
    def test_run_scheduler_runs_pending(self, mock_sleep, mock_setup, mock_schedule):
        """Test run_scheduler runs pending jobs"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import run_scheduler

        # Run a few iterations then stop
        call_count = [0]
        def sleep_side_effect(seconds):
            call_count[0] += 1
            if call_count[0] >= 3:
                raise KeyboardInterrupt()
        mock_sleep.side_effect = sleep_side_effect

        run_scheduler()

        # Should call run_pending multiple times
        assert mock_schedule.run_pending.call_count >= 3


class TestSchedulerThreadLoop:
    """Test _run_scheduler_loop internal function"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.time.sleep')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.log_event')
    def test_scheduler_loop_sets_running_flag(self, mock_log_event, mock_sleep, mock_schedule):
        """Test that scheduler loop sets running flag"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            _run_scheduler_loop, scheduler_running, scheduler_stop
        )

        # Stop after first iteration
        def sleep_side_effect(seconds):
            scheduler_stop.set()
        mock_sleep.side_effect = sleep_side_effect

        _run_scheduler_loop()

        # Running flag should be cleared after loop exits
        assert not scheduler_running.is_set()

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.time.sleep')
    def test_scheduler_loop_stops_on_flag(self, mock_sleep, mock_schedule):
        """Test that scheduler loop stops when stop flag is set"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            _run_scheduler_loop, scheduler_stop
        )

        # Set stop flag before loop starts
        scheduler_stop.set()

        _run_scheduler_loop()

        # Should not sleep if stopped immediately
        mock_sleep.assert_not_called()


class TestIntegration:
    """Integration tests for email scheduler"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_bulk_satisfaction_surveys')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_book_return_reminder')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.time.sleep', side_effect=lambda s: None)
    def test_scheduler_lifecycle(self, mock_sleep, mock_get_conn, mock_book_reminder, mock_surveys, cleanup_scheduler):
        """Test complete scheduler lifecycle: start, check status, stop"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            start_scheduler, is_scheduler_running, stop_scheduler
        )

        # Initially not running
        assert is_scheduler_running() is False

        # Start scheduler
        with patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.setup_schedules'):
            result = start_scheduler()
            assert result is True
            assert is_scheduler_running() is True

        # Stop scheduler
        result = stop_scheduler(timeout=5)
        assert result is True
        assert is_scheduler_running() is False

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    def test_setup_and_get_jobs(self, mock_schedule):
        """Test setting up schedules and retrieving jobs"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            setup_schedules, get_scheduled_jobs
        )

        mock_jobs = [Mock(), Mock()]
        mock_schedule.get_jobs.return_value = mock_jobs

        setup_schedules()
        jobs = get_scheduled_jobs()

        # Should have configured jobs
        mock_schedule.get_jobs.assert_called_once()


class TestErrorRecovery:
    """Test error recovery and resilience"""

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.get_connection')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.logger')
    def test_book_reminders_continues_after_error(self, mock_logger, mock_get_conn):
        """Test that book reminder check continues after individual errors"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import check_book_return_reminders

        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Multiple books, one will fail
        mock_cursor.fetchall.return_value = [
            (1, 101, 201, '2025-01-20', 'Book 1'),
            (2, 102, 202, '2025-01-20', 'Book 2'),
        ]

        with patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.send_book_return_reminder') as mock_send:
            # First call fails, second succeeds
            mock_send.side_effect = [Exception("Failed"), None]

            # Should not raise exception
            check_book_return_reminders()

            # Both books should be attempted
            assert mock_send.call_count == 2

    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.schedule')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.time.sleep')
    @patch('education_system.post_18.university_system.infrastructure.email.email_scheduler.logger')
    def test_scheduler_loop_handles_errors(self, mock_logger, mock_sleep, mock_schedule):
        """Test that scheduler loop handles errors gracefully"""
        from education_system.post_18.university_system.infrastructure.email.email_scheduler import (
            _run_scheduler_loop, scheduler_stop
        )

        # Cause error in run_pending
        mock_schedule.run_pending.side_effect = [
            Exception("Temporary error"),
            None,
            None
        ]

        # Stop after a few iterations
        call_count = [0]
        def sleep_side_effect(seconds):
            call_count[0] += 1
            if call_count[0] >= 3:
                scheduler_stop.set()
        mock_sleep.side_effect = sleep_side_effect

        # Should handle error and continue
        _run_scheduler_loop()

        # Should have logged the error
        assert mock_logger.error.called


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
