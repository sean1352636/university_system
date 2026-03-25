"""Logging utilities and reporting helpers for the email infrastructure package.

This module is in the core package. It depends only on stdlib and other core
modules. Optional lazy imports from infrastructure/utils are kept behind
try/except guards to avoid circular imports.
"""

from __future__ import annotations

import csv
import logging
import os
import sqlite3
import smtplib
from datetime import datetime, timedelta

from education_system.university_system.core.i18n import get_text as _t

# state module is imported lazily when needed to avoid circular imports
state = None

def _get_state():
    """Lazily import and return the state module."""
    global state
    if state is None:
        try:
            from education_system.university_system.infrastructure.email import state as _state
            state = _state
        except ImportError:
            try:
                from education_system.university_system.modules.shared.utils import state as _state
                state = _state
            except ImportError:
                pass
    return state

from education_system.university_system.core import paths

try:
    from education_system.university_system.utils.logging.log_config import (
        configure_logging as project_configure_logging,
        get_log_file as project_get_log_file,
    )
except ImportError:  # pragma: no cover - optional dependency
    project_configure_logging = None
    project_get_log_file = None

# Log management is imported lazily to avoid circular imports
get_log_manager = None
global_log_manager = None
LOG_MANAGEMENT_AVAILABLE = False
log_manager = None
_log_management_checked = False

def _init_log_management():
    """Lazily initialize log management to avoid circular imports."""
    global get_log_manager, global_log_manager, LOG_MANAGEMENT_AVAILABLE, log_manager, _log_management_checked
    if _log_management_checked:
        return
    _log_management_checked = True
    try:
        from education_system.university_system.utils.logging.log_management import (
            get_log_manager as _get_log_manager,
            log_manager as _global_log_manager,
        )
        get_log_manager = _get_log_manager
        global_log_manager = _global_log_manager
        LOG_MANAGEMENT_AVAILABLE = True
    except ImportError:
        pass

def get_log_file(filename: str) -> str:
    """Get log file path, creating directory if needed."""
    if project_get_log_file:
        try:
            return project_get_log_file(filename)
        except Exception as e:  # pragma: no cover - external hook failed
            # Log to stderr since logger may not be configured yet
            import sys
            print(f"Warning: project_get_log_file hook failed: {e}", file=sys.stderr)
            # Fall through to default behavior

    log_dir = paths.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, filename)

def configure_logging() -> None:
    """Configure logging with project settings when available, else fallback."""
    if project_configure_logging:
        try:
            project_configure_logging()
            return
        except Exception as e:  # pragma: no cover - external config failed
            # Log to stderr since logger may not be configured yet
            import sys
            print(f"Warning: project_configure_logging hook failed: {e}. Using fallback configuration.", file=sys.stderr)
            # Fall through to fallback configuration

    # Use centralized app.log for all logging
    log_file = project_get_log_file("app.log") if project_get_log_file else os.path.join(paths.LOG_DIR, "app.log")
    os.makedirs(paths.LOG_DIR, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )

configure_logging()

logger = logging.getLogger(__name__)

def log_event(level, message):
    """Enhanced logging function that uses both standard logging and activity logging"""
    # Ensure log management is initialized
    _init_log_management()

    # Standard logging
    if level == 'debug':
        logger.debug(message)
    elif level == 'info':
        logger.info(message)
    elif level == 'warning':
        logger.warning(message)
    elif level == 'error':
        logger.error(message)
    elif level == 'critical':
        logger.critical(message)
    else:
        logger.info(message)

    # Enhanced activity logging if available and user is authenticated
    _state = _get_state()
    if (
        LOG_MANAGEMENT_AVAILABLE
        and log_manager
        and _state
        and getattr(_state, 'auth', None)
        and getattr(_state.auth, "current_user", None)
    ):
        try:
            # Create activity log entry
            activity_data = {
                'timestamp': datetime.now().isoformat(),
                'user_id': _state.auth.current_user.get('user_id') or _state.auth.current_user.get('id'),
                'username': _state.auth.current_user.get('username', 'unknown'),
                'role': _state.auth.current_user.get('role', 'unknown'),
                'action': 'email_system_activity',
                'module': 'email_manager',
                'details': message,
                'status': 'success' if level in ['info', 'debug'] else level
            }

            # Store in enhanced log system
            log_manager.db.insert_log(activity_data)

        except Exception as e:
            # Don't fail email operations due to logging issues
            logger.warning(f"Enhanced logging failed: {e}")

def handle_exception(func):
    """Decorator for uniform exception handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            log_event('error', f"Database error in {func.__name__}: {e}")
            return False
        except smtplib.SMTPException as e:
            log_event('error', f"SMTP error in {func.__name__}: {e}")
            return False
        except Exception as e:
            log_event('error', f"Unexpected error in {func.__name__}: {e}")
            return False
    return wrapper

def display_communication_logs_menu(dashboard):
    """Display communication activity logs menu with enhanced filtering"""
    while True:
        print(f"\n{_t('shared.utils.logs.menu_title')}:")
        print("===========================")
        print(f"1. {_t('shared.utils.logs.recent_activity')}")
        print(f"2. {_t('shared.utils.logs.activity_by_date')}")
        print(f"3. {_t('shared.utils.logs.activity_by_user')}")
        print(f"4. {_t('shared.utils.logs.email_logs')}")
        print(f"5. {_t('shared.utils.logs.message_logs')}")
        print(f"6. {_t('shared.utils.logs.chat_logs')}")
        print(f"7. {_t('shared.utils.logs.search_logs')}")
        print(f"8. {_t('shared.utils.logs.export_logs')}")
        print(f"9. {_t('shared.utils.logs.back_to_dashboard')}")

        choice = input(_t('shared.utils.logs.enter_choice_1_9'))

        if choice == '1':
            logs = dashboard.get_communication_logs(days=1, limit=50)
            display_activity_logs(logs, _t('shared.utils.logs.activity_last_24h'))

        elif choice == '2':
            days = input(_t('shared.utils.logs.enter_days_prompt'))
            try:
                days = int(days) if days else 7
                logs = dashboard.get_communication_logs(days=days, limit=100)
                display_activity_logs(logs, _t('shared.utils.logs.activity_last_n_days', days=days))
            except ValueError:
                print(_t('shared.utils.logs.invalid_days'))

        elif choice == '3':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                username = input(_t('shared.utils.logs.enter_username_prompt'))
                if username:
                    logs = dashboard.get_communication_logs(days=30, limit=100, user_filter=username)
                    display_activity_logs(logs, _t('shared.utils.logs.activity_for_user', username=username))

        elif choice == '4':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                logs = dashboard.get_communication_logs(days=7, limit=100, action_filter='email')
                display_activity_logs(logs, _t('shared.utils.logs.email_system_activity'))

        elif choice == '5':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                logs = dashboard.get_communication_logs(days=7, limit=100, action_filter='send_message')
                display_activity_logs(logs, _t('shared.utils.logs.message_system_activity'))

        elif choice == '6':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                logs = dashboard.get_communication_logs(days=7, limit=100, action_filter='chat')
                display_activity_logs(logs, _t('shared.utils.logs.chat_system_activity'))

        elif choice == '7':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                search_term = input(_t('shared.utils.logs.enter_search_term'))
                if search_term:
                    filters = {
                        'search_text': search_term,
                        'module': 'email_manager',
                        'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                    }
                    logs = log_manager.db.search_logs(filters, limit=100)
                    display_activity_logs(logs, _t('shared.utils.logs.search_results', term=search_term))

        elif choice == '8':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                export_communication_logs(dashboard)

        elif choice == '9':
            break
        else:
            print(_t('shared.utils.logs.invalid_choice'))

def display_activity_logs(logs, title):
    """Display activity logs in a formatted table"""
    if not logs:
        print(f"\n{_t('shared.utils.logs.no_activity_found', title=title)}")
        input(_t('shared.utils.logs.press_enter'))
        return

    print(f"\n{title} ({_t('shared.utils.logs.entries_count', count=len(logs))}):")
    print("=" * 110)
    print(f"{_t('shared.utils.logs.col_time'):<20}{_t('shared.utils.logs.col_user'):<15}{_t('shared.utils.logs.col_action'):<25}{_t('shared.utils.logs.col_status'):<10}{_t('shared.utils.logs.col_details'):<40}")
    print("-" * 110)

    for log in logs[:25]:  # Show first 25
        timestamp = log.get('timestamp', '')[:19]
        username = log.get('username', '')[:14]
        action = log.get('action', '')[:24]
        status = log.get('status', '')[:9]
        details = log.get('details', '')[:39]

        print(f"{timestamp:<20}{username:<15}{action:<25}{status:<10}{details:<40}")

    if len(logs) > 25:
        print(f"\n{_t('shared.utils.logs.more_entries', count=len(logs) - 25)}")

        show_all = input(f"\n{_t('shared.utils.logs.show_all_prompt')}")
        if show_all.lower() == 'y':
            for log in logs[25:]:
                timestamp = log.get('timestamp', '')[:19]
                username = log.get('username', '')[:14]
                action = log.get('action', '')[:24]
                status = log.get('status', '')[:9]
                details = log.get('details', '')[:39]

                print(f"{timestamp:<20}{username:<15}{action:<25}{status:<10}{details:<40}")

    input(f"\n{_t('shared.utils.logs.press_enter')}")

def export_communication_logs(dashboard):
    """Export communication logs to CSV"""
    try:
        days = input(_t('shared.utils.logs.export_days_prompt'))
        days = int(days) if days else 30

        logs = dashboard.get_communication_logs(days=days, limit=5000)

        if not logs:
            print(_t('shared.utils.logs.no_logs_for_export'))
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"communication_logs_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'user_id', 'username', 'role', 'action', 'module', 'details', 'status']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for log in logs:
                writer.writerow({
                    'timestamp': log.get('timestamp', ''),
                    'user_id': log.get('user_id', ''),
                    'username': log.get('username', ''),
                    'role': log.get('role', ''),
                    'action': log.get('action', ''),
                    'module': log.get('module', ''),
                    'details': log.get('details', ''),
                    'status': log.get('status', '')
                })

        print(_t('shared.utils.logs.export_success', count=len(logs), filename=filename))

    except Exception as e:
        print(_t('shared.utils.logs.export_error', error=e))

    input(f"\n{_t('shared.utils.logs.press_enter')}")

def display_communication_analytics_menu(dashboard):
    """Display communication analytics for admins"""
    from education_system.university_system.modules.shared.utils.database import execute_db_operation  # Local import to avoid circular dependency
    from education_system.university_system.modules.shared.utils.email_service import get_stored_emails  # Local import to avoid circular dependency

    while True:
        print(f"\n{_t('shared.utils.logs.analytics_title')}:")
        print("=======================")
        print(f"1. {_t('shared.utils.logs.activity_summary')}")
        print(f"2. {_t('shared.utils.logs.user_activity_report')}")
        print(f"3. {_t('shared.utils.logs.email_statistics')}")
        print(f"4. {_t('shared.utils.logs.message_statistics')}")
        print(f"5. {_t('shared.utils.logs.chat_statistics')}")
        print(f"6. {_t('shared.utils.logs.generate_charts')}")
        print(f"7. {_t('shared.utils.logs.back_to_dashboard')}")

        choice = input(_t('shared.utils.logs.enter_choice_1_7'))

        if choice == '1':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                try:
                    summary = dashboard.get_communication_analytics(30)
                    if summary:
                        print(f"\n{_t('shared.utils.logs.summary_title')}:")
                        print("=" * 50)
                        print(f"{_t('shared.utils.logs.total_activities')}: {summary.get('total_activities', 0):,}")
                        print(f"{_t('shared.utils.logs.unique_users')}: {summary.get('unique_users', 0)}")
                        print(f"{_t('shared.utils.logs.success_rate')}: {summary.get('success_rate', 0):.1f}%")
                        print(f"{_t('shared.utils.logs.failed_activities')}: {summary.get('failed_activities', 0)}")

                        if 'most_active_users' in summary:
                            print(f"\n{_t('shared.utils.logs.most_active_users')}:")
                            for user, count in list(summary['most_active_users'].items())[:5]:
                                print(f"  {user}: {_t('shared.utils.logs.activities_count', count=count)}")

                        if 'activity_by_action' in summary:
                            print(f"\n{_t('shared.utils.logs.activity_by_type')}:")
                            for action, count in list(summary['activity_by_action'].items())[:5]:
                                print(f"  {action}: {count}")
                    else:
                        print(_t('shared.utils.logs.no_analytics_data'))
                except Exception as e:
                    print(_t('shared.utils.logs.error_retrieving_analytics', error=e))
            else:
                print(_t('shared.utils.logs.enhanced_logging_unavailable'))

            input(f"\n{_t('shared.utils.logs.press_enter')}")

        elif choice == '2':
            username = input(_t('shared.utils.logs.enter_username_for_report'))
            if username and LOG_MANAGEMENT_AVAILABLE and log_manager:
                try:
                    # Get user ID first
                    def _get_user_id(cursor):
                        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                        result = cursor.fetchone()
                        return result[0] if result else None

                    user_id = execute_db_operation(_get_user_id)
                    if user_id:
                        report = log_manager.analytics.generate_user_activity_report(user_id, 30)
                        if report and 'error' not in report:
                            print(f"\n{_t('shared.utils.logs.user_report_title', username=username)}")
                            print("=" * 40)
                            print(f"{_t('shared.utils.logs.total_activities')}: {report.get('total_activities', 0):,}")
                            print(f"{_t('shared.utils.logs.success_rate')}: {report.get('success_rate', 0):.1f}%")

                            if 'modules_used' in report:
                                print(f"\n{_t('shared.utils.logs.modules_used')}:")
                                for module, count in list(report['modules_used'].items())[:5]:
                                    print(f"  {module}: {count}")
                        else:
                            print(_t('shared.utils.logs.no_activity_for_user', username=username))
                    else:
                        print(_t('shared.utils.logs.user_not_found', username=username))
                except Exception as e:
                    print(_t('shared.utils.logs.error_generating_report', error=e))

            input(f"\n{_t('shared.utils.logs.press_enter')}")

        elif choice == '3':
            # Email statistics
            try:
                emails_data = get_stored_emails(limit=1)
                print(f"\n{_t('shared.utils.logs.email_stats_title')}:")
                print("=" * 30)
                print(f"{_t('shared.utils.logs.total_stored_emails')}: {emails_data['total_count']:,}")

                # Get recent email activity
                if LOG_MANAGEMENT_AVAILABLE and log_manager:
                    filters = {
                        'action': 'email',
                        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    }
                    recent_emails = log_manager.db.search_logs(filters, limit=100)
                    print(f"{_t('shared.utils.logs.email_activities_7_days')}: {len(recent_emails)}")

            except Exception as e:
                print(_t('shared.utils.logs.error_email_statistics', error=e))

            input(f"\n{_t('shared.utils.logs.press_enter')}")

        elif choice == '4':
            # Message statistics
            try:
                def _get_message_stats(cursor):
                    cursor.execute('SELECT COUNT(*) FROM messages')
                    total_messages = cursor.fetchone()[0]

                    cursor.execute('SELECT COUNT(*) FROM messages WHERE is_read = 0')
                    unread_messages = cursor.fetchone()[0]

                    cursor.execute('''
                    SELECT COUNT(*) FROM messages
                    WHERE sent_at >= date('now', '-7 days')
                    ''')
                    recent_messages = cursor.fetchone()[0]

                    return total_messages, unread_messages, recent_messages

                total, unread, recent = execute_db_operation(_get_message_stats)

                print(f"\n{_t('shared.utils.logs.message_stats_title')}:")
                print("=" * 30)
                print(f"{_t('shared.utils.logs.total_messages')}: {total:,}")
                print(f"{_t('shared.utils.logs.unread_messages')}: {unread:,}")
                print(f"{_t('shared.utils.logs.messages_7_days')}: {recent:,}")

            except Exception as e:
                print(_t('shared.utils.logs.error_message_statistics', error=e))

            input(f"\n{_t('shared.utils.logs.press_enter')}")

        elif choice == '5':
            # Chat statistics
            try:
                def _get_chat_stats(cursor):
                    cursor.execute('SELECT COUNT(*) FROM chat_rooms WHERE is_active = 1')
                    active_rooms = cursor.fetchone()[0]

                    cursor.execute('SELECT COUNT(*) FROM chat_room_members')
                    total_memberships = cursor.fetchone()[0]

                    cursor.execute('SELECT COUNT(*) FROM chat_messages')
                    total_chat_messages = cursor.fetchone()[0]

                    return active_rooms, total_memberships, total_chat_messages

                rooms, memberships, messages = execute_db_operation(_get_chat_stats)

                print(f"\n{_t('shared.utils.logs.chat_stats_title')}:")
                print("=" * 25)
                print(f"{_t('shared.utils.logs.active_chat_rooms')}: {rooms:,}")
                print(f"{_t('shared.utils.logs.total_memberships')}: {memberships:,}")
                print(f"{_t('shared.utils.logs.total_chat_messages')}: {messages:,}")

            except Exception as e:
                print(_t('shared.utils.logs.error_chat_statistics', error=e))

            input(f"\n{_t('shared.utils.logs.press_enter')}")

        elif choice == '6':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                try:
                    days = input(_t('shared.utils.logs.generate_chart_days_prompt'))
                    days = int(days) if days else 7

                    filename = f"communication_activity_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

                    chart_path = log_manager.analytics.create_activity_chart("daily", days, filename)

                    if chart_path:
                        print(_t('shared.utils.logs.chart_saved', path=chart_path))
                    else:
                        print(_t('shared.utils.logs.chart_generation_completed'))

                except Exception as e:
                    print(_t('shared.utils.logs.error_generating_chart', error=e))
            else:
                print(_t('shared.utils.logs.enhanced_logging_unavailable_charts'))

            input(f"\n{_t('shared.utils.logs.press_enter')}")

        elif choice == '7':
            break
        else:
            print(_t('shared.utils.logs.invalid_choice'))


__all__ = [
    "log_event",
    "handle_exception",
    "logger",
    "configure_logging",
    "get_log_file",
    "display_communication_logs_menu",
    "display_activity_logs",
    "export_communication_logs",
    "display_communication_analytics_menu",
]
