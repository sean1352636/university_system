"""Backup and restore mixin."""

from education_system.post_18.university_system.modules.shared.gui.batch_operations.constants import (
    datetime, shutil, logging,
    DATA_DIR, BACKUP_DIR,
    logger,
)


class BackupRestoreMixin:
    """Mixin providing database backup, restore, and undo methods."""

    def create_database_backup(self, auto: bool = False,
                               progress_callback=None) -> str:
        """Create database backup file - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Creating database backup...")

            # Create backups directory
            backup_dir = BACKUP_DIR
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_type = 'auto' if auto else 'manual'
            backup_filename = f'student_records_backup_{backup_type}_{timestamp}.db'
            backup_path = backup_dir / backup_filename

            if progress_callback:
                progress_callback(30, "Copying database file...")

            # Copy database file
            db_path = self.db_manager.db_path
            shutil.copy2(db_path, backup_path)

            if progress_callback:
                progress_callback(80, "Verifying backup...")

            # Verify backup
            if not backup_path.exists():
                raise FileNotFoundError("Backup file was not created")

            if progress_callback:
                progress_callback(100, f"Backup created: {backup_path}")

            logger.info(f"Created {'automatic' if auto else 'manual'} backup: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            raise

    def cleanup_old_backups(self, keep_count: int = 10,
                           progress_callback=None) -> int:
        """Remove old backup files - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Cleaning up old backups (keeping {keep_count})...")

            backup_dir = BACKUP_DIR
            if not backup_dir.exists():
                return 0

            # Get all backup files sorted by modification time
            backups = sorted(
                backup_dir.glob('student_records_backup_*.db'),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            if len(backups) <= keep_count:
                if progress_callback:
                    progress_callback(100, "No old backups to clean up")
                return 0

            # Delete old backups
            backups_to_delete = backups[keep_count:]
            deleted_count = 0

            for i, backup in enumerate(backups_to_delete):
                try:
                    backup.unlink()
                    deleted_count += 1

                    if progress_callback:
                        progress = int((i / len(backups_to_delete)) * 100)
                        progress_callback(progress, f"Deleting: {i+1}/{len(backups_to_delete)}")

                except Exception as e:
                    logger.warning(f"Failed to delete backup {backup}: {e}")

            if progress_callback:
                progress_callback(100, f"Deleted {deleted_count} old backups")

            logger.info(f"Cleaned up {deleted_count} old backups, kept {keep_count} most recent")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            raise

    def undo_last_import(self, progress_callback=None) -> bool:
        """Undo the last import operation - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Looking for automatic backup...")

            backup_dir = BACKUP_DIR
            if not backup_dir.exists():
                raise FileNotFoundError("No backups directory found")

            # Find most recent auto backup
            auto_backups = sorted(
                backup_dir.glob('student_records_backup_auto_*.db'),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            if not auto_backups:
                raise FileNotFoundError("No automatic backups found")

            latest_backup = auto_backups[0]

            if progress_callback:
                progress_callback(25, f"Found backup: {latest_backup.name}")

            # Create a safety backup of current state
            safety_backup = self.create_database_backup(auto=False, progress_callback=None)

            if progress_callback:
                progress_callback(50, "Restoring from backup...")

            # Close current database connection
            self.db_manager.close()

            # Restore from backup
            db_path = self.db_manager.db_path
            shutil.copy2(latest_backup, db_path)

            if progress_callback:
                progress_callback(90, "Verifying restoration...")

            # Verify restoration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM students")
                count = cursor.fetchone()[0]

            if progress_callback:
                progress_callback(100, f"Undo complete - {count} students in database")

            logger.info(f"Successfully undone last import, restored from {latest_backup}")
            logger.info(f"Safety backup created at {safety_backup}")
            return True

        except Exception as e:
            logger.error(f"Error undoing last import: {e}")
            raise
