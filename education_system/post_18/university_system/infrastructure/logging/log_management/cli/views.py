"""Basic log viewing and configuration CLI functions."""

from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.validation.sanitizers import sanitize_input


def view_recent_logs(log_manager, auth):
    """View recent activity logs"""
    print("\n\U0001f4cb RECENT ACTIVITY LOGS")
    print("="*30)

    hours_input = input("Show logs from last how many hours? (default: 24): ").strip()
    try:
        hours = int(hours_input) if hours_input else 24
        hours = max(1, min(hours, 365 * 24))
    except ValueError:
        print("Invalid input, using default of 24 hours.")
        hours = 24

    cutoff_time = datetime.now() - timedelta(hours=hours)
    filters = {
        'date_from': cutoff_time.strftime('%Y-%m-%d'),
        'date_to': datetime.now().strftime('%Y-%m-%d')
    }

    logs = log_manager.db.search_logs(filters, limit=50)

    if not logs:
        print(f"No logs found in the last {hours} hours.")
        return

    print(f"\nShowing {len(logs)} logs from the last {hours} hours:")
    print("-" * 80)

    for log in logs:
        timestamp = log.get('timestamp', '')[:19]
        user = log.get('username', '')
        action = log.get('action', '')
        module = log.get('module', '')
        status = log.get('status', '')

        status_symbol = "\u2705" if status == "success" else "\u274c"
        print(f"{timestamp} | {status_symbol} {user:15} | {action:15} | {module}")

    _ = input("\nPress Enter to continue...")


def search_logs_basic(log_manager, auth):
    """Basic log search"""
    print("\n\U0001f50d SEARCH LOGS")
    print("="*20)

    username = sanitize_input(input("Username (optional): "), max_length=100, allow_newlines=False)
    action = sanitize_input(input("Action (optional): "), max_length=100, allow_newlines=False)
    module = sanitize_input(input("Module (optional): "), max_length=100, allow_newlines=False)

    filters = {}
    if username:
        filters['username'] = username
    if action:
        filters['action'] = action
    if module:
        filters['module'] = module

    # Default to last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    filters['date_from'] = start_date.strftime('%Y-%m-%d')
    filters['date_to'] = end_date.strftime('%Y-%m-%d')

    logs = log_manager.db.search_logs(filters, limit=100)

    if not logs:
        print("No logs found matching your criteria.")
        return

    print(f"\nFound {len(logs)} logs:")
    print("-" * 80)

    for log in logs[:20]:  # Show first 20
        timestamp = log.get('timestamp', '')[:19]
        user = log.get('username', '')
        action = log.get('action', '')
        module = log.get('module', '')
        status = log.get('status', '')

        status_symbol = "\u2705" if status == "success" else "\u274c"
        print(f"{timestamp} | {status_symbol} {user:15} | {action:15} | {module}")

    if len(logs) > 20:
        print(f"... and {len(logs) - 20} more results")

    _ = input("\nPress Enter to continue...")


def generate_basic_report(log_manager, auth):
    """Generate basic activity report"""
    print("\n\U0001f4ca ACTIVITY REPORT")
    print("="*25)

    days_input = input("Generate report for last how many days? (default: 7): ").strip()
    try:
        days = int(days_input) if days_input else 7
        days = max(1, min(days, 365))
    except ValueError:
        print("Invalid input, using default of 7 days.")
        days = 7

    summary = log_manager.analytics.generate_activity_summary(days)

    if "error" in summary:
        print(summary["error"])
        return

    print(f"\nActivity Summary - Last {days} Days")
    print("="*40)
    print(f"Total Activities: {summary['total_activities']:,}")
    print(f"Unique Users: {summary['unique_users']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Failed Activities: {summary['failed_activities']}")

    print("\nTop 5 Most Active Users:")
    for user, count in list(summary['most_active_users'].items())[:5]:
        print(f"  {user}: {count} activities")

    print("\nTop Actions:")
    for action, count in list(summary['activity_by_action'].items())[:5]:
        print(f"  {action}: {count}")

    _ = input("\nPress Enter to continue...")


def basic_config_menu(log_manager, auth):
    """Basic configuration menu"""
    print("\n\u2699\ufe0f BASIC CONFIGURATION")
    print("="*25)

    print("Current Settings:")
    print(f"1. Log Retention: {log_manager.config.get('retention_days')} days")
    print(f"2. Real-time Monitoring: {log_manager.config.get('enable_real_time')}")
    print(f"3. Alerts Enabled: {log_manager.config.get('enable_alerts')}")
    print("4. Return")

    choice = input("\nSelect setting to change (1-4): ").strip()

    if choice not in ('1', '2', '3', '4'):
        print("Invalid choice. Please select 1-4.")
        return

    if choice == '1':
        days_input = input("Enter new retention period (days): ").strip()
        try:
            days = int(days_input)
            days = max(1, min(days, 365))
            log_manager.config.set('retention_days', days)
            print(f"Retention period set to {days} days")
        except ValueError:
            print("Invalid number")
    elif choice == '2':
        enable = input("Enable real-time monitoring? (y/n): ").strip().lower()
        if enable not in ('y', 'n'):
            print("Invalid input. Please enter y or n.")
            return
        log_manager.config.set('enable_real_time', enable == 'y')
        print(f"Real-time monitoring {'enabled' if enable == 'y' else 'disabled'}")
    elif choice == '3':
        enable = input("Enable alerts? (y/n): ").strip().lower()
        if enable not in ('y', 'n'):
            print("Invalid input. Please enter y or n.")
            return
        log_manager.config.set('enable_alerts', enable == 'y')
        print(f"Alerts {'enabled' if enable == 'y' else 'disabled'}")
