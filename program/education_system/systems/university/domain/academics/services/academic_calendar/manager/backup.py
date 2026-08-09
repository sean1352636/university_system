"""Extracted AcademicCalendarManager backup methods."""

from ._shared import *  # noqa: F401,F403


class BackupMixin:
    def create_backup(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a backup of the database"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to create backups")

        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(self.config.backup_directory, f"calendar_backup_{timestamp}.db")

            # Ensure backup directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            # Create backup using SQLite's backup method
            self.db_manager.backup_database(backup_path)

            # Verify backup
            if os.path.exists(backup_path):
                file_size = os.path.getsize(backup_path)

                # Record backup in history
                with self.db_manager.transaction():
                    backup_id = str(uuid.uuid4())
                    self.db_manager.execute_update(
                        """INSERT INTO backup_history (id, backup_type, file_path, file_size,
                           backup_time, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (backup_id, "manual", backup_path, file_size,
                         datetime.now().isoformat(), "completed", "Manual backup")
                    )

                logger.info(f"Backup created: {backup_path} ({file_size} bytes)")
                return {
                    'success': True,
                    'message': f'Backup created successfully: {backup_path}',
                    'file_path': backup_path,
                    'file_size': file_size
                }
            else:
                return {'success': False, 'message': 'Backup creation failed'}

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise CalendarError(f"Backup creation failed: {e}")

    def restore_backup(self, backup_path: str) -> Dict[str, Any]:
        """Restore database from backup"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to restore backups")

        if not os.path.exists(backup_path):
            raise ValidationError(f"Backup file not found: {backup_path}")

        try:
            # Create backup of current database
            current_backup = f"{self.config.db_file}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.config.db_file, current_backup)

            # Close current connection
            self.db_manager.close()

            # Restore from backup
            shutil.copy2(backup_path, self.config.db_file)

            # Reconnect to restored database
            self.db_manager = DatabaseManager(self.config.db_file)

            logger.info(f"Database restored from {backup_path}")
            return {
                'success': True,
                'message': f'Database restored from {backup_path}. Previous version saved as {current_backup}'
            }

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise CalendarError(f"Restore failed: {e}")

    def close(self):
        """Clean up resources"""
        if self.db_manager:
            self.db_manager.close()
        if self.auth_manager:
            self.auth_manager.logout()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
