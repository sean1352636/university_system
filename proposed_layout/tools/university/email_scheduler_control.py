#!/usr/bin/env python3
"""
Email Scheduler Control Script

This script provides a command-line interface to control the email scheduler.

Usage:
    python -m university_system.scripts.email_scheduler_control start
    python -m university_system.scripts.email_scheduler_control stop
    python -m university_system.scripts.email_scheduler_control status
    python -m university_system.scripts.email_scheduler_control run

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
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from education_system.systems.university.infrastructure.email.email_scheduler import (
    start_scheduler,
    stop_scheduler,
    is_scheduler_running,
    get_scheduled_jobs,
    run_scheduler
)
from education_system.systems.university.infrastructure.i18n import get_text


def print_status():
    """Print current scheduler status"""
    if is_scheduler_running():
        print(get_text("email.scheduler.status_running"))
        print("\n" + get_text("email.scheduler.scheduled_jobs"))
        jobs = get_scheduled_jobs()
        for i, job in enumerate(jobs, 1):
            print(f"  {i}. {job}")
    else:
        print(get_text("email.scheduler.status_stopped"))


def start_command():
    """Start the scheduler"""
    if is_scheduler_running():
        print(get_text("email.scheduler.already_running"))
        return 1

    print(get_text("email.scheduler.starting"))
    if start_scheduler():
        time.sleep(1)  # Give it a moment to fully start
        print(get_text("email.scheduler.started_success"))
        print("\n" + get_text("email.scheduler.scheduled_tasks"))
        print("  - " + get_text("email.scheduler.task_satisfaction_surveys"))
        print("  - " + get_text("email.scheduler.task_book_return_reminders"))
        print("  - " + get_text("email.scheduler.task_overdue_book_notices"))
        print("  - " + get_text("email.scheduler.task_sla_breach_alerts"))
        print("\n" + get_text("email.scheduler.running_in_background"))
        print(get_text("email.scheduler.use_status_or_stop"))
        return 0
    else:
        print(get_text("email.scheduler.start_failed"))
        return 1


def stop_command():
    """Stop the scheduler"""
    if not is_scheduler_running():
        print(get_text("email.scheduler.not_running"))
        return 1

    print(get_text("email.scheduler.stopping"))
    if stop_scheduler(timeout=10):
        print(get_text("email.scheduler.stopped_success"))
        return 0
    else:
        print(get_text("email.scheduler.stop_failed"))
        return 1


def run_command():
    """Run scheduler in foreground"""
    print(get_text("email.scheduler.foreground_mode"))
    print(get_text("email.scheduler.press_ctrl_c"))
    print("-" * 50)

    # Set up signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("\n\n" + get_text("email.scheduler.shutting_down"))
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        run_scheduler()
    except KeyboardInterrupt:
        print("\n" + get_text("email.scheduler.stopped_by_user"))
        return 0


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(get_text("email.scheduler.usage"))
        print("\n" + get_text("email.scheduler.commands_header"))
        print("  start   - " + get_text("email.scheduler.cmd_start_desc"))
        print("  stop    - " + get_text("email.scheduler.cmd_stop_desc"))
        print("  status  - " + get_text("email.scheduler.cmd_status_desc"))
        print("  run     - " + get_text("email.scheduler.cmd_run_desc"))
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
        print(get_text("email.scheduler.unknown_command", command=command))
        print(get_text("email.scheduler.valid_commands"))
        return 1


if __name__ == '__main__':
    sys.exit(main())
