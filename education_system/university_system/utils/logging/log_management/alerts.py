"""Alert system for suspicious activities."""

from datetime import datetime, timedelta
from collections import defaultdict

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.utils.logging.log_management.database import LogDatabase
from education_system.university_system.utils.logging.log_management.config import LogConfig


class LogAlerts:
    """Alert system for suspicious activities"""

    def __init__(self, db: LogDatabase, config: LogConfig):
        self.db = db
        self.config = config
        self.alert_rules = [
            {"name": "Multiple Failed Logins", "check": self.check_failed_logins},
            {"name": "Unusual Activity Hours", "check": self.check_unusual_hours},
            {"name": "Rapid Fire Actions", "check": self.check_rapid_actions},
            {"name": "Admin Actions", "check": self.check_admin_actions}
        ]

    def check_failed_logins(self, recent_logs):
        """Check for multiple failed login attempts"""
        failed_logins = defaultdict(int)
        cutoff_time = datetime.now() - timedelta(minutes=15)

        for log in recent_logs:
            if (log['action'] == 'login' and
                log['status'] == 'failure' and
                datetime.fromisoformat(log['timestamp']) > cutoff_time):
                failed_logins[log['user_id']] += 1

        alerts = []
        for user_id, count in failed_logins.items():
            if count >= 5:
                alerts.append({
                    "type": "security",
                    "severity": "high",
                    "message": f"User {user_id} has {count} failed login attempts in the last 15 minutes"
                })

        return alerts

    def check_unusual_hours(self, recent_logs):
        """Check for activities during unusual hours (e.g., 2-6 AM)"""
        alerts = []
        unusual_hours = range(2, 6)

        for log in recent_logs:
            log_time = datetime.fromisoformat(log['timestamp'])
            if log_time.hour in unusual_hours:
                alerts.append({
                    "type": "anomaly",
                    "severity": "medium",
                    "message": f"Activity by {log['username']} at unusual hour: {log_time.strftime('%H:%M')}"
                })

        return alerts

    def check_rapid_actions(self, recent_logs):
        """Check for rapid-fire actions from the same user"""
        user_actions = defaultdict(list)
        cutoff_time = datetime.now() - timedelta(minutes=5)

        for log in recent_logs:
            if datetime.fromisoformat(log['timestamp']) > cutoff_time:
                user_actions[log['user_id']].append(log['timestamp'])

        alerts = []
        for user_id, timestamps in user_actions.items():
            if len(timestamps) > 20:  # More than 20 actions in 5 minutes
                alerts.append({
                    "type": "anomaly",
                    "severity": "medium",
                    "message": f"User {user_id} performed {len(timestamps)} actions in the last 5 minutes"
                })

        return alerts

    def check_admin_actions(self, recent_logs):
        """Alert on sensitive admin actions"""
        alerts = []
        sensitive_actions = ['delete', 'system_config', 'user_management']

        for log in recent_logs:
            if log['action'] in sensitive_actions or log['module'] in sensitive_actions:
                alerts.append({
                    "type": "audit",
                    "severity": "low",
                    "message": f"Admin action: {log['username']} performed {log['action']} on {log['module']}"
                })

        return alerts

    def run_alert_checks(self):
        """Run all alert checks on recent logs"""
        # Get logs from the last hour
        cutoff_time = datetime.now() - timedelta(hours=1)
        filters = {
            'date_from': cutoff_time.strftime('%Y-%m-%d'),
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }

        recent_logs = self.db.search_logs(filters, limit=1000)

        all_alerts = []
        for rule in self.alert_rules:
            try:
                alerts = rule["check"](recent_logs)
                all_alerts.extend(alerts)
            except Exception as e:
                print(f"Error in alert rule {rule['name']}: {e}")

        # Store alerts in database
        for alert in all_alerts:
            self.store_alert(alert)

        return all_alerts

    def store_alert(self, alert):
        """Store alert in database"""
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO alerts (alert_type, message, severity)
                VALUES (?, ?, ?)
            ''', (alert['type'], alert['message'], alert['severity']))

            conn.commit()
        finally:
            conn.close()
