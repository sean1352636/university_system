"""Logging utilities and reporting helpers for the email infrastructure package."""

from __future__ import annotations

import csv
import logging
import os
from university_system.infrastructure.database.db import sqlite3
import smtplib
from datetime import datetime, timedelta

try:
    from university_system.infrastructure.email import state
except ImportError:
    try:
        from university_system.modules.shared.utils import state
    except ImportError:
        state = None
from university_system.modules.shared.constants import paths

try:
    from university_system.utils.logging.log_config import (
        configure_logging as project_configure_logging,
        get_log_file as project_get_log_file,
    )
except ImportError:  # pragma: no cover - optional dependency
    project_configure_logging = None
    project_get_log_file = None

try:
    from university_system.utils.logging.log_management import (  # type: ignore
        get_log_manager,
        log_manager as global_log_manager,
    )

    LOG_MANAGEMENT_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    get_log_manager = None
    global_log_manager = None
    LOG_MANAGEMENT_AVAILABLE = False

log_manager = None


def get_log_file(filename: str) -> str:
    """Get log file path, creating directory if needed."""
    if project_get_log_file:
        try:
            return project_get_log_file(filename)
        except Exception:  # pragma: no cover - external hook failed
            pass

    log_dir = paths.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, filename)



def configure_logging() -> None:
    """Configure logging with project settings when available, else fallback."""
    if project_configure_logging:
        try:
            project_configure_logging()
            return
        except Exception:  # pragma: no cover - external config failed
            pass

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

logger = logging.getLogger("email_manager")



def log_event(level, message):
    """Enhanced logging function that uses both standard logging and activity logging"""
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
    if (
        LOG_MANAGEMENT_AVAILABLE
        and log_manager
        and state.auth
        and getattr(state.auth, "current_user", None)
    ):
        try:
            # Create activity log entry
            activity_data = {
                'timestamp': datetime.now().isoformat(),
                'user_id': state.auth.current_user['id'],
                'username': state.auth.current_user['username'],
                'role': state.auth.current_user['role'],
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
        print("\nCommunication Activity Logs:")
        print("===========================")
        print("1. Recent Activity (Last 24 hours)")
        print("2. Activity by Date Range") 
        print("3. Activity by User")
        print("4. Email System Logs")
        print("5. Message System Logs")
        print("6. Chat System Logs")
        print("7. Search Activity Logs")
        print("8. Export Activity Logs")
        print("9. Back to Communication Dashboard")
        
        choice = input("Enter your choice (1-9): ")
        
        if choice == '1':
            logs = dashboard.get_communication_logs(days=1, limit=50)
            display_activity_logs(logs, "Communication Activity - Last 24 Hours")
            
        elif choice == '2':
            days = input("Enter number of days to look back (default: 7): ")
            try:
                days = int(days) if days else 7
                logs = dashboard.get_communication_logs(days=days, limit=100)
                display_activity_logs(logs, f"Communication Activity - Last {days} Days")
            except ValueError:
                print("Invalid number of days")
                
        elif choice == '3':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                username = input("Enter username to search: ")
                if username:
                    logs = dashboard.get_communication_logs(days=30, limit=100, user_filter=username)
                    display_activity_logs(logs, f"Communication Activity for {username}")
                    
        elif choice == '4':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                logs = dashboard.get_communication_logs(days=7, limit=100, action_filter='email')
                display_activity_logs(logs, "Email System Activity")
                
        elif choice == '5':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                logs = dashboard.get_communication_logs(days=7, limit=100, action_filter='send_message')
                display_activity_logs(logs, "Message System Activity")
                
        elif choice == '6':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                logs = dashboard.get_communication_logs(days=7, limit=100, action_filter='chat')
                display_activity_logs(logs, "Chat System Activity")
                
        elif choice == '7':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                search_term = input("Enter search term: ")
                if search_term:
                    filters = {
                        'search_text': search_term,
                        'module': 'email_manager',
                        'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                    }
                    logs = log_manager.db.search_logs(filters, limit=100)
                    display_activity_logs(logs, f"Search Results: {search_term}")
                    
        elif choice == '8':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                export_communication_logs(dashboard)
                
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")



def display_activity_logs(logs, title):
    """Display activity logs in a formatted table"""
    if not logs:
        print(f"\nNo activity found for {title}")
        input("Press Enter to continue...")
        return
    
    print(f"\n{title} ({len(logs)} entries):")
    print("=" * 110)
    print(f"{'Time':<20}{'User':<15}{'Action':<25}{'Status':<10}{'Details':<40}")
    print("-" * 110)
    
    for log in logs[:25]:  # Show first 25
        timestamp = log.get('timestamp', '')[:19]
        username = log.get('username', '')[:14]
        action = log.get('action', '')[:24]
        status = log.get('status', '')[:9]
        details = log.get('details', '')[:39]
        
        print(f"{timestamp:<20}{username:<15}{action:<25}{status:<10}{details:<40}")
    
    if len(logs) > 25:
        print(f"\n... and {len(logs) - 25} more entries")
        
        show_all = input("\nShow all entries? (y/n): ")
        if show_all.lower() == 'y':
            for log in logs[25:]:
                timestamp = log.get('timestamp', '')[:19]
                username = log.get('username', '')[:14]
                action = log.get('action', '')[:24]
                status = log.get('status', '')[:9]
                details = log.get('details', '')[:39]
                
                print(f"{timestamp:<20}{username:<15}{action:<25}{status:<10}{details:<40}")
    
    input("\nPress Enter to continue...")



def export_communication_logs(dashboard):
    """Export communication logs to CSV"""
    try:
        days = input("Export logs from last how many days? (default: 30): ")
        days = int(days) if days else 30
        
        logs = dashboard.get_communication_logs(days=days, limit=5000)
        
        if not logs:
            print("No logs found for export.")
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
        
        print(f"Exported {len(logs)} log entries to {filename}")
        
    except Exception as e:
        print(f"Error exporting logs: {e}")
    
    input("\nPress Enter to continue...")



def display_communication_analytics_menu(dashboard):
    """Display communication analytics for admins"""
    from .finance_db_operations import execute_db_operation  # Local import to avoid circular dependency
    from .email_service import get_stored_emails  # Local import to avoid circular dependency

    while True:
        print("\nCommunication Analytics:")
        print("=======================")
        print("1. Activity Summary (Last 30 days)")
        print("2. User Activity Report")
        print("3. Email System Statistics")
        print("4. Message System Statistics")
        print("5. Chat System Statistics")
        print("6. Generate Activity Charts")
        print("7. Back to Communication Dashboard")
        
        choice = input("Enter your choice (1-7): ")
        
        if choice == '1':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                try:
                    summary = dashboard.get_communication_analytics(30)
                    if summary:
                        print(f"\nCommunication Activity Summary (Last 30 days):")
                        print("=" * 50)
                        print(f"Total Activities: {summary.get('total_activities', 0):,}")
                        print(f"Unique Users: {summary.get('unique_users', 0)}")
                        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
                        print(f"Failed Activities: {summary.get('failed_activities', 0)}")
                        
                        if 'most_active_users' in summary:
                            print(f"\nMost Active Users:")
                            for user, count in list(summary['most_active_users'].items())[:5]:
                                print(f"  {user}: {count} activities")
                        
                        if 'activity_by_action' in summary:
                            print(f"\nActivity by Type:")
                            for action, count in list(summary['activity_by_action'].items())[:5]:
                                print(f"  {action}: {count}")
                    else:
                        print("No analytics data available.")
                except Exception as e:
                    print(f"Error retrieving analytics: {e}")
            else:
                print("Enhanced logging not available.")
            
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            username = input("Enter username for detailed report: ")
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
                            print(f"\nUser Activity Report: {username}")
                            print("=" * 40)
                            print(f"Total Activities: {report.get('total_activities', 0):,}")
                            print(f"Success Rate: {report.get('success_rate', 0):.1f}%")
                            
                            if 'modules_used' in report:
                                print(f"\nModules Used:")
                                for module, count in list(report['modules_used'].items())[:5]:
                                    print(f"  {module}: {count}")
                        else:
                            print(f"No activity found for user {username}")
                    else:
                        print(f"User {username} not found")
                except Exception as e:
                    print(f"Error generating user report: {e}")
            
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            # Email statistics
            try:
                emails_data = get_stored_emails(limit=1)
                print(f"\nEmail System Statistics:")
                print("=" * 30)
                print(f"Total Stored Emails: {emails_data['total_count']:,}")
                
                # Get recent email activity
                if LOG_MANAGEMENT_AVAILABLE and log_manager:
                    filters = {
                        'action': 'email',
                        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    }
                    recent_emails = log_manager.db.search_logs(filters, limit=100)
                    print(f"Email Activities (Last 7 days): {len(recent_emails)}")
                
            except Exception as e:
                print(f"Error getting email statistics: {e}")
            
            input("\nPress Enter to continue...")
            
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
                
                print(f"\nMessage System Statistics:")
                print("=" * 30)
                print(f"Total Messages: {total:,}")
                print(f"Unread Messages: {unread:,}")
                print(f"Messages (Last 7 days): {recent:,}")
                
            except Exception as e:
                print(f"Error getting message statistics: {e}")
            
            input("\nPress Enter to continue...")
            
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
                
                print(f"\nChat System Statistics:")
                print("=" * 25)
                print(f"Active Chat Rooms: {rooms:,}")
                print(f"Total Memberships: {memberships:,}")
                print(f"Total Chat Messages: {messages:,}")
                
            except Exception as e:
                print(f"Error getting chat statistics: {e}")
            
            input("\nPress Enter to continue...")
            
        elif choice == '6':
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                try:
                    days = input("Generate chart for last how many days? (default: 7): ")
                    days = int(days) if days else 7
                    
                    filename = f"communication_activity_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    
                    chart_path = log_manager.analytics.create_activity_chart("daily", days, filename)
                    
                    if chart_path:
                        print(f"Activity chart saved to: {chart_path}")
                    else:
                        print("Chart generation completed")
                        
                except Exception as e:
                    print(f"Error generating chart: {e}")
            else:
                print("Enhanced logging not available for chart generation.")
            
            input("\nPress Enter to continue...")
            
        elif choice == '7':
            break
        else:
            print("Invalid choice. Please try again.")
