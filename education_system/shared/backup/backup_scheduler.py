"""Background scheduler for automated database backups."""

import threading
import logging
import time
from education_system.shared.backup.backup_manager import backup, cleanup_old_backups

logger = logging.getLogger(__name__)

_INTERVALS = {"hourly": 3600, "daily": 86400, "weekly": 604800}


class BackupScheduler:
    """Thread-based backup scheduler."""

    def __init__(self):
        self._jobs = []
        self._thread = None
        self._running = False

    def schedule_backup(self, db_path, backup_dir, interval="daily",
                        compress=True, retention_days=30):
        """Schedule a recurring backup."""
        secs = _INTERVALS.get(interval, 86400)
        self._jobs.append({
            "db_path": db_path,
            "backup_dir": backup_dir,
            "interval_secs": secs,
            "compress": compress,
            "retention_days": retention_days,
            "last_run": 0,
        })
        logger.info("Scheduled %s backup for %s", interval, db_path)

    def start(self):
        """Start the scheduler in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Backup scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while self._running:
            now = time.time()
            for job in self._jobs:
                if now - job["last_run"] >= job["interval_secs"]:
                    try:
                        backup(job["db_path"], job["backup_dir"],
                               compress=job["compress"])
                        cleanup_old_backups(job["backup_dir"],
                                            job["retention_days"])
                        job["last_run"] = now
                    except Exception as e:
                        logger.error("Backup failed for %s: %s",
                                     job["db_path"], e)
            time.sleep(60)

    def run_now(self):
        """Run all scheduled backups immediately."""
        for job in self._jobs:
            try:
                path = backup(job["db_path"], job["backup_dir"],
                              compress=job["compress"])
                job["last_run"] = time.time()
                logger.info("Manual backup completed: %s", path)
            except Exception as e:
                logger.error("Backup failed for %s: %s", job["db_path"], e)
