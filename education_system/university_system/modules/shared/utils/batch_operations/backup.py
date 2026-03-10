import os
import json
import shutil
import datetime
from pathlib import Path

from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = configure_logging(name=__name__)


class BackupMixin:
    """Mixin providing database backup and undo operations."""

    def create_database_backup(self, auto: bool = False) -> str:
        """Create database backup with timestamp"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"student_records_backup_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        try:
            # Copy database file
            shutil.copy2(self.db_path, backup_path)

            if not auto:
                print(_t("shared.utils.batch_operations.backup_created", path=backup_path))

            # Keep only last 10 backups
            self.cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            if not auto:
                print(_t("shared.utils.batch_operations.error_creating_backup", error=str(e)))
            return ""

    def cleanup_old_backups(self, keep_count: int = 10):
        """Clean up old backup files, keeping only the most recent"""
        try:
            backup_files = list(Path(self.backup_dir).glob('student_records_backup_*.db'))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Remove old backups
            for old_backup in backup_files[keep_count:]:
                old_backup.unlink()
                logger.info(f"Removed old backup: {old_backup}")

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def undo_last_import(self):
        """Rollback the last import operation"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        print("\n" + _t("shared.utils.batch_operations.title_undo_import"))

        if not self.import_history:
            try:
                with open('import_history.json', 'r') as f:
                    self.import_history = json.load(f)
            except FileNotFoundError:
                print(_t("shared.utils.batch_operations.no_import_history"))
                return

        if not self.import_history:
            print(_t("shared.utils.batch_operations.no_imports_to_undo"))
            return

        last_import = self.import_history[-1]

        print(_t("shared.utils.batch_operations.last_import_operation"))
        print(f"{_t('shared.utils.batch_operations.date')}: {last_import['timestamp']}")
        print(f"{_t('shared.utils.batch_operations.operation')}: {last_import['operation_type']}")
        print(f"{_t('shared.utils.batch_operations.records_imported')}: {last_import['successful_imports']}")
        print(f"{_t('shared.utils.batch_operations.file')}: {last_import['file_path']}")

        confirm = input("\n" + _t("shared.utils.batch_operations.confirm_undo"))
        if confirm.lower() != 'y':
            print(_t("shared.utils.batch_operations.undo_cancelled"))
            return

        # Find records imported in last operation
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get records from around the time of last import
            import_time = datetime.datetime.fromisoformat(last_import['timestamp'])
            time_window_start = (import_time - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
            time_window_end = (import_time + datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            SELECT student_id FROM students
            WHERE registration_datetime BETWEEN ? AND ?
            ORDER BY registration_datetime DESC
            LIMIT ?
            ''', (time_window_start, time_window_end, last_import['successful_imports']))

            student_ids_to_delete = [row[0] for row in cursor.fetchall()]

            if not student_ids_to_delete:
                print(_t("shared.utils.batch_operations.no_records_to_undo"))
                return

            print(_t("shared.utils.batch_operations.found_records_to_delete", count=len(student_ids_to_delete)))

            final_confirm = input(_t("shared.utils.batch_operations.prompt_proceed_deletion"))
            if final_confirm.lower() == 'y':
                # Student deletion has been centralized - show error
                print("\n" + _t("shared.utils.batch_operations.undo_disabled"))
                print(_t("shared.utils.batch_operations.deletion_centralized"))
                print("\n" + _t("shared.utils.batch_operations.use_main_gui"))
                print(_t("shared.utils.batch_operations.bullet_delete_students"))
                print("\n" + _t("shared.utils.batch_operations.ensures_consistency"))
                return

                # Update import history
                last_import['undone'] = True
                last_import['undo_timestamp'] = datetime.datetime.now().isoformat()

                with open('import_history.json', 'w') as f:
                    json.dump(self.import_history, f, indent=2)

        except sqlite3.Error as e:
            conn.rollback()
            print(_t("shared.utils.batch_operations.database_error_undo", error=str(e)))
        finally:
            conn.close()
