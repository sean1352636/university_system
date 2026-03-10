#!/usr/bin/env python3
"""
Comprehensive tests for Email Manager Module
Tests email queue functions, notification sending, and queue management
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from collections import deque

# Add project root to path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


@pytest.fixture
def reset_email_queue():
    """Reset the email queue before each test"""
    from education_system.university_system.infrastructure.email import email_manager
    email_manager._email_queue.clear()
    yield
    email_manager._email_queue.clear()


class TestQueueEmail:
    """Test internal _queue_email function"""

    def test_queue_email_basic(self, reset_email_queue):
        """Test basic email queueing"""
        from education_system.university_system.infrastructure.email.email_manager import _queue_email, _email_queue

        _queue_email(
            email_type='test',
            recipient='test@university.edu',
            subject='Test Subject'
        )

        assert len(_email_queue) == 1
        email = _email_queue[0]
        assert email['type'] == 'test'
        assert email['recipient'] == 'test@university.edu'
        assert email['subject'] == 'Test Subject'
        assert email['status'] == 'queued'
        assert 'timestamp' in email

    def test_queue_email_with_metadata(self, reset_email_queue):
        """Test queueing email with additional metadata"""
        from education_system.university_system.infrastructure.email.email_manager import _queue_email, _email_queue

        _queue_email(
            email_type='notification',
            recipient='student@university.edu',
            subject='Grade Updated',
            course='CS101',
            grade='A',
            instructor='Dr. Smith'
        )

        email = _email_queue[0]
        assert email['metadata']['course'] == 'CS101'
        assert email['metadata']['grade'] == 'A'
        assert email['metadata']['instructor'] == 'Dr. Smith'

    def test_queue_email_timestamp_format(self, reset_email_queue):
        """Test that timestamp is in ISO format"""
        from education_system.university_system.infrastructure.email.email_manager import _queue_email, _email_queue

        _queue_email(
            email_type='test',
            recipient='test@university.edu',
            subject='Test'
        )

        email = _email_queue[0]
        # Should be parseable as ISO format
        timestamp = datetime.fromisoformat(email['timestamp'])
        assert isinstance(timestamp, datetime)

    def test_queue_multiple_emails(self, reset_email_queue):
        """Test queueing multiple emails"""
        from education_system.university_system.infrastructure.email.email_manager import _queue_email, _email_queue

        for i in range(5):
            _queue_email(
                email_type='test',
                recipient=f'user{i}@university.edu',
                subject=f'Test {i}'
            )

        assert len(_email_queue) == 5


class TestDisplayChatRoomsMenu:
    """Test display_chat_rooms_menu function"""

    def test_display_chat_rooms_menu_output(self, capsys):
        """Test that menu is displayed correctly"""
        from education_system.university_system.infrastructure.email.email_manager import display_chat_rooms_menu

        display_chat_rooms_menu()

        captured = capsys.readouterr()
        assert 'CHAT ROOMS MANAGEMENT MENU' in captured.out
        assert 'View All Chat Rooms' in captured.out
        assert 'Create New Chat Room' in captured.out
        assert 'Archive Chat Room' in captured.out
        assert 'View Chat Room Statistics' in captured.out
        assert 'Manage Chat Room Members' in captured.out
        assert 'Return to Main Menu' in captured.out

    def test_display_chat_rooms_menu_accepts_args(self):
        """Test that function accepts arbitrary arguments"""
        from education_system.university_system.infrastructure.email.email_manager import display_chat_rooms_menu

        # Should not raise error
        display_chat_rooms_menu('arg1', 'arg2', key='value')

    @patch('university_system.infrastructure.email.email_manager.logger')
    def test_display_chat_rooms_menu_logging(self, mock_logger):
        """Test that menu display is logged"""
        from education_system.university_system.infrastructure.email.email_manager import display_chat_rooms_menu

        display_chat_rooms_menu()

        mock_logger.debug.assert_called_once_with("Displayed chat rooms menu")


class TestSendTicketNotification:
    """Test send_ticket_notification function"""

    def test_send_ticket_notification_basic(self, reset_email_queue):
        """Test basic ticket notification"""
        from education_system.university_system.infrastructure.email.email_manager import send_ticket_notification, _email_queue

        send_ticket_notification(
            ticket_id='12345',
            recipient='support@university.edu',
            ticket_subject='Login Issue'
        )

        assert len(_email_queue) == 1
        email = _email_queue[0]
        assert email['type'] == 'ticket_notification'
        assert email['recipient'] == 'support@university.edu'
        assert email['subject'] == 'New Helpdesk Ticket #12345: Login Issue'
        assert email['metadata']['ticket_id'] == '12345'
        assert email['metadata']['ticket_subject'] == 'Login Issue'

    def test_send_ticket_notification_no_subject(self, reset_email_queue):
        """Test ticket notification with no subject"""
        from education_system.university_system.infrastructure.email.email_manager import send_ticket_notification, _email_queue

        send_ticket_notification(
            ticket_id='12345',
            recipient='support@university.edu',
            ticket_subject=None
        )

        email = _email_queue[0]
        assert email['subject'] == 'New Helpdesk Ticket #12345: No Subject'

    def test_send_ticket_notification_with_extra_kwargs(self, reset_email_queue):
        """Test ticket notification with additional keyword arguments"""
        from education_system.university_system.infrastructure.email.email_manager import send_ticket_notification, _email_queue

        send_ticket_notification(
            ticket_id='12345',
            recipient='support@university.edu',
            ticket_subject='Login Issue',
            priority='high',
            category='technical'
        )

        email = _email_queue[0]
        assert email['metadata']['priority'] == 'high'
        assert email['metadata']['category'] == 'technical'


class TestSendEmail:
    """Test send_email function"""

    def test_send_email_basic(self, reset_email_queue):
        """Test basic generic email"""
        from education_system.university_system.infrastructure.email.email_manager import send_email, _email_queue

        send_email(
            recipient='user@university.edu',
            subject='Test Subject',
            body='Test Body'
        )

        assert len(_email_queue) == 1
        email = _email_queue[0]
        assert email['type'] == 'generic'
        assert email['recipient'] == 'user@university.edu'
        assert email['subject'] == 'Test Subject'
        assert email['metadata']['body'] == 'Test Body'

    def test_send_email_none_values(self, reset_email_queue):
        """Test sending email with None values"""
        from education_system.university_system.infrastructure.email.email_manager import send_email, _email_queue

        send_email(recipient=None, subject=None, body=None)

        email = _email_queue[0]
        assert email['recipient'] is None
        assert email['subject'] is None
        assert email['metadata']['body'] is None

    def test_send_email_with_attachments(self, reset_email_queue):
        """Test sending email with attachments"""
        from education_system.university_system.infrastructure.email.email_manager import send_email, _email_queue

        send_email(
            recipient='user@university.edu',
            subject='Document',
            body='Please see attached',
            attachments=['/path/to/file.pdf']
        )

        email = _email_queue[0]
        assert email['metadata']['attachments'] == ['/path/to/file.pdf']


class TestSendConfirmationEmail:
    """Test send_confirmation_email function"""

    def test_send_confirmation_email_basic(self, reset_email_queue):
        """Test basic confirmation email"""
        from education_system.university_system.infrastructure.email.email_manager import send_confirmation_email, _email_queue

        send_confirmation_email(
            recipient='student@university.edu',
            confirmation_type='appointment',
            details={'date': '2025-01-15', 'time': '10:00'}
        )

        assert len(_email_queue) == 1
        email = _email_queue[0]
        assert email['type'] == 'confirmation'
        assert email['subject'] == 'Confirmation: appointment'
        assert email['metadata']['confirmation_type'] == 'appointment'
        assert email['metadata']['details']['date'] == '2025-01-15'

    def test_send_confirmation_email_no_type(self, reset_email_queue):
        """Test confirmation email with no confirmation type"""
        from education_system.university_system.infrastructure.email.email_manager import send_confirmation_email, _email_queue

        send_confirmation_email(
            recipient='student@university.edu',
            confirmation_type=None,
            details=None
        )

        email = _email_queue[0]
        assert email['subject'] == 'Confirmation: Action'
        assert email['metadata']['details'] == {}

    def test_send_confirmation_email_empty_details(self, reset_email_queue):
        """Test confirmation email with empty details"""
        from education_system.university_system.infrastructure.email.email_manager import send_confirmation_email, _email_queue

        send_confirmation_email(
            recipient='student@university.edu',
            confirmation_type='registration'
        )

        email = _email_queue[0]
        assert email['metadata']['details'] == {}


class TestSendReplyNotification:
    """Test send_reply_notification function"""

    def test_send_reply_notification_basic(self, reset_email_queue):
        """Test basic reply notification"""
        from education_system.university_system.infrastructure.email.email_manager import send_reply_notification, _email_queue

        send_reply_notification(
            ticket_id='12345',
            recipient='student@university.edu',
            reply_by='Support Agent'
        )

        assert len(_email_queue) == 1
        email = _email_queue[0]
        assert email['type'] == 'reply_notification'
        assert email['subject'] == 'New Reply to Ticket #12345'
        assert email['metadata']['ticket_id'] == '12345'
        assert email['metadata']['reply_by'] == 'Support Agent'

    def test_send_reply_notification_none_values(self, reset_email_queue):
        """Test reply notification with None values"""
        from education_system.university_system.infrastructure.email.email_manager import send_reply_notification, _email_queue

        send_reply_notification(
            ticket_id=None,
            recipient=None,
            reply_by=None
        )

        email = _email_queue[0]
        assert email['subject'] == 'New Reply to Ticket #None'


class TestSendSlaAlert:
    """Test send_sla_alert function"""

    def test_send_sla_alert_basic(self, reset_email_queue):
        """Test basic SLA alert"""
        from education_system.university_system.infrastructure.email.email_manager import send_sla_alert, _email_queue

        send_sla_alert(
            ticket_id='12345',
            recipient='manager@university.edu',
            sla_breach_type='warning',
            time_remaining='2 hours'
        )

        assert len(_email_queue) == 1
        email = _email_queue[0]
        assert email['type'] == 'sla_alert'
        assert email['subject'] == 'SLA warning for Ticket #12345'
        assert email['metadata']['sla_breach_type'] == 'warning'
        assert email['metadata']['time_remaining'] == '2 hours'

    def test_send_sla_alert_breach(self, reset_email_queue):
        """Test SLA breach alert"""
        from education_system.university_system.infrastructure.email.email_manager import send_sla_alert, _email_queue

        send_sla_alert(
            ticket_id='12345',
            recipient='manager@university.edu',
            sla_breach_type='breach',
            time_remaining='-1 hour'
        )

        email = _email_queue[0]
        assert email['subject'] == 'SLA breach for Ticket #12345'

    def test_send_sla_alert_no_breach_type(self, reset_email_queue):
        """Test SLA alert with no breach type"""
        from education_system.university_system.infrastructure.email.email_manager import send_sla_alert, _email_queue

        send_sla_alert(
            ticket_id='12345',
            recipient='manager@university.edu',
            sla_breach_type=None
        )

        email = _email_queue[0]
        assert email['subject'] == 'SLA Alert for Ticket #12345'


class TestSendSatisfactionSurvey:
    """Test send_satisfaction_survey function"""

    def test_send_satisfaction_survey_basic(self, reset_email_queue):
        """Test basic satisfaction survey"""
        from education_system.university_system.infrastructure.email.email_manager import send_satisfaction_survey, _email_queue

        send_satisfaction_survey(
            ticket_id='12345',
            recipient='student@university.edu',
            survey_link='/survey/12345'
        )

        assert len(_email_queue) == 1
        email = _email_queue[0]
        assert email['type'] == 'satisfaction_survey'
        assert email['subject'] == 'Please Rate Your Support Experience - Ticket #12345'
        assert email['metadata']['survey_link'] == '/survey/12345'

    def test_send_satisfaction_survey_no_link(self, reset_email_queue):
        """Test satisfaction survey without survey link"""
        from education_system.university_system.infrastructure.email.email_manager import send_satisfaction_survey, _email_queue

        send_satisfaction_survey(
            ticket_id='12345',
            recipient='student@university.edu',
            survey_link=None
        )

        email = _email_queue[0]
        assert email['metadata']['survey_link'] is None


class TestGetQueuedEmails:
    """Test get_queued_emails function"""

    def test_get_queued_emails_empty_queue(self, reset_email_queue):
        """Test getting emails from empty queue"""
        from education_system.university_system.infrastructure.email.email_manager import get_queued_emails

        emails = get_queued_emails()

        assert emails == []
        assert isinstance(emails, list)

    def test_get_queued_emails_with_limit(self, reset_email_queue):
        """Test getting emails with limit"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, get_queued_emails
        )

        # Queue 10 emails
        for i in range(10):
            send_email(
                recipient=f'user{i}@university.edu',
                subject=f'Test {i}',
                body='Test body'
            )

        # Get only 5
        emails = get_queued_emails(limit=5)

        assert len(emails) == 5

    def test_get_queued_emails_default_limit(self, reset_email_queue):
        """Test getting emails with default limit (100)"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, get_queued_emails
        )

        # Queue 50 emails
        for i in range(50):
            send_email(
                recipient=f'user{i}@university.edu',
                subject=f'Test {i}',
                body='Test body'
            )

        emails = get_queued_emails()

        assert len(emails) == 50

    def test_get_queued_emails_returns_last_n(self, reset_email_queue):
        """Test that get_queued_emails returns the last N emails"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, get_queued_emails
        )

        # Queue 10 emails
        for i in range(10):
            send_email(
                recipient=f'user{i}@university.edu',
                subject=f'Test {i}',
                body='Test body'
            )

        # Get last 3
        emails = get_queued_emails(limit=3)

        # Should get emails 7, 8, 9
        assert emails[0]['subject'] == 'Test 7'
        assert emails[1]['subject'] == 'Test 8'
        assert emails[2]['subject'] == 'Test 9'

    @patch('university_system.infrastructure.email.email_manager.logger')
    def test_get_queued_emails_logging(self, mock_logger, reset_email_queue):
        """Test that retrieval is logged"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, get_queued_emails
        )

        send_email(recipient='test@university.edu', subject='Test', body='Body')
        get_queued_emails(limit=10)

        mock_logger.debug.assert_called_with('Retrieved 1 queued emails')


class TestClearEmailQueue:
    """Test clear_email_queue function"""

    def test_clear_empty_queue(self, reset_email_queue):
        """Test clearing an empty queue"""
        from education_system.university_system.infrastructure.email.email_manager import clear_email_queue

        count = clear_email_queue()

        assert count == 0

    def test_clear_queue_with_emails(self, reset_email_queue):
        """Test clearing queue with emails"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, clear_email_queue, _email_queue
        )

        # Queue some emails
        for i in range(5):
            send_email(
                recipient=f'user{i}@university.edu',
                subject=f'Test {i}',
                body='Test body'
            )

        assert len(_email_queue) == 5

        count = clear_email_queue()

        assert count == 5
        assert len(_email_queue) == 0

    @patch('university_system.infrastructure.email.email_manager.logger')
    def test_clear_queue_logging(self, mock_logger, reset_email_queue):
        """Test that clearing is logged"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, clear_email_queue
        )

        send_email(recipient='test@university.edu', subject='Test', body='Body')
        count = clear_email_queue()

        mock_logger.info.assert_called_with(f'Cleared {count} emails from queue')

    def test_clear_queue_multiple_times(self, reset_email_queue):
        """Test clearing queue multiple times"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, clear_email_queue
        )

        # First batch
        for i in range(3):
            send_email(recipient=f'user{i}@university.edu', subject='Test', body='Body')
        assert clear_email_queue() == 3

        # Second batch
        for i in range(2):
            send_email(recipient=f'user{i}@university.edu', subject='Test', body='Body')
        assert clear_email_queue() == 2

        # Empty
        assert clear_email_queue() == 0


class TestEmailQueueMaxlen:
    """Test email queue maxlen behavior"""

    def test_queue_maxlen_enforced(self, reset_email_queue):
        """Test that queue maxlen is enforced (1000)"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, _email_queue
        )

        # Queue more than maxlen
        for i in range(1100):
            send_email(
                recipient=f'user{i}@university.edu',
                subject=f'Test {i}',
                body='Test body'
            )

        # Should only keep last 1000
        assert len(_email_queue) == 1000

        # Should have emails 100-1099
        emails = list(_email_queue)
        assert emails[0]['subject'] == 'Test 100'
        assert emails[-1]['subject'] == 'Test 1099'


class TestHandleExceptionDecorator:
    """Test handle_exception decorator"""

    def test_handle_exception_decorator_exists(self):
        """Test that handle_exception decorator is available"""
        from education_system.university_system.infrastructure.email.email_manager import handle_exception

        assert callable(handle_exception)

    def test_handle_exception_decorator_usage(self):
        """Test using handle_exception decorator"""
        from education_system.university_system.infrastructure.email.email_manager import handle_exception

        @handle_exception
        def test_function():
            return "success"

        # Should work normally
        result = test_function()
        assert result == "success"


class TestIntegration:
    """Integration tests for email manager"""

    def test_multiple_email_types_queued(self, reset_email_queue):
        """Test queuing multiple different types of emails"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_ticket_notification,
            send_confirmation_email,
            send_reply_notification,
            send_sla_alert,
            send_satisfaction_survey,
            get_queued_emails
        )

        send_ticket_notification(ticket_id='1', recipient='support@university.edu')
        send_confirmation_email(recipient='student@university.edu', confirmation_type='enrollment')
        send_reply_notification(ticket_id='1', recipient='student@university.edu')
        send_sla_alert(ticket_id='2', recipient='manager@university.edu')
        send_satisfaction_survey(ticket_id='3', recipient='student@university.edu')

        emails = get_queued_emails()
        assert len(emails) == 5
        assert emails[0]['type'] == 'ticket_notification'
        assert emails[1]['type'] == 'confirmation'
        assert emails[2]['type'] == 'reply_notification'
        assert emails[3]['type'] == 'sla_alert'
        assert emails[4]['type'] == 'satisfaction_survey'

    def test_queue_clear_and_refill(self, reset_email_queue):
        """Test clearing queue and refilling it"""
        from education_system.university_system.infrastructure.email.email_manager import (
            send_email, clear_email_queue, get_queued_emails
        )

        # First batch
        for i in range(5):
            send_email(recipient='test@university.edu', subject=f'Test {i}', body='Body')
        assert len(get_queued_emails()) == 5

        # Clear
        clear_email_queue()
        assert len(get_queued_emails()) == 0

        # Second batch
        for i in range(3):
            send_email(recipient='test@university.edu', subject=f'New {i}', body='Body')
        emails = get_queued_emails()
        assert len(emails) == 3
        assert all('New' in email['subject'] for email in emails)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
