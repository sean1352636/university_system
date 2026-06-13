"""Tests for plugins.slack.SlackNotificationPlugin"""
from unittest.mock import patch, MagicMock

from education_system.university_system.modules.shared.utils.simple_activity_logger.plugins.slack import (
    SlackNotificationPlugin,
)


class TestSlackPlugin:
    def test_skipped_when_no_webhook(self, make_log_entry):
        p = SlackNotificationPlugin({})
        with patch.object(p, "_send_slack_notification") as m:
            p.after_log(make_log_entry(security_level="CRITICAL"), True)
            m.assert_not_called()

    def test_skipped_when_unsuccessful(self, make_log_entry):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://hooks/x"})
        with patch.object(p, "_send_slack_notification") as m:
            p.after_log(make_log_entry(security_level="CRITICAL"), False)
            m.assert_not_called()

    def test_sends_for_critical_security(self, make_log_entry):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://hooks/x"})
        with patch.object(p, "_send_slack_notification") as m:
            p.after_log(make_log_entry(security_level="CRITICAL"), True)
            m.assert_called_once()

    def test_sends_for_critical_log_level(self, make_log_entry):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://hooks/x"})
        with patch.object(p, "_send_slack_notification") as m:
            p.after_log(make_log_entry(security_level="LOW", log_level="CRITICAL"), True)
            m.assert_called_once()

    def test_skipped_for_normal_severity(self, make_log_entry):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://hooks/x"})
        with patch.object(p, "_send_slack_notification") as m:
            p.after_log(make_log_entry(), True)
            m.assert_not_called()

    def test_send_posts_to_webhook(self, make_log_entry):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://hooks/x"})
        with patch(
            "education_system.university_system.modules.shared.utils.simple_activity_logger.plugins.slack.requests"
        ) as req:
            req.post = MagicMock(return_value=MagicMock(raise_for_status=MagicMock()))
            p._send_slack_notification(make_log_entry(security_level="CRITICAL"))
            req.post.assert_called_once()
            args, kwargs = req.post.call_args
            assert args[0] == "https://hooks/x"
            assert "attachments" in kwargs["json"]

    def test_rate_limit_blocks_repeats(self, make_log_entry):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://hooks/x", "rate_limit_seconds": 300})
        with patch(
            "education_system.university_system.modules.shared.utils.simple_activity_logger.plugins.slack.requests"
        ) as req:
            req.post = MagicMock(return_value=MagicMock(raise_for_status=MagicMock()))
            entry = make_log_entry(security_level="CRITICAL")
            p._send_slack_notification(entry)
            p._send_slack_notification(entry)
            assert req.post.call_count == 1

    def test_handles_post_exception(self, make_log_entry):
        p = SlackNotificationPlugin({"slack_webhook_url": "https://hooks/x"})
        with patch(
            "education_system.university_system.modules.shared.utils.simple_activity_logger.plugins.slack.requests"
        ) as req:
            req.post = MagicMock(side_effect=RuntimeError("boom"))
            # Should not raise
            p._send_slack_notification(make_log_entry(security_level="CRITICAL"))
