import logging
import shutil

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
            backup_dir = str(paths.UNIVERSITY_BACKUP_FILES_DIR)
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"document_manager_backup_{timestamp}.zip"
            backup_path = os.path.join(backup_dir, backup_filename)

            # The guard here tested for the pre-consolidation name `DB_PATH`,
            # which stopped existing when paths gained per-system prefixes. It
            # was therefore always False, and every "full system backup"
            # silently archived a relative 'university_system.db' that is not
            # the live database — i.e. backed up no data at all.
            db_path = str(paths.UNIVERSITY_DEFAULT_DB_PATH)

            # Members are stored relative to VAR_DIR so restore_from_backup can
            # put each file back where it came from. Passing an absolute path to
            # write() with no arcname stores it minus its leading separator —
            # a member like `home/<user>/.../var/data/...` that only extracting
            # at `/` would restore correctly.
            var_root = str(paths.VAR_DIR)
            db_arcname = os.path.basename(db_path)
            try:
                if os.path.commonpath([os.path.abspath(db_path), var_root]) == var_root:
                    db_arcname = os.path.relpath(db_path, var_root)
            except ValueError:
                # Different drives (Windows): fall back to the bare filename.
                pass

            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                # Backup database
                if os.path.exists(db_path):
                    backup_zip.write(db_path, arcname=db_arcname)

                # Backup settings
                # NOTE: this relative path resolves against the process working
                # directory, so which settings.json is archived depends on where
                # the app was launched from. Left as-is — the intended location
                # is a separate decision — but it restores to VAR_DIR.
                settings_path = 'settings.json'
                if os.path.exists(settings_path):
                    backup_zip.write(settings_path, arcname=os.path.basename(settings_path))

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
            backup_dir = str(paths.UNIVERSITY_BACKUP_FILES_DIR)

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

            # Restore beneath the runtime state tree via safe_extract, never
            # extractall(): a backup archive is untrusted input (it may have
            # been swapped on disk) and extractall would honour "../" members
            # and symlink members, writing anywhere the process can reach.
            from education_system.platform.kernel.core.safe_paths import (
                PathSecurityError,
                safe_extract,
            )

            # Members are written relative to VAR_DIR, so that is the restore
            # root. This read `getattr(paths, 'PROJECT_ROOT', os.getcwd())` —
            # but paths has never defined PROJECT_ROOT (the alias is
            # PROGRAM_ROOT), so the default always won and restores unpacked
            # into whatever directory the process happened to start in.
            #
            # safe_extract opens every member O_EXCL and so cannot overwrite a
            # live database — extracting straight onto VAR_DIR would fail on the
            # first existing file. Unpack into an empty staging directory, keep
            # a copy of whatever is about to be replaced, then move into place.
            var_root = str(paths.VAR_DIR)
            staging = os.path.join(
                var_root, '.restore-staging',
                datetime.now().strftime('%Y%m%d_%H%M%S'),
            )
            try:
                with zipfile.ZipFile(selected_backup, 'r') as backup_zip:
                    extracted = safe_extract(backup_zip, staging)
            except PathSecurityError as e:
                logger.error("Refused unsafe backup archive %s: %s", selected_backup, e)
                print(f"❌ Restore refused — the backup archive is unsafe: {e}")
                shutil.rmtree(staging, ignore_errors=True)
                return

            try:
                replaced_dir = paths.maintenance_backup_dir(
                    'document-manager-restore', create=True,
                )
                for extracted_path in extracted:
                    relative = os.path.relpath(str(extracted_path), staging)
                    destination = os.path.join(var_root, relative)
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    if os.path.exists(destination):
                        keep = os.path.join(str(replaced_dir), relative)
                        os.makedirs(os.path.dirname(keep), exist_ok=True)
                        shutil.copy2(destination, keep)
                    shutil.move(str(extracted_path), destination)
                    logger.info("Restored %s from %s", destination, selected_backup)
            finally:
                shutil.rmtree(staging, ignore_errors=True)

            print(f"   Replaced files copied to {replaced_dir}")
            print("✅ System restored successfully!")
            print("⚠️  Please restart the application.")

        except Exception as e:
            print(f"Restore error: {e}")

    def view_backup_history(self):
        """View history of backups"""
        try:
            backup_dir = str(paths.UNIVERSITY_BACKUP_FILES_DIR)

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
