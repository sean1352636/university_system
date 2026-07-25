"""
Automated Backup Scheduling

Schedules regular backups, manages retention, and verifies backup integrity.
"""

import os
import logging
import shutil
import schedule
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class BackupScheduler:
    """
    Manages automated database backups.

    Features:
    - Scheduled backups (daily, weekly, monthly)
    - Backup retention policies
    - Backup verification
    - Space management
    """

    def __init__(self, backup_dir: Optional[str] = None):
        from education_system.systems.university.infrastructure import paths

        self.backup_dir = Path(backup_dir) if backup_dir else Path(paths.DATA_DIR) / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Retention settings (days to keep backups)
        self.retention = {
            'daily': 7,      # Keep daily backups for 7 days
            'weekly': 30,    # Keep weekly backups for 30 days
            'monthly': 365,  # Keep monthly backups for 1 year
        }

        # Scheduler thread
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_scheduler = threading.Event()
        self._running = False

    def create_backup(self, backup_type: str = 'manual') -> Dict[str, Any]:
        """
        Create a database backup.

        Args:
            backup_type: Type of backup ('manual', 'daily', 'weekly', 'monthly')

        Returns:
            Dictionary with backup info
        """
        try:
            from education_system.systems.university.infrastructure import paths

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f'backup_{backup_type}_{timestamp}.db'
            backup_path = self.backup_dir / backup_name

            # Copy database file
            shutil.copy2(paths.DEFAULT_DB_PATH, backup_path)

            # Verify backup
            is_valid = self._verify_backup(backup_path)

            # Calculate backup size
            size_mb = backup_path.stat().st_size / (1024 * 1024)

            logger.info(f"Created {backup_type} backup: {backup_name} ({size_mb:.2f} MB)")

            return {
                'success': True,
                'backup_path': str(backup_path),
                'backup_name': backup_name,
                'backup_type': backup_type,
                'timestamp': timestamp,
                'size_mb': round(size_mb, 2),
                'verified': is_valid
            }

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity"""
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master")
            result = cursor.fetchone()
            conn.close()

            return result is not None

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False

    def schedule_daily_backup(self, time_str: str = "02:00"):
        """Schedule daily backup at specified time"""
        schedule.every().day.at(time_str).do(
            lambda: self.create_backup('daily')
        )
        logger.info(f"Scheduled daily backups at {time_str}")

    def schedule_weekly_backup(self, day: str = "sunday", time_str: str = "03:00"):
        """Schedule weekly backup"""
        getattr(schedule.every(), day.lower()).at(time_str).do(
            lambda: self.create_backup('weekly')
        )
        logger.info(f"Scheduled weekly backups on {day} at {time_str}")

    def schedule_monthly_backup(self, day: int = 1, time_str: str = "04:00"):
        """Schedule monthly backup (first day of month)"""
        schedule.every().day.at(time_str).do(
            lambda: self._create_monthly_backup_if_first_day()
        )
        logger.info(f"Scheduled monthly backups on day {day} at {time_str}")

    def _create_monthly_backup_if_first_day(self):
        """Create monthly backup only on first day of month"""
        if datetime.now().day == 1:
            self.create_backup('monthly')

    def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        now = datetime.now()
        removed_count = 0

        for backup_file in self.backup_dir.glob('backup_*.db'):
            try:
                # Extract backup type and timestamp from filename
                parts = backup_file.stem.split('_')
                if len(parts) < 3:
                    continue

                backup_type = parts[1]
                file_time = datetime.strptime(parts[2] + '_' + parts[3], '%Y%m%d_%H%M%S')

                # Check retention
                retention_days = self.retention.get(backup_type, 30)
                if (now - file_time).days > retention_days:
                    backup_file.unlink()
                    removed_count += 1
                    logger.info(f"Removed old backup: {backup_file.name}")

            except Exception as e:
                logger.warning(f"Could not process backup file {backup_file}: {e}")

        return removed_count

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        backups = []

        for backup_file in sorted(self.backup_dir.glob('backup_*.db'), reverse=True):
            try:
                parts = backup_file.stem.split('_')
                backup_type = parts[1] if len(parts) > 1 else 'unknown'
                timestamp = parts[2] + '_' + parts[3] if len(parts) > 3 else 'unknown'

                size_mb = backup_file.stat().st_size / (1024 * 1024)

                backups.append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'type': backup_type,
                    'timestamp': timestamp,
                    'size_mb': round(size_mb, 2),
                    'age_days': (datetime.now() - datetime.fromtimestamp(backup_file.stat().st_mtime)).days
                })

            except Exception as e:
                logger.warning(f"Could not read backup info for {backup_file}: {e}")

        return backups

    def get_backup_stats(self) -> Dict[str, Any]:
        """Get backup statistics"""
        backups = self.list_backups()

        total_size = sum(b['size_mb'] for b in backups)
        by_type = {}

        for backup in backups:
            backup_type = backup['type']
            if backup_type not in by_type:
                by_type[backup_type] = {'count': 0, 'size_mb': 0}
            by_type[backup_type]['count'] += 1
            by_type[backup_type]['size_mb'] += backup['size_mb']

        return {
            'total_backups': len(backups),
            'total_size_mb': round(total_size, 2),
            'by_type': by_type,
            'oldest_backup': backups[-1] if backups else None,
            'newest_backup': backups[0] if backups else None,
        }

    def start_scheduler(self):
        """Start the backup scheduler in background thread"""
        if self._running:
            logger.warning("Backup scheduler already running")
            return

        self._running = True
        self._stop_scheduler.clear()

        # Setup default schedule
        self.schedule_daily_backup()
        self.schedule_weekly_backup()

        # Add cleanup job (daily at 05:00)
        schedule.every().day.at("05:00").do(self.cleanup_old_backups)

        # Start scheduler thread
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()

        logger.info("Backup scheduler started")

    def _run_scheduler(self):
        """Run the scheduler loop"""
        while not self._stop_scheduler.is_set():
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def stop_scheduler(self):
        """Stop the backup scheduler"""
        if not self._running:
            return

        self._stop_scheduler.set()
        self._running = False

        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)

        logger.info("Backup scheduler stopped")

# Global backup scheduler instance
_backup_scheduler: Optional[BackupScheduler] = None

def get_backup_scheduler() -> BackupScheduler:
    """Get the global backup scheduler instance"""
    global _backup_scheduler

    if _backup_scheduler is None:
        _backup_scheduler = BackupScheduler()

    return _backup_scheduler

def schedule_backups():
    """Quick function to start backup scheduling"""
    scheduler = get_backup_scheduler()
    scheduler.start_scheduler()
    return scheduler
