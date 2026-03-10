"""
Comprehensive tests for security_alerts module.

Tests cover:
- SecurityAlertManager initialization and configuration
- ALERT_LEVELS ordering
- _parse_recipients() parsing comma-separated emails
- send_alert() multi-channel dispatch logic
- _format_alert_message() message formatting
- _send_email_alert() SMTP integration
- _send_slack_alert() webhook integration
- _send_sms_alert() Twilio integration
- Convenience functions: alert_suspicious_login, alert_brute_force_attempt, etc.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, call

from education_system.university_system.infrastructure.security.security_alerts import (
    SecurityAlertManager,
    get_alert_manager,
    send_security_alert,
    alert_suspicious_login,
    alert_brute_force_attempt,
    alert_unauthorized_access,
    alert_data_exfiltration,
    alert_account_lockout,
    alert_privilege_escalation,
    alert_configuration_change,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_global():
    """Reset the global alert manager singleton."""
    import education_system.university_system.infrastructure.security.security_alerts as mod
    mod._alert_manager = None
    yield
    mod._alert_manager = None


@pytest.fixture
def manager():
    """Create a SecurityAlertManager with controlled env vars."""
    with patch.dict(os.environ, {
        "SECURITY_ALERT_EMAILS": "admin@test.com, sec@test.com",
        "SECURITY_SLACK_WEBHOOK": "https://hooks.slack.com/test",
        "SECURITY_SMS_ENABLED": "false",
        "SECURITY_MIN_EMAIL_LEVEL": "MEDIUM",
        "SECURITY_MIN_SLACK_LEVEL": "LOW",
    }):
        yield SecurityAlertManager()


# ---------------------------------------------------------------------------
# ALERT_LEVELS
# ---------------------------------------------------------------------------

class TestAlertLevels:
    def test_level_ordering(self):
        levels = SecurityAlertManager.ALERT_LEVELS
        assert levels["LOW"] < levels["MEDIUM"] < levels["HIGH"] < levels["CRITICAL"]

    def test_all_levels_present(self):
        levels = SecurityAlertManager.ALERT_LEVELS
        assert set(levels.keys()) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ---------------------------------------------------------------------------
# _parse_recipients
# ---------------------------------------------------------------------------

class TestParseRecipients:
    def test_parses_comma_separated(self):
        mgr = SecurityAlertManager.__new__(SecurityAlertManager)
        result = mgr._parse_recipients("a@test.com, b@test.com, c@test.com")
        assert result == ["a@test.com", "b@test.com", "c@test.com"]

    def test_strips_whitespace(self):
        mgr = SecurityAlertManager.__new__(SecurityAlertManager)
        result = mgr._parse_recipients("  a@test.com ,  b@test.com  ")
        assert result == ["a@test.com", "b@test.com"]

    def test_empty_string(self):
        mgr = SecurityAlertManager.__new__(SecurityAlertManager)
        result = mgr._parse_recipients("")
        assert result == []

    def test_single_recipient(self):
        mgr = SecurityAlertManager.__new__(SecurityAlertManager)
        result = mgr._parse_recipients("admin@test.com")
        assert result == ["admin@test.com"]

    def test_filters_empty_entries(self):
        mgr = SecurityAlertManager.__new__(SecurityAlertManager)
        result = mgr._parse_recipients("a@test.com,,, ,b@test.com")
        assert result == ["a@test.com", "b@test.com"]


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestSecurityAlertManagerInit:
    def test_reads_email_recipients(self, manager):
        assert len(manager.alert_recipients) == 2
        assert "admin@test.com" in manager.alert_recipients

    def test_reads_slack_webhook(self, manager):
        assert manager.slack_webhook == "https://hooks.slack.com/test"

    def test_sms_disabled_by_default(self, manager):
        assert manager.sms_enabled is False

    @patch.dict(os.environ, {"SECURITY_SMS_ENABLED": "true"})
    def test_sms_enabled_from_env(self):
        mgr = SecurityAlertManager()
        assert mgr.sms_enabled is True

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_with_no_env(self):
        os.environ.pop("SECURITY_ALERT_EMAILS", None)
        os.environ.pop("SECURITY_SLACK_WEBHOOK", None)
        mgr = SecurityAlertManager()
        assert mgr.alert_recipients == []
        assert mgr.slack_webhook is None


# ---------------------------------------------------------------------------
# _format_alert_message
# ---------------------------------------------------------------------------

class TestFormatAlertMessage:
    def test_contains_level(self, manager):
        msg = manager._format_alert_message("HIGH", "Test Title", {"key": "val", "timestamp": "ts"})
        assert "HIGH" in msg

    def test_contains_title(self, manager):
        msg = manager._format_alert_message("LOW", "My Title", {"timestamp": "ts"})
        assert "My Title" in msg

    def test_contains_details(self, manager):
        msg = manager._format_alert_message("MEDIUM", "Test", {"ip": "1.2.3.4", "timestamp": "ts"})
        assert "1.2.3.4" in msg

    def test_contains_timestamp(self, manager):
        msg = manager._format_alert_message("LOW", "Test", {"timestamp": "2024-01-01T00:00:00"})
        assert "2024-01-01" in msg


# ---------------------------------------------------------------------------
# _send_email_alert
# ---------------------------------------------------------------------------

class TestSendEmailAlert:
    @patch("university_system.infrastructure.security.security_alerts.smtplib.SMTP")
    def test_success(self, mock_smtp_cls, manager):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = manager._send_email_alert("HIGH", "Alert!", "message body")
        assert result is True

    @patch("university_system.infrastructure.security.security_alerts.smtplib.SMTP")
    def test_failure(self, mock_smtp_cls, manager):
        mock_smtp_cls.side_effect = Exception("SMTP error")
        result = manager._send_email_alert("HIGH", "Alert!", "message body")
        assert result is False


# ---------------------------------------------------------------------------
# _send_slack_alert
# ---------------------------------------------------------------------------

class TestSendSlackAlert:
    @patch("university_system.infrastructure.security.security_alerts.requests")
    def test_success(self, mock_requests, manager):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response

        result = manager._send_slack_alert("HIGH", "Alert!", "message body")
        assert result is True

    @patch("university_system.infrastructure.security.security_alerts.requests")
    def test_failure(self, mock_requests, manager):
        mock_requests.post.side_effect = Exception("Network error")
        result = manager._send_slack_alert("HIGH", "Alert!", "message body")
        assert result is False

    def test_no_webhook_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SECURITY_SLACK_WEBHOOK", None)
            mgr = SecurityAlertManager()
            mgr.slack_webhook = None
            # The method checks REQUESTS_AVAILABLE, but won't be called if no webhook
            # Test the send_alert logic path instead
            with patch.object(mgr, "_send_email_alert", return_value=False):
                with patch.object(mgr, "_log_alert"):
                    with patch.object(mgr, "_log_to_immutable_audit"):
                        result = mgr.send_alert("LOW", "Test", {})
            assert result is False


# ---------------------------------------------------------------------------
# _send_sms_alert
# ---------------------------------------------------------------------------

class TestSendSmsAlert:
    def test_no_twilio_config_returns_false(self, manager):
        with patch.dict(os.environ, {}, clear=True):
            result = manager._send_sms_alert("Alert!", {})
            assert result is False

    @patch.dict(os.environ, {
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_FROM_NUMBER": "+1234567890",
        "SECURITY_SMS_NUMBERS": "+9876543210",
    })
    def test_twilio_import_error(self, manager):
        # twilio is not installed, so this should return False
        result = manager._send_sms_alert("Alert!", {})
        assert result is False


# ---------------------------------------------------------------------------
# send_alert - multi-channel orchestration
# ---------------------------------------------------------------------------

class TestSendAlert:
    def test_invalid_level_defaults_to_medium(self, manager):
        with patch.object(manager, "_format_alert_message", return_value="msg") as mock_fmt:
            with patch.object(manager, "_send_email_alert", return_value=True):
                with patch.object(manager, "_send_slack_alert", return_value=False):
                    with patch.object(manager, "_log_alert"):
                        with patch.object(manager, "_log_to_immutable_audit"):
                            result = manager.send_alert("INVALID", "Test", {})
        # Should have been called with 'MEDIUM'
        assert mock_fmt.call_args[0][0] == "MEDIUM"

    def test_email_sent_for_medium_and_above(self, manager):
        with patch.object(manager, "_send_email_alert", return_value=True) as mock_email:
            with patch.object(manager, "_send_slack_alert", return_value=False):
                with patch.object(manager, "_log_alert"):
                    with patch.object(manager, "_log_to_immutable_audit"):
                        manager.send_alert("HIGH", "Test", {})
        mock_email.assert_called_once()

    def test_email_not_sent_for_low(self, manager):
        manager.min_email_level = "MEDIUM"
        with patch.object(manager, "_send_email_alert") as mock_email:
            with patch.object(manager, "_send_slack_alert", return_value=False):
                with patch.object(manager, "_log_alert"):
                    with patch.object(manager, "_log_to_immutable_audit"):
                        manager.send_alert("LOW", "Test", {})
        mock_email.assert_not_called()

    def test_slack_sent_for_low(self, manager):
        with patch.object(manager, "_send_email_alert", return_value=False):
            with patch.object(manager, "_send_slack_alert", return_value=True) as mock_slack:
                with patch.object(manager, "_log_alert"):
                    with patch.object(manager, "_log_to_immutable_audit"):
                        result = manager.send_alert("LOW", "Test", {})
        mock_slack.assert_called_once()
        assert result is True

    def test_returns_true_if_any_channel_succeeds(self, manager):
        with patch.object(manager, "_send_email_alert", return_value=False):
            with patch.object(manager, "_send_slack_alert", return_value=True):
                with patch.object(manager, "_log_alert"):
                    with patch.object(manager, "_log_to_immutable_audit"):
                        assert manager.send_alert("HIGH", "Test", {}) is True

    def test_adds_timestamp_to_details(self, manager):
        details = {"key": "val"}
        with patch.object(manager, "_send_email_alert", return_value=False):
            with patch.object(manager, "_send_slack_alert", return_value=False):
                with patch.object(manager, "_log_alert"):
                    with patch.object(manager, "_log_to_immutable_audit"):
                        manager.send_alert("LOW", "Test", details)
        assert "timestamp" in details

    def test_adds_source_module(self, manager):
        details = {}
        with patch.object(manager, "_send_email_alert", return_value=False):
            with patch.object(manager, "_send_slack_alert", return_value=False):
                with patch.object(manager, "_log_alert"):
                    with patch.object(manager, "_log_to_immutable_audit"):
                        manager.send_alert("LOW", "Test", details, source_module="auth")
        assert details.get("source_module") == "auth"


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    @patch("university_system.infrastructure.security.security_alerts.get_alert_manager")
    def test_send_security_alert(self, mock_get_mgr):
        mock_mgr = MagicMock()
        mock_mgr.send_alert.return_value = True
        mock_get_mgr.return_value = mock_mgr

        result = send_security_alert("HIGH", "Title", {"k": "v"})
        assert result is True
        mock_mgr.send_alert.assert_called_once()

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_suspicious_login(self, mock_send):
        alert_suspicious_login(
            user_id="u1", ip_address="1.2.3.4",
            reason="impossible_travel", country="US"
        )
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]["level"] == "HIGH" or call_kwargs[0][0] == "HIGH"

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_brute_force_high(self, mock_send):
        alert_brute_force_attempt("admin", "1.2.3.4", attempts=5)
        call_args = mock_send.call_args
        assert call_args[1].get("level", call_args[0][0] if call_args[0] else None) == "HIGH"

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_brute_force_critical(self, mock_send):
        alert_brute_force_attempt("admin", "1.2.3.4", attempts=15)
        call_args = mock_send.call_args
        assert call_args[1].get("level", call_args[0][0] if call_args[0] else None) == "CRITICAL"
        assert call_args[1].get("notify_sms", False) is True

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_unauthorized_access(self, mock_send):
        alert_unauthorized_access("u1", "grades", "g123", "admin_read")
        mock_send.assert_called_once()

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_data_exfiltration_high(self, mock_send):
        alert_data_exfiltration("u1", "student_records", 500, "csv")
        call_args = mock_send.call_args
        assert call_args[1].get("level") == "HIGH"

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_data_exfiltration_critical(self, mock_send):
        alert_data_exfiltration("u1", "student_records", 5000, "csv")
        call_args = mock_send.call_args
        assert call_args[1].get("level") == "CRITICAL"

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_account_lockout(self, mock_send):
        alert_account_lockout("u1", "1.2.3.4", 5, 30)
        mock_send.assert_called_once()

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_privilege_escalation(self, mock_send):
        alert_privilege_escalation("u1", "student", "admin", "superadmin")
        mock_send.assert_called_once()

    @patch("university_system.infrastructure.security.security_alerts.send_security_alert")
    def test_alert_configuration_change(self, mock_send):
        alert_configuration_change("max_sessions", "5", "10", "admin")
        mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# get_alert_manager singleton
# ---------------------------------------------------------------------------

class TestGetAlertManager:
    def test_returns_same_instance(self):
        m1 = get_alert_manager()
        m2 = get_alert_manager()
        assert m1 is m2

    def test_returns_security_alert_manager(self):
        mgr = get_alert_manager()
        assert isinstance(mgr, SecurityAlertManager)
