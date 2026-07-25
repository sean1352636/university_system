"""Log retention and archival management."""

import os
import json
import zipfile
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.paths import LOG_DIR

from education_system.systems.university.infrastructure.logging.log_management.config import LogConfig
from education_system.systems.university.infrastructure.logging.log_management.database import LogDatabase


class LogRetention:
    """Log retention and archival management"""

    def __init__(self, config: LogConfig, db: LogDatabase):
        self.config = config
        self.db = db

    def archive_old_logs(self):
        """Archive logs older than configured days"""
        cutoff_date = datetime.now() - timedelta(days=self.config.get('auto_archive_days', 30))

        # Get old logs
        filters = {
            'date_to': cutoff_date.strftime('%Y-%m-%d')
        }

        old_logs = self.db.search_logs(filters, limit=50000)

        if not old_logs:
            print("No logs to archive")
            return

        # Create archive
        archive_path = LOG_DIR / "archives"
        archive_path.mkdir(parents=True, exist_ok=True)
        archive_path = str(archive_path)

        archive_file = os.path.join(archive_path, f"logs_archive_{cutoff_date.strftime('%Y%m%d')}.zip")

        with zipfile.ZipFile(archive_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Export to JSON and add to zip
            json_data = json.dumps(old_logs, indent=2)
            zipf.writestr(f"archived_logs_{cutoff_date.strftime('%Y%m%d')}.json", json_data)

        print(f"Archived {len(old_logs)} logs to {archive_file}")

        # Remove old logs from database (in production, be very careful with this)
        # This is commented out for safety
        # self._delete_old_logs(cutoff_date)

    def cleanup_old_logs(self):
        """Delete logs older than retention period"""
        retention_days = self.config.get('retention_days', 90)
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        # Clean database entries
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            cursor = conn.cursor()

            cursor.execute('DELETE FROM logs WHERE timestamp < ?', (cutoff_date.isoformat(),))
            deleted_db_count = cursor.rowcount

            conn.commit()
        finally:
            conn.close()

        # Clean old log files
        deleted_files_count = 0
        cutoff_timestamp = cutoff_date.timestamp()

        import os
        for filename in os.listdir(LOG_DIR):
            filepath = LOG_DIR / filename
            if filepath.is_file():
                # Check if it's an old log file
                if any(filename.startswith(prefix) for prefix in ['activity.', 'activity_log_', 'enhanced_log_']):
                    try:
                        file_mtime = os.path.getmtime(filepath)
                        if file_mtime < cutoff_timestamp:
                            os.remove(filepath)
                            deleted_files_count += 1
                    except Exception as e:
                        print(f"Warning: Could not delete {filename}: {e}")

        print(f"Deleted {deleted_db_count} database logs and {deleted_files_count} log files older than {retention_days} days")
