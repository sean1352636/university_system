"""Backup and recovery system for attendance data."""

import datetime
import json
import threading
import time
from pathlib import Path
import schedule
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.attendance.settings import get_setting


class BackupRecoverySystem:
    def __init__(self):
        # Use centralized attendance backup directory
        from education_system.systems.university.infrastructure.paths import BACKUP_ATTENDANCE_DIR
        self.backup_dir = BACKUP_ATTENDANCE_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Get the correct database path
        try:
            from education_system.systems.university.interfaces.cli.shell.cli_main import DB_PATH
            self.db_path = DB_PATH
        except ImportError:
            # Fallback to centralized path
            from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
            self.db_path = str(DEFAULT_DB_PATH)

    def create_backup(self, backup_type="full"):
        """Create database backup"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"attendance_backup_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_filename

            # Copy database file
            import shutil
            shutil.copy2(self.db_path, backup_path)

            # Create metadata file
            metadata = {
                "backup_type": backup_type,
                "timestamp": timestamp,
                "file_size": backup_path.stat().st_size,
                "created_by": "System"
            }

            metadata_path = self.backup_dir / f"metadata_{timestamp}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            print(f"Backup created successfully: {backup_filename}")
            return str(backup_path)

        except Exception as e:
            print(f"Error creating backup: {e}")
            return None

    def restore_backup(self, backup_path):
        """Restore from backup"""
        try:
            if not Path(backup_path).exists():
                return False, "Backup file not found"

            # Create current backup before restore
            current_backup = self.create_backup("pre_restore")

            # Restore backup
            import shutil
            shutil.copy2(backup_path, self.db_path)

            return True, f"Backup restored successfully. Previous backup saved as: {current_backup}"

        except Exception as e:
            return False, f"Error restoring backup: {e}"

    def schedule_automatic_backups(self):
        """Schedule automatic backups"""
        if get_setting('auto_backup_enabled') == 'True':
            frequency_hours = int(get_setting('backup_frequency_hours') or 24)

            def backup_job():
                self.create_backup("scheduled")
                self.cleanup_old_backups()

            schedule.every(frequency_hours).hours.do(backup_job)

            # Run scheduler in background thread
            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(60)

            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()

            print(f"Automatic backups scheduled every {frequency_hours} hours")

    def cleanup_old_backups(self, keep_days=30):
        """Clean up old backup files"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.datetime.now() - timedelta(days=keep_days)

            for backup_file in self.backup_dir.glob("*.db"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    backup_file.unlink()

                    # Also remove corresponding metadata
                    metadata_file = backup_file.with_suffix('.json')
                    if metadata_file.exists():
                        metadata_file.unlink()

            print(f"Cleaned up backups older than {keep_days} days")

        except Exception as e:
            print(f"Error cleaning up backups: {e}")
