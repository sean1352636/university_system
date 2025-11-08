#!/usr/bin/env python3
"""
Email Scheduler Control Script

This script provides a command-line interface to control the email scheduler.

Usage:
    python -m university_system.utils.email_scheduler_control start
    python -m university_system.utils.email_scheduler_control stop
    python -m university_system.utils.email_scheduler_control status
    python -m university_system.utils.email_scheduler_control run

Commands:
    start   - Start the scheduler in the background
    stop    - Stop the scheduler
    status  - Check scheduler status
    run     - Run scheduler in foreground (blocking)
"""

import sys
import time
import signal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from university_system.infrastructure.email.email_scheduler import (
    start_scheduler,
    stop_scheduler,
    is_scheduler_running,
    get_scheduled_jobs,
    run_scheduler
)


def print_status():
    """Print current scheduler status"""
    if is_scheduler_running():
        print("✅ Email Scheduler: RUNNING")
        print("\nScheduled Jobs:")
        jobs = get_scheduled_jobs()
        for i, job in enumerate(jobs, 1):
            print(f"  {i}. {job}")
    else:
        print("❌ Email Scheduler: STOPPED")


def start_command():
    """Start the scheduler"""
    if is_scheduler_running():
        print("⚠️  Email scheduler is already running")
        return 1

    print("Starting email scheduler...")
    if start_scheduler():
        time.sleep(1)  # Give it a moment to fully start
        print("✅ Email scheduler started successfully")
        print("\nScheduled Tasks:")
        print("  - Satisfaction surveys: Daily at 09:00")
        print("  - Book return reminders: Daily at 08:00")
        print("  - Overdue book notices: Daily at 10:00")
        print("  - SLA breach alerts: Every 30 minutes")
        print("\nScheduler is running in background.")
        print("Use 'status' to check status or 'stop' to stop it.")
        return 0
    else:
        print("❌ Failed to start email scheduler")
        return 1


def stop_command():
    """Stop the scheduler"""
    if not is_scheduler_running():
        print("⚠️  Email scheduler is not running")
        return 1

    print("Stopping email scheduler...")
    if stop_scheduler(timeout=10):
        print("✅ Email scheduler stopped successfully")
        return 0
    else:
        print("❌ Failed to stop email scheduler (timeout)")
        return 1


def run_command():
    """Run scheduler in foreground"""
    print("Starting email scheduler in foreground mode...")
    print("Press Ctrl+C to stop")
    print("-" * 50)

    # Set up signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("\n\nShutting down scheduler...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        run_scheduler()
    except KeyboardInterrupt:
        print("\n✅ Scheduler stopped by user")
        return 0


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python -m university_system.utils.email_scheduler_control {start|stop|status|run}")
        print("\nCommands:")
        print("  start   - Start the scheduler in the background")
        print("  stop    - Stop the scheduler")
        print("  status  - Check scheduler status")
        print("  run     - Run scheduler in foreground (blocking)")
        return 1

    command = sys.argv[1].lower()

    if command == 'start':
        return start_command()
    elif command == 'stop':
        return stop_command()
    elif command == 'status':
        print_status()
        return 0
    elif command == 'run':
        return run_command()
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: start, stop, status, run")
        return 1


if __name__ == '__main__':
    sys.exit(main())
