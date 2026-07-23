import time
from typing import Dict, Any

import requests

from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger.models import LogEntry, SecurityLevel, LogLevel
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger.plugins.base import LoggerPlugin


class SlackNotificationPlugin(LoggerPlugin):
    """Plugin to send critical alerts to Slack"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('slack_webhook_url')
        self.last_notification = {}  # Rate limiting
        self.rate_limit_seconds = config.get('rate_limit_seconds', 300)  # 5 minutes

    def after_log(self, log_entry: LogEntry, success: bool):
        if not success or not self.webhook_url:
            return

        if (log_entry.security_level == SecurityLevel.CRITICAL.name or
            log_entry.log_level == LogLevel.CRITICAL.name):
            self._send_slack_notification(log_entry)

    def _send_slack_notification(self, log_entry: LogEntry):
        """Send notification to Slack with rate limiting"""
        # Rate limiting by user and action
        key = f"{log_entry.username}:{log_entry.action}"
        now = time.time()

        if key in self.last_notification:
            if now - self.last_notification[key] < self.rate_limit_seconds:
                return  # Skip due to rate limiting

        self.last_notification[key] = now

        try:
            color = "danger" if log_entry.security_level == "CRITICAL" else "warning"

            message = {
                "text": "🚨 Critical Activity Alert",
                "attachments": [{
                    "color": color,
                    "fields": [
                        {"title": "User", "value": log_entry.username, "short": True},
                        {"title": "Action", "value": log_entry.action, "short": True},
                        {"title": "Module", "value": log_entry.module, "short": True},
                        {"title": "Status", "value": log_entry.status, "short": True},
                        {"title": "Timestamp", "value": log_entry.timestamp, "short": True},
                        {"title": "IP Address", "value": log_entry.ip_address, "short": True},
                        {"title": "Details", "value": log_entry.details[:500], "short": False}
                    ],
                    "footer": f"Trace ID: {log_entry.trace_id}"
                }]
            }

            response = requests.post(self.webhook_url, json=message, timeout=10)
            response.raise_for_status()

        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
