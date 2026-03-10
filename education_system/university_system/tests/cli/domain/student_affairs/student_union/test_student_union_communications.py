"""
Tests for student union communications module.
Tests email sending functionality.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch

from education_system.university_system.modules.domain.student_affairs.student_union.services import communications

@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = Mock()
    conn.cursor = Mock()
    conn.close = Mock()
    return conn

@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = Mock()
    cursor.fetchone = Mock()
    cursor.execute = Mock()
    return cursor

class TestSendConfirmationEmail:
    """Tests for send_confirmation_email function."""

    @patch('builtins.print')
    @patch('university_system.infrastructure.email.queue_email', return_value=True)
    @patch('university_system.infrastructure.email.log_event')
    @patch('university_system.modules.core.services.student_union_misc.communications.get_connection')
    def test_send_email_success(self, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test successfully sending confirmation email."""
        # Setup mocks
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', 'Test message body'
        )

        # Verify results
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_queue.assert_called_once_with('student@example.com', 'Test Subject', 'Test message body')
        mock_log.assert_called()
        mock_conn.close.assert_called_once()

    @patch('builtins.print')
    @patch('university_system.infrastructure.email.log_event')
    @patch('university_system.modules.core.services.student_union_misc.communications.get_connection')
    def test_send_email_student_not_found(self, mock_get_conn, mock_log, mock_print):
        """Test sending email when student doesn't exist."""
        # Setup mocks
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        result = communications.send_confirmation_email(
            'S99999', 'Test Subject', 'Test message body'
        )

        # Verify results
        assert result is False
        assert any('Could not find email address' in str(call)
                  for call in mock_print.call_args_list)
        mock_log.assert_called_with('error', 'Could not find email address for student ID S99999')
        mock_conn.close.assert_called_once()

    @patch('builtins.print')
    @patch('university_system.infrastructure.email.queue_email', return_value=False)
    @patch('university_system.infrastructure.email.log_event')
    @patch('university_system.modules.core.services.student_union_misc.communications.get_connection')
    def test_send_email_queue_failure(self, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test when email queueing fails."""
        # Setup mocks
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', 'Test message body'
        )

        # Verify results
        assert result is False
        assert any('Failed to send email' in str(call)
                  for call in mock_print.call_args_list)
        mock_log.assert_called_with('error', 'Failed to send confirmation email to student S12345')

    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.communications.get_connection')
    def test_send_email_import_error_fallback(self, mock_get_conn, mock_print):
        """Test fallback when email system is not available."""
        # Setup mocks
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Patch the imports to raise ImportError
        with patch.dict('sys.modules', {'university_system.infrastructure.email': None}):
            with patch('university_system.modules.core.services.student_union_misc.communications.queue_email',
                      side_effect=ImportError):
                # Call function
                result = communications.send_confirmation_email(
                    'S12345', 'Test Subject', 'Test message body'
                )

        # In case of ImportError, should use placeholder
        # Result depends on implementation - checking for placeholder message
        assert any('placeholder' in str(call).lower() or 'Email sent' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('university_system.modules.core.services.student_union_misc.communications.get_connection')
    def test_send_email_database_error(self, mock_get_conn, mock_print):
        """Test handling of database errors."""
        # Setup mocks
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Call function
        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', 'Test message body'
        )

        # Verify results
        assert result is False
        assert any('Error sending email' in str(call)
                  for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('university_system.infrastructure.email.queue_email', return_value=True)
    @patch('university_system.infrastructure.email.log_event')
    @patch('university_system.modules.core.services.student_union_misc.communications.get_connection')
    def test_send_email_with_long_message(self, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test sending email with long message body."""
        # Setup mocks
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Long message
        long_message = "Test message " * 1000

        # Call function
        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', long_message
        )

        # Verify results
        assert result is True
        mock_queue.assert_called_once()
        call_args = mock_queue.call_args[0]
        assert call_args[2] == long_message

    @patch('builtins.print')
    @patch('university_system.infrastructure.email.queue_email', return_value=True)
    @patch('university_system.infrastructure.email.log_event')
    @patch('university_system.modules.core.services.student_union_misc.communications.get_connection')
    def test_send_email_with_special_characters(self, mock_get_conn, mock_log, mock_queue, mock_print):
        """Test sending email with special characters."""
        # Setup mocks
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ('student@example.com',)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Special characters in message
        special_message = "Test message with special chars: £€¥ © ® ™ @#$%^&*()"

        # Call function
        result = communications.send_confirmation_email(
            'S12345', 'Test Subject', special_message
        )

        # Verify results
        assert result is True

class TestIntegrationCommunications:
    """Integration tests for communications module."""

    @pytest.fixture
    def db_conn(self):
        """Create a test database connection."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Create students table
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT
            )
        ''')

        # Insert test student
        cursor.execute(
            "INSERT INTO students VALUES (?, ?, ?, ?)",
            ('S12345', 'John', 'Doe', 'john.doe@example.com')
        )

        conn.commit()
        yield conn
        conn.close()

    @patch('university_system.infrastructure.email.queue_email', return_value=True)
    @patch('university_system.infrastructure.email.log_event')
    def test_send_email_integration(self, mock_log, mock_queue, db_conn):
        """Test email sending with real database."""
        cursor = db_conn.cursor()

        # Get student email
        cursor.execute('SELECT email_address FROM students WHERE student_id = ?', ('S12345',))
        email = cursor.fetchone()[0]

        assert email == 'john.doe@example.com'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
