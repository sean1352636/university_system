"""
Alerting System

Sends alerts for critical failures, anomalies, and system issues.
Supports email, log, and webhook notifications.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertManager:
    """
    Manages system alerts and notifications.

    Features:
    - Alert rate limiting (prevent spam)
    - Multiple notification channels
    - Alert history tracking
    - Anomaly detection
    """

    def __init__(self):
        # Alert history
        self._alert_history: List[Dict] = []

        # Alert rate limiting (max alerts per hour)
        self._alert_counts: Dict[str, List[datetime]] = defaultdict(list)
        self._max_alerts_per_hour = 10

        # Thresholds for anomaly detection
        self._thresholds = {
            'failed_logins_per_minute': 10,
            'database_errors_per_minute': 5,
            'email_queue_size': 100,
            'disk_usage_percent': 90,
            'unusual_grade_changes_per_hour': 50,
        }

    def send_alert(
        self,
        alert_type: str,
        level: AlertLevel,
        message: str,
        details: Optional[Dict] = None
    ) -> bool:
        """
        Send an alert.

        Args:
            alert_type: Type of alert (e.g., 'database_error', 'disk_full')
            level: Alert severity level
            message: Alert message
            details: Additional details

        Returns:
            True if alert was sent, False if rate limited
        """
        # Check rate limiting
        if self._is_rate_limited(alert_type):
            logger.warning(f"Alert rate limited: {alert_type}")
            return False

        # Create alert
        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'level': level.value,
            'message': message,
            'details': details or {}
        }

        # Add to history
        self._alert_history.append(alert)

        # Keep only last 1000 alerts
        if len(self._alert_history) > 1000:
            self._alert_history = self._alert_history[-1000:]

        # Send alert via configured channels
        self._send_via_channels(alert)

        # Update rate limit tracking
        self._alert_counts[alert_type].append(datetime.now())

        return True

    def _is_rate_limited(self, alert_type: str) -> bool:
        """Check if alert type is rate limited"""
        # Clean old alerts (older than 1 hour)
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)

        self._alert_counts[alert_type] = [
            ts for ts in self._alert_counts[alert_type]
            if ts > one_hour_ago
        ]

        # Check if limit exceeded
        return len(self._alert_counts[alert_type]) >= self._max_alerts_per_hour

    def _send_via_channels(self, alert: Dict):
        """Send alert via configured notification channels"""
        level = AlertLevel(alert['level'])

        # Always log
        if level == AlertLevel.CRITICAL:
            logger.critical(f"ALERT: {alert['message']}", extra=alert)
        elif level == AlertLevel.ERROR:
            logger.error(f"ALERT: {alert['message']}", extra=alert)
        elif level == AlertLevel.WARNING:
            logger.warning(f"ALERT: {alert['message']}", extra=alert)
        else:
            logger.info(f"ALERT: {alert['message']}", extra=alert)

        # Send email for critical and error alerts
        if level in [AlertLevel.CRITICAL, AlertLevel.ERROR]:
            self._send_email_alert(alert)

    def _send_email_alert(self, alert: Dict):
        """Send alert via email"""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service import EmailService

            email_service = EmailService()

            subject = f"[{alert['level'].upper()}] {alert['type']}"
            body = f"""
System Alert

Type: {alert['type']}
Level: {alert['level']}
Time: {alert['timestamp']}

Message:
{alert['message']}

Details:
{alert['details']}

---
University Management System
Automated Alert
"""

            # Try to send email (don't fail if email not configured)
            email_service.send_email(
                to_email='admin@university.edu',  # Should be configurable
                subject=subject,
                body=body
            )

        except Exception as e:
            logger.debug(f"Could not send email alert: {e}")

    def check_anomalies(self, metrics: Dict[str, Any]) -> List[Dict]:
        """
        Check metrics for anomalies and send alerts.

        Args:
            metrics: Metrics dictionary from MetricsCollector

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Check failed logins
        failed_logins = metrics.get('counters', {}).get('login.failures', 0)
        if failed_logins > self._thresholds['failed_logins_per_minute']:
            anomaly = {
                'type': 'excessive_failed_logins',
                'value': failed_logins,
                'threshold': self._thresholds['failed_logins_per_minute']
            }
            anomalies.append(anomaly)

            self.send_alert(
                'excessive_failed_logins',
                AlertLevel.WARNING,
                f'Unusual number of failed logins: {failed_logins} in last minute',
                anomaly
            )

        # Check database errors
        db_errors = metrics.get('error_rates', {}).get('database_operation', 0)
        if db_errors > self._thresholds['database_errors_per_minute']:
            anomaly = {
                'type': 'database_errors',
                'value': db_errors,
                'threshold': self._thresholds['database_errors_per_minute']
            }
            anomalies.append(anomaly)

            self.send_alert(
                'database_errors',
                AlertLevel.ERROR,
                f'High database error rate: {db_errors} errors per minute',
                anomaly
            )

        return anomalies

    def get_alert_history(self, hours: int = 24) -> List[Dict]:
        """Get alert history for the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)

        return [
            alert for alert in self._alert_history
            if datetime.fromisoformat(alert['timestamp']) > cutoff
        ]

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of recent alerts"""
        recent = self.get_alert_history(hours=24)

        summary = {
            'total_alerts': len(recent),
            'by_level': defaultdict(int),
            'by_type': defaultdict(int),
            'recent_critical': []
        }

        for alert in recent:
            summary['by_level'][alert['level']] += 1
            summary['by_type'][alert['type']] += 1

            if alert['level'] == AlertLevel.CRITICAL.value:
                summary['recent_critical'].append(alert)

        # Keep only last 10 critical alerts
        summary['recent_critical'] = summary['recent_critical'][-10:]

        return dict(summary)


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance"""
    global _alert_manager

    if _alert_manager is None:
        _alert_manager = AlertManager()

    return _alert_manager


def send_alert(alert_type: str, level: AlertLevel, message: str, details: Optional[Dict] = None):
    """Quick function to send an alert"""
    manager = get_alert_manager()
    return manager.send_alert(alert_type, level, message, details)
