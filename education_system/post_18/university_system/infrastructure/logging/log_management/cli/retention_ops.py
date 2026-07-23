"""Retention, integrity check, and anonymization CLI functions."""

from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.logging.log_management.security import LogSecurity


def retention_settings_menu(log_manager, auth):
    """Data retention settings menu"""
    print("\n\U0001f5c4\ufe0f DATA RETENTION SETTINGS")
    print("="*30)

    current_retention = log_manager.config.get('retention_days', 90)
    current_archive = log_manager.config.get('auto_archive_days', 30)

    print("Current Settings:")
    print(f"Log Retention: {current_retention} days")
    print(f"Auto Archive: {current_archive} days")

    print("\n1. Change retention period")
    print("2. Change archive period")
    print("3. Manual archive")
    print("4. Manual cleanup")
    print("5. Return")

    choice = input("Choose option: ")

    if choice == '1':
        new_retention = input(f"Enter new retention period in days (current: {current_retention}): ")
        try:
            days = int(new_retention)
            log_manager.config.set('retention_days', days)
            print(f"Retention period updated to {days} days")
        except ValueError:
            print("Invalid number")

    elif choice == '2':
        new_archive = input(f"Enter new archive period in days (current: {current_archive}): ")
        try:
            days = int(new_archive)
            log_manager.config.set('auto_archive_days', days)
            print(f"Archive period updated to {days} days")
        except ValueError:
            print("Invalid number")

    elif choice == '3':
        confirm = input("Archive old logs now? This may take some time (y/n): ")
        if confirm.lower() == 'y':
            log_manager.retention.archive_old_logs()

    elif choice == '4':
        confirm = input("\u26a0\ufe0f Delete old logs permanently? This cannot be undone! (y/n): ")
        if confirm.lower() == 'y':
            confirm2 = input("Type 'DELETE' to confirm: ")
            if confirm2 == 'DELETE':
                log_manager.retention.cleanup_old_logs()
            else:
                print("Cleanup cancelled")


def integrity_check_menu(log_manager, auth):
    """Log integrity check menu"""
    print("\n\U0001f50d LOG INTEGRITY CHECK")
    print("="*25)

    print("Checking log integrity...")

    # Sample check of recent logs
    filters = {
        'date_from': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    }

    recent_logs = log_manager.db.search_logs(filters, limit=1000)

    if not recent_logs:
        print("No recent logs to check.")
        return

    corrupted_count = 0
    checked_count = 0

    for log in recent_logs:
        if log.get('hash'):
            # Verify hash
            log_data = {k: v for k, v in log.items() if k != 'hash'}
            calculated_hash = LogSecurity.generate_hash(log_data)

            if calculated_hash != log['hash']:
                corrupted_count += 1

            checked_count += 1

    print("Integrity check completed:")
    print(f"Logs checked: {checked_count}")
    print(f"Corrupted logs: {corrupted_count}")

    if corrupted_count > 0:
        print("\u26a0\ufe0f Warning: Some logs may have been tampered with!")
    else:
        print("\u2705 All checked logs passed integrity verification")

    input("\nPress Enter to continue...")


def anonymize_data_menu(log_manager, auth):
    """Data anonymization menu"""
    print("\n\U0001f512 DATA ANONYMIZATION")
    print("="*25)

    print("\u26a0\ufe0f Warning: This will anonymize user data in logs.")
    print("This operation cannot be reversed!")

    confirm = input("Continue? (y/n): ")
    if confirm.lower() != 'y':
        return

    # Get date range for anonymization
    days = input("Anonymize logs older than how many days? (default: 90): ")
    try:
        days = int(days) if days else 90
    except ValueError:
        days = 90

    cutoff_date = datetime.now() - timedelta(days=days)

    print(f"Anonymizing logs older than {cutoff_date.strftime('%Y-%m-%d')}...")

    # This is a simplified example - in production, implement proper anonymization
    filters = {
        'date_to': cutoff_date.strftime('%Y-%m-%d')
    }

    old_logs = log_manager.db.search_logs(filters, limit=10000)

    if not old_logs:
        print("No logs found for anonymization.")
        return

    anonymized_count = 0

    # In a real implementation, you would update the database
    # For demo purposes, we'll just show what would be anonymized
    for log in old_logs[:10]:  # Show first 10 as examples
        anonymized_log = LogSecurity.anonymize_data(log)
        print(f"Original: {log['username']} -> Anonymized: {anonymized_log['username']}")
        anonymized_count += 1

    print(f"\nWould anonymize {len(old_logs)} log entries")
    print("(This is a demonstration - actual anonymization not performed)")

    input("\nPress Enter to continue...")
