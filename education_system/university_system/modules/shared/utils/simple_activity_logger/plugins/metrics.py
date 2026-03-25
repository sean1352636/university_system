import time
import logging
from datetime import datetime
from typing import Dict, Any

from education_system.university_system.modules.shared.utils.simple_activity_logger.models import LogEntry, SecurityLevel
from education_system.university_system.modules.shared.utils.simple_activity_logger.plugins.base import LoggerPlugin

_logger = logging.getLogger(__name__)


class MetricsCollectionPlugin(LoggerPlugin):
    """Plugin to collect metrics for monitoring systems"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.metrics = {
            'total_logs': 0,
            'error_count': 0,
            'security_alerts': 0,
            'action_counts': {},
            'user_activity': {},
            'module_usage': {},
            'hourly_activity': {},
            'last_reset': time.time()
        }
        self.reset_interval = config.get('reset_interval_hours', 24) * 3600

    def after_log(self, log_entry: LogEntry, success: bool):
        if not success:
            return

        # Check if we need to reset metrics
        if time.time() - self.metrics['last_reset'] > self.reset_interval:
            self._reset_metrics()

        self.metrics['total_logs'] += 1

        if log_entry.status == 'failure':
            self.metrics['error_count'] += 1

        if log_entry.security_level in [SecurityLevel.HIGH.name, SecurityLevel.CRITICAL.name]:
            self.metrics['security_alerts'] += 1

        # Count actions
        action = log_entry.action
        self.metrics['action_counts'][action] = self.metrics['action_counts'].get(action, 0) + 1

        # Count user activity
        user = log_entry.username
        self.metrics['user_activity'][user] = self.metrics['user_activity'].get(user, 0) + 1

        # Count module usage
        module = log_entry.module
        self.metrics['module_usage'][module] = self.metrics['module_usage'].get(module, 0) + 1

        # Count hourly activity
        try:
            hour = datetime.strptime(log_entry.timestamp, "%Y-%m-%d %H:%M:%S.%f").hour
            self.metrics['hourly_activity'][hour] = self.metrics['hourly_activity'].get(hour, 0) + 1
        except (ValueError, AttributeError) as e:
            _logger.debug(f"Failed to parse log entry timestamp for metrics: {e}")

    def _reset_metrics(self):
        """Reset metrics (keeping structure)"""
        self.metrics = {
            'total_logs': 0,
            'error_count': 0,
            'security_alerts': 0,
            'action_counts': {},
            'user_activity': {},
            'module_usage': {},
            'hourly_activity': {},
            'last_reset': time.time()
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        metrics_copy = self.metrics.copy()

        # Add calculated metrics
        if metrics_copy['total_logs'] > 0:
            metrics_copy['error_rate'] = (metrics_copy['error_count'] / metrics_copy['total_logs']) * 100
            metrics_copy['security_alert_rate'] = (metrics_copy['security_alerts'] / metrics_copy['total_logs']) * 100
        else:
            metrics_copy['error_rate'] = 0
            metrics_copy['security_alert_rate'] = 0

        # Add top items
        metrics_copy['top_actions'] = dict(sorted(metrics_copy['action_counts'].items(), key=lambda x: x[1], reverse=True)[:10])
        metrics_copy['top_users'] = dict(sorted(metrics_copy['user_activity'].items(), key=lambda x: x[1], reverse=True)[:10])
        metrics_copy['top_modules'] = dict(sorted(metrics_copy['module_usage'].items(), key=lambda x: x[1], reverse=True)[:10])

        return metrics_copy

    def get_status(self) -> Dict[str, Any]:
        """Get plugin status with current metrics"""
        status = super().get_status()
        status['current_metrics'] = self.get_metrics()
        return status
