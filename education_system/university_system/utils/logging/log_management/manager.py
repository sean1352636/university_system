"""Main enhanced log management class."""

import time
import threading

try:
    import schedule  # type: ignore
    SCHEDULE_AVAILABLE = True
except Exception:
    SCHEDULE_AVAILABLE = False

    class _ScheduleJobStub:
        def __getattr__(self, name):  # pragma: no cover
            return self
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return self

    class _ScheduleStub:
        def __getattr__(self, name):  # pragma: no cover
            return _ScheduleJobStub()
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return _ScheduleJobStub()
    schedule = _ScheduleStub()

from education_system.university_system.utils.logging.log_management.config import LogConfig
from education_system.university_system.utils.logging.log_management.database import LogDatabase
from education_system.university_system.utils.logging.log_management.analytics import LogAnalytics
from education_system.university_system.utils.logging.log_management.alerts import LogAlerts
from education_system.university_system.utils.logging.log_management.monitoring import RealTimeMonitor
from education_system.university_system.utils.logging.log_management.retention import LogRetention


class EnhancedLogManager:
    """Main enhanced log management class"""

    def __init__(self):
        self.config = LogConfig()
        self.db = LogDatabase()
        self.analytics = LogAnalytics(self.db)
        self.alerts = LogAlerts(self.db, self.config)
        self.monitor = RealTimeMonitor(self.db)
        self.retention = LogRetention(self.config, self.db)

        # Set up scheduled tasks
        self.setup_scheduled_tasks()

        # Start real-time monitoring if enabled
        if self.config.get('enable_real_time'):
            self.monitor.start_monitoring()

    def setup_scheduled_tasks(self):
        """Set up automated tasks"""
        # Daily cleanup and archival
        schedule.every().day.at("02:00").do(self.retention.archive_old_logs)
        schedule.every().day.at("03:00").do(self.retention.cleanup_old_logs)

        # Hourly alert checks
        schedule.every().hour.do(self.alerts.run_alert_checks)

        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self._run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()

    def _run_scheduler(self):
        """Run scheduled tasks"""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


# Create global log manager instance (but only when needed)
log_manager = None


def get_log_manager():
    """Get the global log manager instance, creating it if necessary"""
    global log_manager
    if log_manager is None:
        log_manager = EnhancedLogManager()
    return log_manager
