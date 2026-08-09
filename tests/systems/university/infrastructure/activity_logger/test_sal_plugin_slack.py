"""Tests for simple_activity_logger.plugins.slack."""
from unittest.mock import patch

from education_system.systems.university.infrastructure.utils.activity_logger.plugins import slack
from education_system.systems.university.infrastructure.utils.activity_logger.plugins.slack import (
    SlackNotificationPlugin,
)
from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry


def _entry(**o):
    base = dict(
        timestamp="t", user_id="u", username="alice", role="user",
        action="login", module="auth", details="d", status="success",
        log_level="INFO", session_id="s", ip_address="1.1.1.1",
        user_agent="UA", request_size=0, response_size=0,
        processing_time=0.0, geolocation={}, security_level="LOW",
        trace_id="t",
    )
    base.update(o)
    return LogEntry(**base)


class TestSlackNotification:
    def test_no_webhook_skips_send(self):
        p = SlackNotificationPlugin({})
        with patch.object(slack, "requests") as req:
            p.after_log(_entry(security_level="CRITICAL"), True)
        req.post.assert_not_called()

    def test_failure_log_skipped(self):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://example.com/h"})
        with patch.object(slack, "requests") as req:
            p.after_log(_entry(security_level="CRITICAL"), success=False)
        req.post.assert_not_called()

    def test_low_severity_not_sent(self):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://example.com/h"})
        with patch.object(slack, "requests") as req:
            p.after_log(_entry(security_level="LOW"), True)
        req.post.assert_not_called()

    def test_critical_sends_webhook(self):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://example.com/h"})
        with patch.object(slack, "requests") as req:
            p.after_log(_entry(security_level="CRITICAL"), True)
        req.post.assert_called_once()
        kwargs = req.post.call_args.kwargs
        assert kwargs["json"]["attachments"][0]["color"] == "danger"

    def test_rate_limiting_blocks_repeats(self):
        p = SlackNotificationPlugin({
            "slack_webhook_url": "https://example.com/h",
            "rate_limit_seconds": 600,
        })
        with patch.object(slack, "requests") as req:
            p.after_log(_entry(security_level="CRITICAL"), True)
            p.after_log(_entry(security_level="CRITICAL"), True)
        assert req.post.call_count == 1

    def test_swallows_request_errors(self):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://example.com/h"})
        with patch.object(slack, "requests") as req:
            req.post.side_effect = RuntimeError("net down")
            # must not raise
            p.after_log(_entry(security_level="CRITICAL"), True)
