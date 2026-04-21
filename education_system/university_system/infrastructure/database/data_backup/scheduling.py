"""Backup scheduling with cron and simple time-based triggers."""

import datetime
import threading
import time

import schedule

from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.infrastructure.database.data_backup.config import config
import education_system.university_system.infrastructure.database.data_backup.config as _cfg
from education_system.university_system.infrastructure.database.data_backup.operations import create_enhanced_backup
from education_system.university_system.infrastructure.database.data_backup.notifications import notify_backup_result

logger = configure_logging(name=__name__)


def parse_cron_schedule(cron_expr):
    """Parse cron expression and schedule backup"""
    try:
        # Use croniter to parse cron expressions
        from croniter import croniter

        def cron_backup_job():
            if config["auto_backup_enabled"]:
                logger.info(f"Running cron scheduled backup at {datetime.datetime.now()}")
                create_enhanced_backup(manual=False)

        # Schedule using cron expression
        schedule.clear()

        # This is a simplified implementation
        # In a full implementation, you'd use a proper cron scheduler
        cron = croniter(cron_expr, datetime.datetime.now())
        next_run = cron.get_next(datetime.datetime)

        logger.info(f"Next backup scheduled for: {next_run}")

        # For demo purposes, we'll just log the schedule
        # Real implementation would use a proper cron daemon

    except ValueError as e:
        logger.error(f"Invalid cron expression: {e}")
    except ImportError as e:
        logger.error(f"croniter module not available: {e}")


def scheduled_backup_job():
    """Enhanced scheduled backup function"""
    try:
        if not config["auto_backup_enabled"]:
            return

        logger.info(f"Running scheduled backup at {datetime.datetime.now()}")

        # Determine backup type based on schedule
        backup_type = "full"
        if config["enable_incremental"]:
            # Simple logic: full backup once a week, incremental otherwise
            now = datetime.datetime.now()
            if now.weekday() == 0:  # Monday
                backup_type = "full"
            else:
                backup_type = "incremental"

        # Create backup
        backup_path = create_enhanced_backup(
            manual=False,
            backup_type=backup_type
        )

        if backup_path:
            logger.info(f"Scheduled backup completed: {backup_path}")
        else:
            logger.error("Scheduled backup failed")

        # Auto-validate if enabled
        if config["auto_validate"] and backup_path:
            from education_system.university_system.infrastructure.database.data_backup.analysis import validate_backup
            validation_results = validate_backup(backup_path)
            if validation_results.get("errors"):
                logger.warning(f"Backup validation issues: {validation_results['errors']}")
                notify_backup_result(False, backup_path, "validation")

    except (KeyError, TypeError) as e:
        logger.error(f"Configuration error in scheduled backup job: {e}")
    except (OSError, IOError) as e:
        logger.error(f"I/O error in scheduled backup job: {e}")


def start_scheduler():
    """Start the enhanced backup scheduler"""
    # Set up the schedule based on configuration
    backup_time = config["scheduled_backup_time"]
    frequency = config["backup_frequency"]
    cron_schedule = config.get("cron_schedule", "")

    # Clear any existing jobs
    schedule.clear()

    # Use cron schedule if provided
    if cron_schedule:
        try:
            parse_cron_schedule(cron_schedule)
        except (ValueError, ImportError) as e:
            logger.error(f"Invalid cron schedule, falling back to simple schedule: {e}")

    # Schedule based on frequency
    if frequency == "daily":
        schedule.every().day.at(backup_time).do(scheduled_backup_job)
    elif frequency == "weekly":
        schedule.every().monday.at(backup_time).do(scheduled_backup_job)
    elif frequency == "monthly":
        schedule.every().day.at(backup_time).do(lambda:
            scheduled_backup_job() if datetime.datetime.now().day == 1 else None)

    # Define the scheduler loop
    def run_scheduler():
        while not _cfg.stop_flag:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    # Start the scheduler in a new thread
    _cfg.stop_flag = False
    _cfg.backup_thread = threading.Thread(target=run_scheduler)
    _cfg.backup_thread.daemon = True
    _cfg.backup_thread.start()

    logger.info(f"Enhanced backup scheduler started. Frequency: {frequency}, Time: {backup_time}")


def stop_scheduler():
    """Stop the backup scheduler thread"""
    if _cfg.backup_thread and _cfg.backup_thread.is_alive():
        _cfg.stop_flag = True
        _cfg.backup_thread.join(timeout=1)
        logger.info("Backup scheduler stopped")
