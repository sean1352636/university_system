"""
Comprehensive tests for communication_integration.py

Tests all unified communication wrappers for email, SMS,
domain-specific helpers, and migration functions.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call


class TestEmailIntegration:
    """Test email integration functions"""

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_as_system')
    def test_send_email_unified_simple(self, mock_send):
        """Test simple email sending"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_send.return_value = True

        result = send_email_unified(
            'test@example.com',
            'Test Subject',
            'Test body'
        )

        assert result is True
        mock_send.assert_called_once_with(
            'test@example.com',
            'Test Subject',
            'Test body',
            cc=None,
            bcc=None,
            attachments=None
        )

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_as_system')
    def test_send_email_unified_with_cc_bcc(self, mock_send):
        """Test email with CC and BCC"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_send.return_value = True

        result = send_email_unified(
            'test@example.com',
            'Test Subject',
            'Test body',
            cc=['cc@example.com'],
            bcc=['bcc@example.com']
        )

        assert result is True
        assert mock_send.call_args.kwargs['cc'] == ['cc@example.com']
        assert mock_send.call_args.kwargs['bcc'] == ['bcc@example.com']

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_as_system')
    def test_send_email_unified_with_attachments(self, mock_send):
        """Test email with attachments"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_send.return_value = True

        result = send_email_unified(
            'test@example.com',
            'Test Subject',
            'Test body',
            attachments=['/path/to/file.pdf']
        )

        assert result is True
        assert mock_send.call_args.kwargs['attachments'] == ['/path/to/file.pdf']

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_template_email')
    def test_send_email_unified_with_template(self, mock_template):
        """Test email with template"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_template.return_value = True

        result = send_email_unified(
            'test@example.com',
            'Subject',
            '',
            template_name='welcome',
            template_vars={'name': 'John'}
        )

        assert result is True
        mock_template.assert_called_once_with(
            'welcome',
            'test@example.com',
            {'name': 'John'},
            cc=None,
            bcc=None,
            attachments=None
        )

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email')
    def test_send_email_unified_user_sender(self, mock_send):
        """Test email with user sender type"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_send.return_value = True

        result = send_email_unified(
            'test@example.com',
            'Subject',
            'Body',
            sender_type='user'
        )

        assert result is True
        mock_send.assert_called_once()

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_as_system')
    def test_send_email_unified_error_fallback(self, mock_send, capsys):
        """Test email error fallback to console"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_send.side_effect = Exception("Email service error")

        result = send_email_unified(
            'test@example.com',
            'Subject',
            'Body content'
        )

        assert result is False
        captured = capsys.readouterr()
        assert "[EMAIL FALLBACK]" in captured.out
        assert "test@example.com" in captured.out

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_bulk')
    def test_send_bulk_email_unified(self, mock_bulk):
        """Test bulk email sending"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_bulk_email_unified

        recipients = ['test1@example.com', 'test2@example.com']
        result = send_bulk_email_unified(recipients, 'template_name')

        assert result == {'sent': 2, 'failed': 0}
        mock_bulk.assert_called_once_with(recipients, 'template_name', None)

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_bulk')
    def test_send_bulk_email_with_vars(self, mock_bulk):
        """Test bulk email with template vars"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_bulk_email_unified

        recipients = ['test1@example.com', 'test2@example.com']
        template_vars_list = [{'name': 'John'}, {'name': 'Jane'}]

        result = send_bulk_email_unified(
            recipients,
            'template_name',
            template_vars_list=template_vars_list
        )

        assert result == {'sent': 2, 'failed': 0}

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_bulk')
    def test_send_bulk_email_error(self, mock_bulk):
        """Test bulk email error handling"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_bulk_email_unified

        mock_bulk.side_effect = Exception("Bulk send error")
        recipients = ['test1@example.com', 'test2@example.com']

        result = send_bulk_email_unified(recipients, 'template_name')

        assert result == {'sent': 0, 'failed': 2}

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.queue_email')
    def test_queue_email_unified(self, mock_queue):
        """Test queueing email"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import queue_email_unified

        result = queue_email_unified(
            'test@example.com',
            'Subject',
            'Body'
        )

        assert result is True
        mock_queue.assert_called_once_with('test@example.com', 'Subject', 'Body')

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.queue_email')
    def test_queue_email_error(self, mock_queue):
        """Test queue email error handling"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import queue_email_unified

        mock_queue.side_effect = Exception("Queue error")

        result = queue_email_unified('test@example.com', 'Subject', 'Body')

        assert result is False


class TestSMSIntegration:
    """Test SMS integration functions"""

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms')
    def test_send_sms_unified_simple(self, mock_send):
        """Test simple SMS sending"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_sms_unified

        mock_send.return_value = True

        result = send_sms_unified('+447123456789', 'Test message')

        assert result is True
        mock_send.assert_called_once_with(
            '+447123456789',
            'Test message',
            student_id=None,
            related_to=None
        )

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms')
    def test_send_sms_unified_with_metadata(self, mock_send):
        """Test SMS with student_id and related_to"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_sms_unified

        mock_send.return_value = True

        result = send_sms_unified(
            '+447123456789',
            'Test message',
            student_id='STU001',
            related_to='calendar'
        )

        assert result is True
        mock_send.assert_called_once_with(
            '+447123456789',
            'Test message',
            student_id='STU001',
            related_to='calendar'
        )

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms')
    def test_send_sms_unified_error_fallback(self, mock_send, capsys):
        """Test SMS error fallback to console"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_sms_unified

        mock_send.side_effect = Exception("SMS service error")

        result = send_sms_unified('+447123456789', 'Test message')

        assert result is False
        captured = capsys.readouterr()
        assert "[SMS FALLBACK]" in captured.out
        assert "+447123456789" in captured.out

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_bulk_sms')
    def test_send_bulk_sms_unified(self, mock_bulk):
        """Test bulk SMS sending"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_bulk_sms_unified

        mock_bulk.return_value = {'sent': 2, 'failed': 0}
        recipients = ['+447123456789', '+447987654321']

        result = send_bulk_sms_unified(recipients, 'Test message')

        assert result == {'sent': 2, 'failed': 0}
        mock_bulk.assert_called_once_with(
            recipients,
            'Test message',
            student_ids=None,
            related_to=None
        )

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_bulk_sms')
    def test_send_bulk_sms_with_metadata(self, mock_bulk):
        """Test bulk SMS with metadata"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_bulk_sms_unified

        mock_bulk.return_value = {'sent': 2, 'failed': 0}
        recipients = ['+447123456789', '+447987654321']
        student_ids = ['STU001', 'STU002']

        result = send_bulk_sms_unified(
            recipients,
            'Test message',
            student_ids=student_ids,
            related_to='library'
        )

        assert result == {'sent': 2, 'failed': 0}

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_bulk_sms')
    def test_send_bulk_sms_error(self, mock_bulk):
        """Test bulk SMS error handling"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_bulk_sms_unified

        mock_bulk.side_effect = Exception("Bulk SMS error")
        recipients = ['+447123456789', '+447987654321']

        result = send_bulk_sms_unified(recipients, 'Test message')

        assert result == {'sent': 0, 'failed': 2}


class TestLibraryNotifications:
    """Test library notification helper"""

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_library_notification_due_soon_email(self, mock_email):
        """Test library due soon notification via email"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_library_notification

        mock_email.return_value = True

        result = send_library_notification(
            'STU001',
            'due_soon',
            'Python Programming',
            due_date='2025-01-15',
            email='student@example.com',
            via='email'
        )

        assert result is True
        mock_email.assert_called_once()
        call_args = mock_email.call_args
        assert 'due on 2025-01-15' in call_args[0][2]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    def test_library_notification_due_soon_sms(self, mock_sms):
        """Test library due soon notification via SMS"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_library_notification

        mock_sms.return_value = True

        result = send_library_notification(
            'STU001',
            'due_soon',
            'Python Programming',
            due_date='2025-01-15',
            phone='+447123456789',
            via='sms'
        )

        assert result is True
        mock_sms.assert_called_once()
        call_args = mock_sms.call_args
        assert '2025-01-15' in call_args[0][1]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_library_notification_overdue(self, mock_email):
        """Test library overdue notification"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_library_notification

        mock_email.return_value = True

        result = send_library_notification(
            'STU001',
            'overdue',
            'Python Programming',
            days_overdue=5,
            email='student@example.com'
        )

        assert result is True
        call_args = mock_email.call_args
        assert '5 days overdue' in call_args[0][2]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.render_template')
    def test_library_notification_reservation_ready(self, mock_render, mock_email):
        """Test library reservation ready notification"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_library_notification

        mock_render.return_value = ('Reservation Ready', 'Your book "Python Programming" is ready for pickup.')
        mock_email.return_value = True

        result = send_library_notification(
            'STU001',
            'reservation_ready',
            'Python Programming',
            email='student@example.com'
        )

        assert result is True
        call_args = mock_email.call_args
        assert 'ready for pickup' in call_args[0][2]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_library_notification_checkout(self, mock_email):
        """Test library checkout notification"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_library_notification

        mock_email.return_value = True

        result = send_library_notification(
            'STU001',
            'checkout',
            'Python Programming',
            due_date='2025-01-15',
            email='student@example.com'
        )

        assert result is True
        call_args = mock_email.call_args
        assert 'checked out' in call_args[0][2]

    def test_library_notification_unknown_type(self):
        """Test library notification with unknown type"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_library_notification

        result = send_library_notification(
            'STU001',
            'unknown_type',
            'Python Programming',
            email='student@example.com'
        )

        assert result is False

    def test_library_notification_no_contact_method(self):
        """Test library notification with no contact method"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_library_notification

        result = send_library_notification(
            'STU001',
            'due_soon',
            'Python Programming',
            due_date='2025-01-15'
        )

        assert result is False


class TestCalendarReminder:
    """Test calendar reminder helper"""

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.render_template')
    def test_calendar_reminder_email(self, mock_render, mock_email):
        """Test calendar reminder via email"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_calendar_reminder

        mock_render.return_value = ('Calendar Reminder', 'Reminder: Final Exam on 2025-01-20 at 09:00\nLocation: Room 101')
        mock_email.return_value = True

        result = send_calendar_reminder(
            'STU001',
            'Final Exam',
            '2025-01-20',
            '09:00',
            location='Room 101',
            email='student@example.com',
            via='email'
        )

        assert result is True
        call_args = mock_email.call_args
        assert 'Final Exam' in call_args[0][2]
        assert '2025-01-20' in call_args[0][2]
        assert 'Room 101' in call_args[0][2]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    def test_calendar_reminder_sms(self, mock_sms):
        """Test calendar reminder via SMS"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_calendar_reminder

        mock_sms.return_value = True

        result = send_calendar_reminder(
            'STU001',
            'Final Exam',
            '2025-01-20',
            '09:00',
            location='Room 101',
            phone='+447123456789',
            via='sms'
        )

        assert result is True
        call_args = mock_sms.call_args
        assert 'Final Exam' in call_args[0][1]
        assert 'Room 101' in call_args[0][1]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_calendar_reminder_without_location(self, mock_email):
        """Test calendar reminder without location"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_calendar_reminder

        mock_email.return_value = True

        result = send_calendar_reminder(
            'STU001',
            'Final Exam',
            '2025-01-20',
            '09:00',
            email='student@example.com'
        )

        assert result is True
        call_args = mock_email.call_args
        # Should not contain location
        assert 'Final Exam' in call_args[0][2]

    def test_calendar_reminder_no_contact(self):
        """Test calendar reminder with no contact method"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_calendar_reminder

        result = send_calendar_reminder(
            'STU001',
            'Final Exam',
            '2025-01-20',
            '09:00'
        )

        assert result is False


class TestRestaurantNotifications:
    """Test restaurant notification helper"""

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.render_template')
    def test_restaurant_order_confirmation(self, mock_render, mock_email):
        """Test restaurant order confirmation"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_restaurant_notification

        mock_render.return_value = ('Order Confirmation - ORD123', 'Thank you for your order!\nTotal: £25.50\nItems: 2 x Pizza')
        mock_email.return_value = True

        result = send_restaurant_notification(
            'CUST001',
            'order_confirmation',
            order_id='ORD123',
            email='customer@example.com',
            details={'total': 25.50, 'items': '2 x Pizza'}
        )

        assert result is True
        call_args = mock_email.call_args
        assert 'ORD123' in call_args[0][1]
        assert '25.50' in call_args[0][2]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_restaurant_reservation_confirmation(self, mock_email):
        """Test restaurant reservation confirmation"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_restaurant_notification

        mock_email.return_value = True

        result = send_restaurant_notification(
            'CUST001',
            'reservation_confirmation',
            reservation_id='RES456',
            email='customer@example.com',
            details={
                'date': '2025-01-20',
                'time': '19:00',
                'guests': 4
            }
        )

        assert result is True
        call_args = mock_email.call_args
        assert 'RES456' in call_args[0][1]
        assert '2025-01-20' in call_args[0][2]

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_restaurant_loyalty_update(self, mock_email):
        """Test restaurant loyalty update"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_restaurant_notification

        mock_email.return_value = True

        result = send_restaurant_notification(
            'CUST001',
            'loyalty_update',
            email='customer@example.com',
            details={'points': 150}
        )

        assert result is True
        call_args = mock_email.call_args
        assert '150' in call_args[0][2]

    def test_restaurant_unknown_type(self):
        """Test restaurant notification with unknown type"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_restaurant_notification

        result = send_restaurant_notification(
            'CUST001',
            'unknown_type',
            email='customer@example.com'
        )

        assert result is False

    def test_restaurant_no_email(self):
        """Test restaurant notification with no email"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_restaurant_notification

        result = send_restaurant_notification(
            'CUST001',
            'order_confirmation',
            order_id='ORD123'
        )

        assert result is False


class TestMigrationHelpers:
    """Test migration helper functions"""

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_migrate_standalone_email(self, mock_email):
        """Test migrating standalone email function"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import migrate_standalone_email

        mock_email.return_value = True

        result = migrate_standalone_email(
            'old_send_email',
            'test@example.com',
            'Subject',
            'Body'
        )

        assert result is True
        mock_email.assert_called_once_with(
            'test@example.com',
            'Subject',
            'Body'
        )

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_unified')
    def test_migrate_standalone_email_with_kwargs(self, mock_email):
        """Test migrating standalone email with kwargs"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import migrate_standalone_email

        mock_email.return_value = True

        result = migrate_standalone_email(
            'old_send_email',
            'test@example.com',
            'Subject',
            'Body',
            cc=['cc@example.com']
        )

        assert result is True
        assert mock_email.call_args.kwargs['cc'] == ['cc@example.com']

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    def test_migrate_standalone_sms(self, mock_sms):
        """Test migrating standalone SMS function"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import migrate_standalone_sms

        mock_sms.return_value = True

        result = migrate_standalone_sms(
            'old_send_sms',
            '+447123456789',
            'Test message'
        )

        assert result is True
        mock_sms.assert_called_once_with(
            '+447123456789',
            'Test message'
        )

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms_unified')
    def test_migrate_standalone_sms_with_kwargs(self, mock_sms):
        """Test migrating standalone SMS with kwargs"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import migrate_standalone_sms

        mock_sms.return_value = True

        result = migrate_standalone_sms(
            'old_send_sms',
            '+447123456789',
            'Test message',
            student_id='STU001'
        )

        assert result is True
        assert mock_sms.call_args.kwargs['student_id'] == 'STU001'


class TestEdgeCases:
    """Test edge cases and error scenarios"""

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_as_system')
    def test_send_email_with_empty_body(self, mock_send):
        """Test sending email with empty body"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_send.return_value = True

        result = send_email_unified('test@example.com', 'Subject', '')

        assert result is True

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_sms')
    def test_send_sms_with_long_message(self, mock_send):
        """Test sending SMS with long message"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_sms_unified

        mock_send.return_value = True
        long_message = 'X' * 1600  # Max SMS length

        result = send_sms_unified('+447123456789', long_message)

        assert result is True

    @patch('education_system.post_18.university_system.modules.shared.utils.communication_integration.send_email_as_system')
    def test_send_email_with_template_no_vars(self, mock_send):
        """Test template email with empty vars dict falls back to regular send (empty dict is falsy)"""
        from education_system.post_18.university_system.modules.shared.utils.communication_integration import send_email_unified

        mock_send.return_value = True

        result = send_email_unified(
            'test@example.com',
            'Subject',
            '',
            template_name='simple_template',
            template_vars={}
        )

        assert result is True
        mock_send.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
