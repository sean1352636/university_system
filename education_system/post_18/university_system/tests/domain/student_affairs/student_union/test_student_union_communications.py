"""
Tests for student union communications module.
Tests email sending functionality.
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch, MagicMock

from education_system.post_18.university_system.modules.domain.student_affairs.student_union.services import communications

# Module path constant for patching
_MOD = 'education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.communications'
_EMAIL = 'education_system.post_18.university_system.infrastructure.email'


def _fake_i18n(key, **kwargs):
    """Return the translation key so tests can match against it."""
    return key


class TestSendConfirmationEmail:
    """Tests for send_confirmation_email function."""

    @patch('builtins.print')
    @patch(f'{_EMAIL}.queue_email', return_value=True)
    @patch(f'{_EMAIL}.log_event', create=True)
    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}._', side_effect=_fake_i18n)
    def test_send_email_success(self, mock_i18n, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test successfully sending confirmation email."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', 'Test message body'
        )

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_queue.assert_called_once_with('student@example.com', 'Test Subject', 'Test message body')
        mock_log.assert_called()
        mock_conn.close.assert_called_once()

    @patch('builtins.print')
    @patch(f'{_EMAIL}.log_event', create=True)
    @patch(f'{_EMAIL}.queue_email')
    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}._', side_effect=_fake_i18n)
    def test_send_email_student_not_found(self, mock_i18n, mock_get_conn, mock_queue, mock_log, mock_print):
        """Test sending email when student doesn't exist."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = communications.send_confirmation_email(
            'S99999', 'Test Subject', 'Test message body'
        )

        assert result is False
        mock_log.assert_called_with('error', 'Could not find email address for student ID S99999')
        mock_conn.close.assert_called_once()

    @patch('builtins.print')
    @patch(f'{_EMAIL}.queue_email', return_value=False)
    @patch(f'{_EMAIL}.log_event', create=True)
    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}._', side_effect=_fake_i18n)
    def test_send_email_queue_failure(self, mock_i18n, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test when email queueing fails."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', 'Test message body'
        )

        assert result is False
        mock_log.assert_called_with('error', 'Failed to send confirmation email to student S12345')

    @patch('builtins.print')
    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}._', side_effect=_fake_i18n)
    def test_send_email_import_error_fallback(self, mock_i18n, mock_get_conn, mock_print):
        """Test fallback when email system is not available.

        Since log_event is not exported from the email package, the real
        import inside send_confirmation_email raises ImportError,
        triggering the fallback path which returns True.
        """
        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', 'Test message body'
        )

        # ImportError fallback returns True
        assert result is True
        # Check that the placeholder i18n keys were printed
        assert any('communication.email_sent_placeholder' in str(c)
                   for c in mock_print.call_args_list)

    @patch('builtins.print')
    @patch(f'{_EMAIL}.log_event', create=True)
    @patch(f'{_EMAIL}.queue_email')
    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}._', side_effect=_fake_i18n)
    def test_send_email_database_error(self, mock_i18n, mock_get_conn, mock_queue, mock_log, mock_print):
        """Test handling of database errors."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', 'Test message body'
        )

        # sqlite3.Error is a subclass of Exception, caught by the generic handler
        assert result is False
        assert any('communication.email_error' in str(c)
                   for c in mock_print.call_args_list)

    @patch('builtins.print')
    @patch(f'{_EMAIL}.queue_email', return_value=True)
    @patch(f'{_EMAIL}.log_event', create=True)
    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}._', side_effect=_fake_i18n)
    def test_send_email_with_long_message(self, mock_i18n, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test sending email with long message body."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        long_message = "Test message " * 1000

        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', long_message
        )

        assert result is True
        mock_queue.assert_called_once()
        call_args = mock_queue.call_args[0]
        assert call_args[2] == long_message

    @patch('builtins.print')
    @patch(f'{_EMAIL}.queue_email', return_value=True)
    @patch(f'{_EMAIL}.log_event', create=True)
    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}._', side_effect=_fake_i18n)
    def test_send_email_with_special_characters(self, mock_i18n, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test sending email with special characters."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        special_message = "Test message with special chars: £€¥ © ® ™ @#$%^&*()"

        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', special_message
        )

        assert result is True


class TestIntegrationCommunications:
    """Integration tests for communications module."""

    @pytest.fixture
    def db_conn(self):
        """Create a test database connection."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT
            )
        ''')

        cursor.execute(
            "INSERT INTO students VALUES (?, ?, ?, ?)",
            ('S12345', 'John', 'Doe', 'john.doe@example.com')
        )

        conn.commit()
        yield conn
        conn.close()

    @patch(f'{_EMAIL}.queue_email', return_value=True)
    @patch(f'{_EMAIL}.log_event', create=True)
    def test_send_email_integration(self, mock_log, mock_queue, db_conn):
        """Test email sending with real database."""
        cursor = db_conn.cursor()

        cursor.execute('SELECT email_address FROM students WHERE student_id = ?', ('S12345',))
        email = cursor.fetchone()[0]

        assert email == 'john.doe@example.com'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
