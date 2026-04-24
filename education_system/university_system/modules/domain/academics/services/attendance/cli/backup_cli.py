"""CLI handler for backup and recovery operations."""

import datetime
from pathlib import Path
from education_system.university_system.modules.domain.academics.services.attendance.settings import (
    get_enhanced_setting, set_enhanced_setting,
)


def handle_backup_recovery(backup_system):
    """Handle backup and recovery operations"""
    print("\n💾 BACKUP & RECOVERY SYSTEM")
    print("1. Create Manual Backup")
    print("2. List Available Backups")
    print("3. Restore from Backup")
    print("4. Backup Settings")
    print("5. Cleanup Old Backups")

    choice = input("Enter your choice (1-5): ")

    if choice == '1':
        backup_type = input("Enter backup type (full/partial): ") or "manual"
        backup_path = backup_system.create_backup(backup_type)

        if backup_path:
            print(f"✅ Backup created: {backup_path}")
        else:
            print("❌ Backup creation failed.")

    elif choice == '2':
        # Use centralized backup directory
        from education_system.university_system.modules.shared.constants.paths import BACKUP_ATTENDANCE_DIR
        backup_dir = BACKUP_ATTENDANCE_DIR

        if backup_dir.exists():
            backups = sorted(backup_dir.glob("*.db"), key=lambda x: x.stat().st_mtime, reverse=True)

            if backups:
                print("\n📁 AVAILABLE BACKUPS:")
                print(f"{'Filename':<40} {'Size':<10} {'Date'}")
                print("-" * 70)

                for backup_file in backups[:20]:  # Show last 20 backups
                    size = backup_file.stat().st_size
                    size_mb = size / (1024 * 1024)
                    date = datetime.datetime.fromtimestamp(backup_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')

                    print(f"{backup_file.name:<40} {size_mb:<10.1f}MB {date}")
            else:
                print("No backups found.")
        else:
            print("Backup directory not found.")

    elif choice == '3':
        backup_path = input("Enter backup file path: ")

        confirm = input(f"⚠️  This will restore from '{backup_path}' and overwrite current data. Continue? (yes/no): ")

        if confirm.lower() == 'yes':
            success, message = backup_system.restore_backup(backup_path)

            if success:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
        else:
            print("Restore cancelled.")

    elif choice == '4':
        print("\n💾 BACKUP SETTINGS:")

        auto_backup = get_enhanced_setting('auto_backup_enabled', True, 'boolean')
        frequency = get_enhanced_setting('backup_frequency_hours', 24, 'integer')

        print(f"Automatic Backups: {'Enabled' if auto_backup else 'Disabled'}")
        print(f"Backup Frequency: Every {frequency} hours")

        print("\n1. Toggle Automatic Backups")
        print("2. Change Backup Frequency")

        setting_choice = input("Enter choice (1-2): ")

        if setting_choice == '1':
            new_value = not auto_backup
            if set_enhanced_setting('auto_backup_enabled', new_value, data_type='boolean'):
                status = "enabled" if new_value else "disabled"
                print(f"✅ Automatic backups {status}!")
            else:
                print("❌ Failed to update setting.")

        elif setting_choice == '2':
            try:
                new_frequency = int(input("Enter new frequency in hours: "))
                if set_enhanced_setting('backup_frequency_hours', new_frequency, data_type='integer'):
                    print(f"✅ Backup frequency set to {new_frequency} hours!")
                else:
                    print("❌ Failed to update setting.")
            except ValueError:
                print("Invalid frequency value.")

    elif choice == '5':
        try:
            keep_days = int(input("Enter number of days to keep backups (default 30): ") or 30)
            backup_system.cleanup_old_backups(keep_days)
            print(f"✅ Cleaned up backups older than {keep_days} days.")
        except ValueError:
            print("Invalid number of days.")
