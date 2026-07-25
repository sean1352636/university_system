import logging

from education_system.systems.university.infrastructure.utils.document_manager._common import (
    os, zipfile, datetime, sqlite3,
    get_connection, _t, paths,
)

logger = logging.getLogger(__name__)


class BackupMixin:
    def backup_system(self):
        """System backup functionality"""
        print("\n💾 BACKUP SYSTEM")
        print("1. Create Full Backup")
        print("2. Restore from Backup")
        print("3. View Backup History")
        print("4. Schedule Automatic Backup")
        print("5. Return to Main Menu")

        choice = input("\nChoose option (1-5): ").strip()

        if choice == '1':
            self.create_full_backup()
        elif choice == '2':
            self.restore_from_backup()
        elif choice == '3':
            self.view_backup_history()
        elif choice == '4':
            self.schedule_automatic_backup()

    def create_full_backup(self):
        """Create a full system backup"""
        try:
            backup_dir = str(paths.BACKUP_FILES_DIR)
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"document_manager_backup_{timestamp}.zip"
            backup_path = os.path.join(backup_dir, backup_filename)

            db_path = str(paths.DB_PATH) if hasattr(paths, 'DB_PATH') else 'university_system.db'

            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                # Backup database
                if os.path.exists(db_path):
                    backup_zip.write(db_path)

                # Backup settings
                settings_path = 'settings.json'
                if os.path.exists(settings_path):
                    backup_zip.write(settings_path)

            backup_size = os.path.getsize(backup_path) / (1024 * 1024)

            # Log the backup in audit trail
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO audit_log (user_id, action, table_name, record_id, new_values, timestamp)
                VALUES (?, 'BACKUP_CREATED', 'system', ?, ?, ?)
                ''', (self.current_user, backup_filename,
                      f"Size: {backup_size:.2f} MB",
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                conn.close()
            except Exception:
                logger.warning(
                    "Failed to write BACKUP_CREATED audit_log entry for %s",
                    backup_filename, exc_info=True)

            print("\n✅ Backup created successfully!")
            print(f"File: {backup_path}")
            print(f"Size: {backup_size:.2f} MB")

        except Exception as e:
            print(f"Backup error: {e}")

    def restore_from_backup(self):
        """Restore system from a backup file"""
        try:
            backup_dir = str(paths.BACKUP_FILES_DIR)

            if not os.path.exists(backup_dir):
                print("No backup directory found.")
                return

            # List available backups
            backups = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]

            if not backups:
                print("No backup files found.")
                return

            print("\n🔄 RESTORE FROM BACKUP")
            print("\nAvailable Backups:")

            backups.sort(reverse=True)

            for i, backup in enumerate(backups):
                backup_path = os.path.join(backup_dir, backup)
                size = os.path.getsize(backup_path) / (1024 * 1024)
                mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
                print(f"{i+1}. {backup} ({size:.2f} MB) - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                choice = int(input("\nSelect backup to restore: ")) - 1
                if 0 <= choice < len(backups):
                    selected_backup = os.path.join(backup_dir, backups[choice])
                else:
                    print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                    return
            except ValueError:
                print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
                return

            print("\n⚠️  WARNING: This will replace your current database!")
            confirm = input("Are you sure you want to restore? Type 'YES' to confirm: ").strip()

            if confirm != 'YES':
                print("Restore cancelled.")
                return

            print(f"\nRestoring from {backups[choice]}...")

            with zipfile.ZipFile(selected_backup, 'r') as backup_zip:
                backup_zip.extractall('.')

            print("✅ System restored successfully!")
            print("⚠️  Please restart the application.")

        except Exception as e:
            print(f"Restore error: {e}")

    def view_backup_history(self):
        """View history of backups"""
        try:
            backup_dir = str(paths.BACKUP_FILES_DIR)

            if not os.path.exists(backup_dir):
                print("No backup directory found.")
                return

            backups = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]

            if not backups:
                print("No backup files found.")
                return

            print("\n💾 BACKUP HISTORY")
            print("=" * 80)

            backups.sort(reverse=True)

            total_size = 0

            for backup in backups:
                backup_path = os.path.join(backup_dir, backup)
                size = os.path.getsize(backup_path) / (1024 * 1024)
                total_size += size
                mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))

                print(f"\nFile: {backup}")
                print(f"Size: {size:.2f} MB")
                print(f"Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

            print(f"\n{'='*80}")
            print(f"Total Backups: {len(backups)}")
            print(f"Total Size: {total_size:.2f} MB")

            # Check audit log for backup records
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT record_id, new_values, timestamp
            FROM audit_log
            WHERE action = 'BACKUP_CREATED'
            ORDER BY timestamp DESC
            LIMIT 10
            ''')

            log_entries = cursor.fetchall()

            if log_entries:
                print("\n📋 Recent Backup Log Entries:")
                for filename, details, timestamp in log_entries:
                    print(f"  {timestamp}: {filename}")

            conn.close()

        except Exception as e:
            print(f"Error viewing backup history: {e}")

    def schedule_automatic_backup(self):
        """Schedule automatic backups"""
        print("\n⏰ SCHEDULE AUTOMATIC BACKUP")

        print("\nAutomatic backup scheduling requires:")
        print("1. System cron job (Linux/Mac)")
        print("2. Task Scheduler (Windows)")
        print("3. Or a background service")

        print("\nTo enable automatic backups:")
        print("1. Set auto_backup_enabled to 'true' in backup settings")
        print("2. Configure your system's task scheduler")
        print("3. Run this script with '--backup' flag")

        enable = input("\nEnable automatic backup flag in settings? (y/n): ").strip().lower()

        if enable == 'y':
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE system_settings
                SET setting_value = 'true', updated_date = ?
                WHERE setting_name = 'auto_backup_enabled'
                ''', (datetime.now().strftime('%Y-%m-%d'),))

                conn.commit()
                conn.close()

                print("✅ Automatic backup enabled in settings.")
                print("\nNext steps:")
                print("- Configure your system scheduler to run regular backups")
                print("- Command: python document_manager --backup")

            except sqlite3.Error as e:
                print(f"Database error: {e}")
