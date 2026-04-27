from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class FallbackConfig:
    """Fallback config manager"""
    def __init__(self):
        self.config = {
            'api_enabled': False,
            'retention_days': 90,
            'auto_archive_days': 30,
            'max_log_size_mb': 100,
            'enable_real_time': False,
            'enable_alerts': True,
            'enable_analytics': True,
            'enable_encryption': False,
            'smtp_username': '',
            'smtp_password': '',
            'smtp_server': '',
            'smtp_port': 587,
            'webhook_secret': '',
            'alert_email': '',
            'api_secret_key': '',
            'weekly_report_email': '',
            'weekly_report_day': 1,
            'weekly_report_time': '09:00',
            'daily_report_time': '08:00',
            'security_alert_email': '',
            'failed_login_threshold': 5,
            'rapid_actions_threshold': 20,
            'alert_failed_logins': True,
            'alert_unusual_hours': True,
            'alert_rapid_actions': True,
            'alert_admin_actions': True,
            'weekly_include_summary': True,
            'weekly_include_charts': True,
            'weekly_include_alerts': True
        }
        # For compatibility with code that accesses .default_config
        self.default_config = self.config.copy()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def save_config(self):
        """Save fallback configuration - stores config in memory only"""
        logger.debug("FallbackConfig: save_config called (no-op, config stored in memory only)")

class FallbackAnalytics:
    """
    Fallback analytics manager

    Provides mock analytics functionality when the full analytics
    module is unavailable. Returns empty/default data to prevent
    application failures while maintaining API compatibility.
    """
    def __init__(self):
        """Initialize fallback analytics with empty state"""
        self.activities = []
        self.users = set()

    def generate_activity_summary(self, days=7):
        """Generate a mock activity summary"""
        return {
            'total_activities': 0,
            'unique_users': 0,
            'success_rate': 100.0,
            'failed_activities': 0,
            'peak_activity_hour': 9
        }

    def generate_user_activity_report(self, user_id, days=30):
        """Generate a mock user activity report"""
        return f"Mock activity report for user {user_id} over {days} days"

    def create_activity_chart(self, chart_type, days, save_path):
        """Create activity visualization chart from the activity_log table."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT action, timestamp FROM activity_log "
                "WHERE timestamp >= ? ORDER BY timestamp",
                (start_date.strftime("%Y-%m-%d"),),
            )
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.error("Error querying activity_log for chart: %s", e)
            return None

        if not rows:
            return None

        # Parse timestamps and collect actions
        dates = []
        hours = []
        actions = []
        for r in rows:
            try:
                ts = datetime.strptime(r["timestamp"][:19], "%Y-%m-%d %H:%M:%S")
                dates.append(ts.date())
                hours.append(ts.hour)
                actions.append(r["action"] or "unknown")
            except (ValueError, TypeError):
                continue

        if not dates:
            return None

        plt.style.use("seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default")
        fig, axes = plt.subplots(2, 2, figsize=(14, 9))
        fig.suptitle(f"Activity Analysis \u2014 Last {days} Days", fontsize=15)

        # 1) Daily activity trend
        from collections import Counter
        daily_counts = Counter(dates)
        sorted_days = sorted(daily_counts)
        axes[0, 0].plot(
            sorted_days, [daily_counts[d] for d in sorted_days], marker="o",
        )
        axes[0, 0].set_title("Daily Activity Trend")
        axes[0, 0].set_xlabel("Date")
        axes[0, 0].set_ylabel("Activities")
        axes[0, 0].tick_params(axis="x", rotation=45)

        # 2) Activity by action type (pie)
        action_counts = Counter(actions)
        top_actions = action_counts.most_common(8)
        labels = [a for a, _ in top_actions]
        sizes = [c for _, c in top_actions]
        axes[0, 1].pie(sizes, labels=labels, autopct="%1.1f%%", textprops={"fontsize": 8})
        axes[0, 1].set_title("Activity Distribution")

        # 3) Hourly pattern (bar)
        hour_counts = Counter(hours)
        all_hours = range(24)
        axes[1, 0].bar(all_hours, [hour_counts.get(h, 0) for h in all_hours])
        axes[1, 0].set_title("Activity by Hour")
        axes[1, 0].set_xlabel("Hour of Day")
        axes[1, 0].set_ylabel("Activities")

        # 4) Top actions (horizontal bar)
        top10 = action_counts.most_common(10)
        act_labels = [a for a, _ in top10]
        act_vals = [c for _, c in top10]
        axes[1, 1].barh(act_labels, act_vals)
        axes[1, 1].set_title("Top Actions")
        axes[1, 1].set_xlabel("Count")

        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches="tight")

        plt.close(fig)
        return save_path

class FallbackAlerts:
    """
    Fallback alerts manager

    Provides mock alert functionality when the full alerts module
    is unavailable. Returns empty alerts to maintain compatibility
    while preventing application crashes.
    """
    def __init__(self):
        """Initialize fallback alerts with empty state"""
        self.alerts = []
        self.alert_rules = []

    def run_alert_checks(self):
        """Run mock alert checks"""
        return []

class FallbackDatabase:
    """Fallback database manager"""
    def __init__(self, db_path):
        self.db_path = db_path

    def search_logs(self, filters=None, limit=100):
        """Search logs with filters"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM activity_log"
            params = []

            if filters:
                conditions = []
                if filters.get('user_id'):
                    conditions.append("user_id = ?")
                    params.append(filters['user_id'])
                if filters.get('action'):
                    conditions.append("action = ?")
                    params.append(filters['action'])
                if filters.get('date_from'):
                    conditions.append("timestamp >= ?")
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    conditions.append("timestamp <= ?")
                    params.append(filters['date_to'])
                if filters.get('status'):
                    conditions.append("status = ?")
                    params.append(filters['status'])

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            query += f" ORDER BY timestamp DESC LIMIT {limit}"

            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return results
        except Exception as e:
            print(f"Database search error: {e}")
            return []

    def insert_log(self, log_data):
        """Insert a log entry"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_log (timestamp, user_id, username, action, details, status, module, message, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_data.get('timestamp'),
                log_data.get('user_id'),
                log_data.get('username', ''),
                log_data.get('action'),
                log_data.get('details', ''),
                log_data.get('status', ''),
                log_data.get('module', ''),
                log_data.get('message', ''),
                log_data.get('ip_address', '127.0.0.1'),
                log_data.get('user_agent', '')
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database insert error: {e}")

# Fallback Log Manager implementation
class FallbackLogManager:
    """Fallback log manager when the main one is not available"""

    def __init__(self):
        self.db_path = str(DEFAULT_DB_PATH)
        self.available = True
        self.config = FallbackConfig()
        self.db = FallbackDatabase(self.db_path)
        self.analytics = FallbackAnalytics()
        self.alerts = FallbackAlerts()

    def get_logs(self, limit=100, offset=0, filters=None):
        """Get logs from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = "SELECT * FROM activity_log"
            params = []

            if filters:
                conditions = []
                if filters.get('user_id'):
                    conditions.append("user_id = ?")
                    params.append(filters['user_id'])
                if filters.get('action'):
                    conditions.append("action = ?")
                    params.append(filters['action'])
                if filters.get('date_from'):
                    conditions.append("timestamp >= ?")
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    conditions.append("timestamp <= ?")
                    params.append(filters['date_to'])

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            query += f" ORDER BY timestamp DESC LIMIT {limit} OFFSET {offset}"

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            return results
        except Exception as e:
            print(f"Error getting logs: {e}")
            return []

    def get_alerts(self, limit=50):
        """Get alerts from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM alerts
                ORDER BY triggered_at DESC
                LIMIT ?
            """, (limit,))
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"Error getting alerts: {e}")
            return []

    def add_log(self, user_id, action, status, module, message, **kwargs):
        """Add a log entry"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_log (user_id, username, action, status, module, message, ip_address, user_agent, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                kwargs.get('username', user_id),
                action,
                status,
                module,
                message,
                kwargs.get('ip_address', '127.0.0.1'),
                kwargs.get('user_agent', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                kwargs.get('details', '')
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding log: {e}")
            return False
