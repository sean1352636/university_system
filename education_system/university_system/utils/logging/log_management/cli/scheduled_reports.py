"""Scheduled reports CLI functions."""


def scheduled_reports_menu(log_manager, auth):
    """Scheduled reports menu"""
    print("\n\U0001f4c5 SCHEDULED REPORTS")
    print("="*25)

    print("1. Setup Daily Summary Email")
    print("2. Setup Weekly Analytics Report")
    print("3. Setup Security Alert Notifications")
    print("4. View Scheduled Tasks")
    print("5. Return")

    choice = input("Choose option: ")

    if choice == '1':
        setup_daily_email_report(log_manager, auth)
    elif choice == '2':
        setup_weekly_report(log_manager, auth)
    elif choice == '3':
        setup_security_alerts(log_manager, auth)
    elif choice == '4':
        view_scheduled_tasks(log_manager)


def setup_daily_email_report(log_manager, auth):
    """Setup daily email reports"""
    print("\n\U0001f4e7 SETUP DAILY EMAIL REPORT")
    print("="*35)

    email = input("Email address for reports: ")
    if not email:
        print("Email address is required")
        return

    log_manager.config.set('alert_email', email)

    smtp_server = input("SMTP server (e.g., smtp.gmail.com): ")
    smtp_port = input("SMTP port (default: 587): ")
    smtp_username = input("SMTP username: ")
    smtp_password = input("SMTP password: ")

    log_manager.config.set('smtp_server', smtp_server)
    log_manager.config.set('smtp_port', int(smtp_port) if smtp_port else 587)
    log_manager.config.set('smtp_username', smtp_username)
    log_manager.config.set('smtp_password', smtp_password)

    print("Daily email reports configured!")
    print("Reports will be sent at 08:00 daily")


def setup_weekly_report(log_manager, auth):
    """Setup weekly analytics report"""
    print("\n\U0001f4ca SETUP WEEKLY ANALYTICS REPORT")
    print("="*38)

    email = input("Email address for weekly reports: ")
    if not email:
        print("Email address is required")
        return

    log_manager.config.set('weekly_report_email', email)

    day = input("Day of week for reports (Monday=1, Sunday=7, default=1): ")
    try:
        day = int(day) if day else 1
        if not 1 <= day <= 7:
            day = 1
    except ValueError:
        day = 1

    log_manager.config.set('weekly_report_day', day)

    print(f"Weekly analytics reports configured!")
    print(f"Reports will be sent every {'Monday Tuesday Wednesday Thursday Friday Saturday Sunday'.split()[day-1]}")


def setup_security_alerts(log_manager, auth):
    """Setup security alert notifications"""
    print("\n\U0001f6a8 SETUP SECURITY ALERTS")
    print("="*28)

    email = input("Email address for security alerts: ")
    if not email:
        print("Email address is required")
        return

    log_manager.config.set('security_alert_email', email)

    print("Alert thresholds:")

    failed_login_threshold = input("Failed login threshold (default: 5): ")
    try:
        threshold = int(failed_login_threshold) if failed_login_threshold else 5
    except ValueError:
        threshold = 5

    log_manager.config.set('failed_login_threshold', threshold)

    print(f"Security alerts configured!")
    print(f"Alerts will be sent for {threshold}+ failed logins")


def view_scheduled_tasks(log_manager):
    """View configured scheduled tasks"""
    print("\n\U0001f4cb SCHEDULED TASKS")
    print("="*20)

    print("Current scheduled tasks:")
    print("- Daily log archival at 02:00")
    print("- Daily log cleanup at 03:00")
    print("- Hourly alert checks")

    if log_manager.config.get('alert_email'):
        print(f"- Daily email reports to: {log_manager.config.get('alert_email')}")

    if log_manager.config.get('weekly_report_email'):
        day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_index = log_manager.config.get('weekly_report_day', 1) - 1
        print(f"- Weekly analytics reports to: {log_manager.config.get('weekly_report_email')} ({day_name[day_index]})")

    if log_manager.config.get('security_alert_email'):
        threshold = log_manager.config.get('failed_login_threshold', 5)
        print(f"- Security alerts to: {log_manager.config.get('security_alert_email')} (threshold: {threshold})")

    input("\nPress Enter to continue...")
