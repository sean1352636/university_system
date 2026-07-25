"""Tests for simple_activity_logger.plugins.email."""
import sys
from unittest.mock import MagicMock, patch

from education_system.systems.university.infrastructure.utils.activity_logger.plugins.email import (
    EmailNotificationPlugin,
)
from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry


def _entry(**o):
    base = dict(
        timestamp="t", user_id="u", username="alice", role="user",
        action="login", module="auth", details="d", status="success",
        log_level="INFO", session_id="s", ip_address="1.1.1.1",
        user_agent="UA", request_size=0, response_size=0,
        processing_time=0.0, geolocation={}, security_level="CRITICAL",
        trace_id="t",
    )
    base.update(o)
    return LogEntry(**base)


def _configured():
    return EmailNotificationPlugin({
        "smtp_server": "smtp.example.com",
        "smtp_username": "u",
        "smtp_password": "p",
        "from_email": "from@x",
        "to_emails": ["a@x", "b@x"],
    })


class TestEmailNotificationConfig:
    def test_unconfigured_when_missing_fields(self):
        p = EmailNotificationPlugin({})
        assert p._is_configured() is False

    def test_configured_when_all_present(self):
        assert _configured()._is_configured() is True


class TestEmailNotificationSending:
    def _patch_smtp(self, return_value=True):
        fake_smtp = MagicMock()
        fake_smtp.send_email_via_smtp.return_value = return_value
        return patch.dict(
            sys.modules,
            {"education_system.systems.university.infrastructure.email.smtp": fake_smtp},
        ), fake_smtp

    def test_skips_when_not_configured(self):
        p = EmailNotificationPlugin({})
        p.after_log(_entry(), True)  # must not raise

    def test_skips_on_failure(self):
        p = _configured()
        ctx, smtp = self._patch_smtp()
        with ctx:
            p.after_log(_entry(), success=False)
        smtp.send_email_via_smtp.assert_not_called()

    def test_skips_non_critical(self):
        p = _configured()
        ctx, smtp = self._patch_smtp()
        with ctx:
            p.after_log(_entry(security_level="HIGH"), True)
        smtp.send_email_via_smtp.assert_not_called()

    def test_sends_for_critical(self):
        p = _configured()
        ctx, smtp = self._patch_smtp()
        with ctx:
            p.after_log(_entry(), True)
        smtp.send_email_via_smtp.assert_called_once()
        kwargs = smtp.send_email_via_smtp.call_args.kwargs
        assert kwargs["recipient_email"] == "a@x"
        assert kwargs["cc"] == ["b@x"]

    def test_rate_limit_blocks_repeats(self):
        p = EmailNotificationPlugin({
            "smtp_server": "x", "smtp_username": "u", "smtp_password": "p",
            "from_email": "f", "to_emails": ["t"], "rate_limit_seconds": 9999,
        })
        ctx, smtp = self._patch_smtp()
        with ctx:
            p.after_log(_entry(), True)
            p.after_log(_entry(), True)
        assert smtp.send_email_via_smtp.call_count == 1
