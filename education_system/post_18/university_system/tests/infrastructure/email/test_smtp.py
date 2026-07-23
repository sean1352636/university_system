#!/usr/bin/env python3
"""
Comprehensive tests for SMTP Email Module
Tests email sending via SMTP with TLS, authentication, attachments, CC/BCC, and error handling
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_config():
    """Mock email configuration"""
    return {
        'sender_name': 'University System',
        'sender_email': 'noreply@university.edu',
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'use_tls': True,
        'use_authentication': True,
        'username': 'test@university.edu',
        'password': 'test_password'
    }


@pytest.fixture
def temp_attachment():
    """Create a temporary file for attachment testing"""
    fd, path = tempfile.mkstemp(suffix='.txt')
    os.write(fd, b'Test attachment content')
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except (OSError, IOError):
        pass


def _make_config_mock(values):
    """Create a mock config that supports .get() and [] access like a real dict."""
    mock = MagicMock()
    mock.get.side_effect = lambda key, default=None: values.get(key, default)
    mock.__getitem__.side_effect = lambda key: values[key]
    mock.__contains__.side_effect = lambda key: key in values
    return mock


class TestSendEmailViaSMTP:
    """Test send_email_via_smtp() function"""

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_simple_email_success(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test sending a simple email successfully"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        # Setup - use helper to make config.get() work properly
        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Call function
        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        # Assert
        assert result is True
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with('test@university.edu', 'test_password')
        mock_smtp_instance.sendmail.assert_called_once()

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_with_cc_recipients(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test sending email with CC recipients"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc='cc1@university.edu,cc2@university.edu',
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        # Verify CC was included in recipients
        assert result is True
        call_args = mock_smtp_instance.sendmail.call_args
        all_recipients = call_args[0][1]
        assert 'student@university.edu' in all_recipients
        assert 'cc1@university.edu' in all_recipients
        assert 'cc2@university.edu' in all_recipients

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_with_bcc_recipients(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test sending email with BCC recipients"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc='bcc1@university.edu,bcc2@university.edu',
            attachments=None,
            current_time=current_time
        )

        # Verify BCC was included in recipients
        assert result is True
        call_args = mock_smtp_instance.sendmail.call_args
        all_recipients = call_args[0][1]
        assert 'student@university.edu' in all_recipients
        assert 'bcc1@university.edu' in all_recipients
        assert 'bcc2@university.edu' in all_recipients

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_with_cc_and_bcc(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test sending email with both CC and BCC recipients"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc='cc@university.edu',
            bcc='bcc@university.edu',
            attachments=None,
            current_time=current_time
        )

        # Verify all recipients were included
        assert result is True
        call_args = mock_smtp_instance.sendmail.call_args
        all_recipients = call_args[0][1]
        assert len(all_recipients) == 3
        assert 'student@university.edu' in all_recipients
        assert 'cc@university.edu' in all_recipients
        assert 'bcc@university.edu' in all_recipients

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.os.path.exists', return_value=True)
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.open', new_callable=mock_open, read_data=b'file content')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.os.path.basename')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_with_single_attachment(self, mock_config_dict, mock_db_op, mock_smtp, mock_basename, mock_file, mock_exists, mock_config):
        """Test sending email with a single attachment"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        mock_basename.return_value = 'test.txt'
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments='/path/to/test.txt',
            current_time=current_time
        )

        assert result is True
        mock_file.assert_called()

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.os.path.exists', return_value=True)
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.open', new_callable=mock_open, read_data=b'file content')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.os.path.basename')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_with_multiple_attachments(self, mock_config_dict, mock_db_op, mock_smtp, mock_basename, mock_file, mock_exists, mock_config):
        """Test sending email with multiple attachments"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        mock_basename.side_effect = lambda x: x.split('/')[-1]
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments='/path/to/file1.txt,/path/to/file2.pdf',
            current_time=current_time
        )

        assert result is True
        # Should have opened both files
        assert mock_file.call_count >= 2

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_without_tls(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test sending email without TLS"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        config_no_tls = dict(mock_config)
        config_no_tls['use_tls'] = False
        config_no_tls['smtp_port'] = 25  # Non-TLS port (587/465 force TLS)
        mock_config_dict.get.side_effect = lambda key, default=None: config_no_tls.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: config_no_tls[key]

        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        # TLS should not be called
        mock_smtp_instance.starttls.assert_not_called()
        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_without_authentication(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test sending email without SMTP authentication"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        config_no_auth = dict(mock_config)
        config_no_auth['use_authentication'] = False
        mock_config_dict.get.side_effect = lambda key, default=None: config_no_auth.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: config_no_auth[key]

        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        # Login should not be called
        mock_smtp_instance.login.assert_not_called()
        assert result is True

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_smtp_connection_error(self, mock_config_dict, mock_smtp, mock_config):
        """Test handling of SMTP connection errors"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp.side_effect = Exception("SMTP connection failed")
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        assert result is False

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_authentication_error(self, mock_config_dict, mock_smtp, mock_config):
        """Test handling of SMTP authentication errors"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        mock_smtp_instance.login.side_effect = Exception("Authentication failed")
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        assert result is False

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_send_email_sendmail_error(self, mock_config_dict, mock_smtp, mock_config):
        """Test handling of sendmail errors"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        mock_smtp_instance.sendmail.side_effect = Exception("Sending failed")
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        assert result is False

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_email_message_structure(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test that email message is properly structured"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc='cc@university.edu',
            bcc='bcc@university.edu',
            attachments=None,
            current_time=current_time
        )

        # Get the email message that was sent
        call_args = mock_smtp_instance.sendmail.call_args
        msg_string = call_args[0][2]

        # Verify message contains expected headers
        assert 'From: University System <noreply@university.edu>' in msg_string
        assert 'To: student@university.edu' in msg_string
        assert 'Subject: Test Subject' in msg_string
        assert 'Cc: cc@university.edu' in msg_string
        assert 'Bcc: bcc@university.edu' in msg_string
        assert 'Test Body' in msg_string

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_database_logging_called(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test that database logging is called after successful send"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc='cc@university.edu',
            bcc='bcc@university.edu',
            attachments='/path/to/file.txt',
            current_time=current_time
        )

        assert result is True
        mock_db_op.assert_called_once()

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.ssl.create_default_context')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_ssl_context_used(self, mock_config_dict, mock_db_op, mock_smtp, mock_ssl_context, mock_config):
        """Test that SSL context is created and used for TLS"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        mock_ssl_context.assert_called_once()
        mock_smtp_instance.starttls.assert_called_once_with(context=mock_context)

    @patch('education_system.post_18.university_system.infrastructure.email.smtp.smtplib.SMTP')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.execute_db_operation')
    @patch('education_system.post_18.university_system.infrastructure.email.smtp.config')
    def test_attachment_file_not_found(self, mock_config_dict, mock_db_op, mock_smtp, mock_config):
        """Test handling of missing attachment files - file is silently skipped"""
        from education_system.post_18.university_system.infrastructure.email.smtp import send_email_via_smtp

        mock_config_dict.get.side_effect = lambda key, default=None: mock_config.get(key, default)
        mock_config_dict.__getitem__.side_effect = lambda key: mock_config[key]
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # The source code checks os.path.exists() and skips missing files,
        # so the email still sends successfully
        result = send_email_via_smtp(
            recipient_email='student@university.edu',
            subject='Test Subject',
            body='Test Body',
            cc=None,
            bcc=None,
            attachments='/nonexistent/file.txt',
            current_time=current_time
        )

        # Email sends successfully even with missing attachments (they're skipped)
        assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
