"""Real-time monitoring and alerts CLI functions."""

from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.systems.university.infrastructure.database.db import sqlite3


def real_time_monitor_menu(log_manager, auth):
    """Real-time monitoring menu"""
    print("\n\u23f1\ufe0f  REAL-TIME LOG MONITOR")
    print("="*30)

    if not log_manager.monitor.running:
        start = input("Real-time monitoring is not running. Start it? (y/n): ")
        if start.lower() == 'y':
            log_manager.monitor.start_monitoring()

    print("Real-time monitor is active.")
    print("Monitoring recent log activity...")
    print("Press Ctrl+C to stop monitoring")

    def print_log_update(log_entry):
        """Callback for real-time log updates"""
        timestamp = log_entry.get('timestamp', '')[:19]
        user = log_entry.get('username', '')
        action = log_entry.get('action', '')
        module = log_entry.get('module', '')
        status = log_entry.get('status', '')

        status_symbol = "\u2705" if status == "success" else "\u274c"
        print(f"{timestamp} | {status_symbol} {user} - {action} on {module}")

    # Subscribe to updates
    log_manager.monitor.subscribe(print_log_update)

    try:
        # Show recent activity
        recent_filters = {
            'date_from': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d'),
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }
        recent_logs = log_manager.db.search_logs(recent_filters, limit=10)

        print("\nLast 10 activities:")
        for log in recent_logs:
            print_log_update(log)

        print("\nMonitoring live activity... (Press Enter to stop)")
        input()

    except KeyboardInterrupt:
        pass
    finally:
        log_manager.monitor.unsubscribe(print_log_update)
        print("\nStopped real-time monitoring")


def view_alerts_menu(log_manager, auth):
    """View alerts menu"""
    print("\n\U0001f6a8 SECURITY ALERTS")
    print("="*20)

    # Run alert checks
    print("Running alert checks...")
    alerts = log_manager.alerts.run_alert_checks()

    if not alerts:
        print("No new alerts found.")
    else:
        print(f"Found {len(alerts)} alerts:")

        for i, alert in enumerate(alerts, 1):
            severity_icon = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(alert['severity'], "\u26aa")
            print(f"{i}. {severity_icon} [{alert['type'].upper()}] {alert['message']}")

    # Show recent alerts from database
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM alerts
            WHERE triggered_at > datetime('now', '-24 hours')
            ORDER BY triggered_at DESC
            LIMIT 20
        ''')

        recent_alerts = cursor.fetchall()
    finally:
        conn.close()

    if recent_alerts:
        print("\nRecent alerts (last 24 hours):")
        for alert in recent_alerts:
            severity_icon = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(alert['severity'], "\u26aa")
            resolved_status = "\u2705 Resolved" if alert['resolved'] else "\u274c Active"
            print(f"{severity_icon} {alert['triggered_at'][:19]} - {alert['message']} ({resolved_status})")

    input("\nPress Enter to continue...")
