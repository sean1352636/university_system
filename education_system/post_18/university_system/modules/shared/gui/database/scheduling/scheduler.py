"""Backup scheduler thread management."""
import datetime
import threading
import time

from education_system.post_18.university_system.modules.shared.gui.database.shared_imports import (
    DEFAULT_DB_PATH, logger, get_db_connection,
)
from education_system.post_18.university_system.modules.shared.gui.database.config import config
import education_system.post_18.university_system.modules.shared.gui.database.config as cfg
from education_system.post_18.university_system.modules.shared.gui.database.scheduling.cron import (
    _compute_cron_occurrences, _set_next_cron_run,
)


def start_scheduler():
    """Start the enhanced backup scheduler"""
    if cfg.scheduler_running:
        return

    def scheduler_worker():
        cfg.scheduler_running = True

        while cfg.scheduler_running:
            try:
                current_time = datetime.datetime.now()
                cron_expr = config.get("cron_schedule", "").strip()

                if cron_expr:
                    with cfg._cron_schedule_lock:
                        cron_next = cfg._next_cron_run

                    try:
                        if cron_next is None or cron_next < current_time:
                            cron_next = _compute_cron_occurrences(cron_expr, current_time, occurrences=1)[0]
                            _set_next_cron_run(cron_next)

                        if cron_next and current_time >= cron_next:
                            if config.get("auto_backup_enabled", True):
                                logger.info("Running cron scheduled backup at %s", current_time)
                                scheduled_backup_job()
                            next_occurrence = _compute_cron_occurrences(cron_expr, cron_next, occurrences=1)[0]
                            _set_next_cron_run(next_occurrence)
                        time.sleep(30)
                        continue
                    except Exception as cron_error:
                        logger.error(f"Cron scheduling error: {cron_error}")
                        _set_next_cron_run(None)
                        # Fall back to frequency-based scheduling until cron expression is corrected

                scheduled_time = datetime.datetime.strptime(config["scheduled_backup_time"], "%H:%M").time()

                if (current_time.time().hour == scheduled_time.hour and
                    current_time.time().minute == scheduled_time.minute):

                    frequency = config["backup_frequency"]
                    should_run = False

                    if frequency == "daily":
                        should_run = True
                    elif frequency == "weekly" and current_time.weekday() == 0:  # Monday
                        should_run = True
                    elif frequency == "monthly" and current_time.day == 1:
                        should_run = True

                    if should_run and config.get("auto_backup_enabled", True):
                        scheduled_backup_job()
                        time.sleep(60)  # Prevent multiple runs in same minute

                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)

    cfg.scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
    cfg.scheduler_thread.start()
    logger.info("Backup scheduler started")

def stop_scheduler():
    """Stop the backup scheduler thread"""
    cfg.scheduler_running = False
    _set_next_cron_run(None)
    logger.info("Backup scheduler stopped")

def scheduled_backup_job():
    """Enhanced scheduled backup function"""
    try:
        # Late import to avoid circular dependency
        from education_system.post_18.university_system.modules.shared.gui.database.operations.backup_ops import (
            create_enhanced_backup, cleanup_old_backups, notify_backup_result,
        )
        logger.info("Starting scheduled backup job")
        backup_type = config.get("backup_type", "full")

        result = create_enhanced_backup(
            manual=False,
            backup_type=backup_type
        )

        if result:
            notify_backup_result(True, result, "scheduled backup")
            cleanup_old_backups()
        else:
            notify_backup_result(False, "unknown", "scheduled backup")

        return result is not None
    except Exception as e:
        logger.error(f"Error in scheduled backup job: {e}")
        try:
            notify_backup_result(False, str(e), "scheduled backup")
        except Exception:
            pass
        return False

def get_connection():
    """Database connection wrapper for compatibility"""
    try:
        return get_db_connection()
    except Exception:
        # Fallback to direct sqlite connection
        from education_system.post_18.university_system.infrastructure.database.db import sqlite3
        return sqlite3.connect(str(DEFAULT_DB_PATH))
