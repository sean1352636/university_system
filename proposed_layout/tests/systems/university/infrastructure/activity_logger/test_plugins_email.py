"""Tests for plugins.email.EmailNotificationPlugin"""
from unittest.mock import patch, MagicMock

from education_system.systems.university.infrastructure.utils.activity_logger.plugins.email import (
    EmailNotificationPlugin,
)


def _full_config(**over):
    cfg = {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "u",
        "smtp_password": "p",
        "from_email": "a@x.com",
        "to_emails": ["b@x.com", "c@x.com"],
        "rate_limit_seconds": 600,
    }
    cfg.update(over)
    return cfg


class TestEmailPluginConfiguration:
    def test_is_configured_true(self):
        p = EmailNotificationPlugin(_full_config())
        assert p._is_configured() is True

    def test_is_configured_false_when_missing(self):
        p = EmailNotificationPlugin({"smtp_server": "x"})
        assert p._is_configured() is False


class TestAfterLog:
    def test_skipped_when_unsuccessful(self, make_log_entry):
        p = EmailNotificationPlugin(_full_config())
        with patch.object(p, "_send_email_notification") as m:
            p.after_log(make_log_entry(security_level="CRITICAL"), success=False)
            m.assert_not_called()

    def test_skipped_when_not_critical(self, make_log_entry):
        p = EmailNotificationPlugin(_full_config())
        with patch.object(p, "_send_email_notification") as m:
            p.after_log(make_log_entry(security_level="LOW"), success=True)
            m.assert_not_called()

    def test_skipped_when_not_configured(self, make_log_entry):
        p = EmailNotificationPlugin({})
        with patch.object(p, "_send_email_notification") as m:
            p.after_log(make_log_entry(security_level="CRITICAL"), success=True)
            m.assert_not_called()

    def test_invokes_send_for_critical(self, make_log_entry):
        p = EmailNotificationPlugin(_full_config())
        with patch.object(p, "_send_email_notification") as m:
            p.after_log(make_log_entry(security_level="CRITICAL"), success=True)
            m.assert_called_once()


class TestRateLimiting:
    def test_rate_limit_blocks_repeats(self, make_log_entry):
        p = EmailNotificationPlugin(_full_config(rate_limit_seconds=600))
        with patch(
            "education_system.systems.university.infrastructure.email.smtp.send_email_via_smtp",
            return_value=True,
        ) as send_mock:
            entry = make_log_entry(security_level="CRITICAL")
            p._send_email_notification(entry)
            p._send_email_notification(entry)
            assert send_mock.call_count == 1


class TestSendEmail:
    def test_sends_via_smtp_with_cc(self, make_log_entry):
        p = EmailNotificationPlugin(_full_config())
        with patch(
            "education_system.systems.university.infrastructure.email.smtp.send_email_via_smtp",
            return_value=True,
        ) as send_mock, patch(
            "education_system.systems.university.infrastructure.email.template_utils.render_template",
            side_effect=Exception("no template"),
        ):
            p._send_email_notification(make_log_entry(security_level="CRITICAL"))
            kwargs = send_mock.call_args.kwargs
            assert kwargs["recipient_email"] == "b@x.com"
            assert kwargs["cc"] == ["c@x.com"]
            assert "CRITICAL" in kwargs["subject"]

    def test_handles_send_exception(self, make_log_entry, capsys):
        p = EmailNotificationPlugin(_full_config())
        with patch(
            "education_system.systems.university.infrastructure.email.smtp.send_email_via_smtp",
            side_effect=RuntimeError("boom"),
        ):
            # Should not raise
            p._send_email_notification(make_log_entry(security_level="CRITICAL"))
