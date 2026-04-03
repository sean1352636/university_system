from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import os
import shutil


class BackupMixin:
    def create_backup(self, backup_name=None, description=""):
        """Create a backup of the database"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"

        # Ensure backups directory exists (already created via paths._ensure)
        from education_system.university_system.modules.shared.constants import paths
        os.makedirs(str(paths.BACKUP_DATABASE_DIR), exist_ok=True)

        backup_path = os.path.join(str(paths.BACKUP_DATABASE_DIR), f"{backup_name}.db")

        try:
            # Check if source database exists
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"Database file not found: {self.db_path}")

            # Copy the database file
            shutil.copy2(self.db_path, backup_path)

            # Get file size
            file_size = os.path.getsize(backup_path)

            # Record backup in database
            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO backups (backup_name, backup_path, backup_size, description)
            VALUES (?, ?, ?, ?)
            ''', (backup_name, backup_path, file_size, description))

            conn.commit()
            conn.close()

            print(f"Backup created successfully: {backup_path}")
            return backup_path

        except Exception as e:
            print(f"Error creating backup: {e}")
            return None

    def list_backups(self):
        """List all available backups"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT backup_name, backup_date, backup_size, description
        FROM backups
        ORDER BY backup_date DESC
        ''')

        backups = cursor.fetchall()
        conn.close()

        if not backups:
            print("No backups found.")
            return []

        print("\nAvailable Backups:")
        print("=" * 80)
        print(f"{'Name':<25} {'Date':<20} {'Size (KB)':<12} {'Description':<20}")
        print("-" * 80)

        for backup in backups:
            name, date, size, desc = backup
            backup_date = datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
            size_kb = round(size / 1024, 2) if size else 0
            print(f"{name:<25} {backup_date:<20} {size_kb:<12} {desc:<20}")

        print("=" * 80)
        return backups

    def restore_backup(self, backup_name):
        """Restore from a backup"""
        from education_system.university_system.modules.shared.constants import paths
        backup_path = paths.BACKUP_DATABASE_DIR / f"{backup_name}.db"

        if not backup_path.exists():
            print(f"Backup file not found: {backup_path}")
            return False

        # Confirm restoration
        print(f"WARNING: This will replace the current database with the backup from {backup_name}")
        confirm = input("Are you sure you want to continue? (y/n): ")

        if confirm.lower() != 'y':
            print("Restore canceled.")
            return False

        try:
            # Create a backup of current state before restoring
            self.create_backup("pre_restore_backup", "Automatic backup before restore")

            # Replace current database
            shutil.copy2(backup_path, self.db_path)

            print(f"Database restored from backup: {backup_name}")
            return True

        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False

    def validate_data_consistency(self):
        """Validate data consistency and integrity"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        issues = []

        # Check for orphaned schedules (invalid room_id)
        cursor.execute('''
        SELECT ms.id, ms.module_code, ms.room_id
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE r.id IS NULL
        ''')
        orphaned_rooms = cursor.fetchall()
        if orphaned_rooms:
            issues.append(f"Found {len(orphaned_rooms)} schedules with invalid room references")

        # Check for orphaned schedules (invalid instructor_id)
        cursor.execute('''
        SELECT ms.id, ms.module_code, ms.instructor_id
        FROM module_schedule ms
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        WHERE i.id IS NULL
        ''')
        orphaned_instructors = cursor.fetchall()
        if orphaned_instructors:
            issues.append(f"Found {len(orphaned_instructors)} schedules with invalid instructor references")

        # Check for duplicate schedules
        cursor.execute('''
        SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id, COUNT(*)
        FROM module_schedule
        GROUP BY module_code, day_of_week, start_time, end_time, room_id, instructor_id
        HAVING COUNT(*) > 1
        ''')
        duplicates = cursor.fetchall()
        if duplicates:
            issues.append(f"Found {len(duplicates)} duplicate schedule entries")

        # Check for invalid time formats
        cursor.execute('''
        SELECT id, start_time, end_time
        FROM module_schedule
        WHERE start_time NOT GLOB '[0-9][0-9]:[0-9][0-9]'
           OR end_time NOT GLOB '[0-9][0-9]:[0-9][0-9]'
        ''')
        invalid_times = cursor.fetchall()
        if invalid_times:
            issues.append(f"Found {len(invalid_times)} schedules with invalid time formats")

        conn.close()

        if issues:
            print("\nData Consistency Issues Found:")
            print("=" * 50)
            for i, issue in enumerate(issues, 1):
                print(f"{i}. {issue}")
            print("=" * 50)
        else:
            print("No data consistency issues found.")

        return issues

    def clean_orphaned_records(self):
        """Clean up orphaned records"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Remove schedules with invalid room references
        cursor.execute('''
        DELETE FROM module_schedule
        WHERE room_id NOT IN (SELECT id FROM rooms)
        ''')
        removed_room_refs = cursor.rowcount

        # Remove schedules with invalid instructor references
        cursor.execute('''
        DELETE FROM module_schedule
        WHERE instructor_id NOT IN (SELECT id FROM instructors)
        ''')
        removed_instructor_refs = cursor.rowcount

        conn.commit()
        conn.close()

        print(f"Cleanup completed:")
        print(f"  - Removed {removed_room_refs} schedules with invalid room references")
        print(f"  - Removed {removed_instructor_refs} schedules with invalid instructor references")

    def _log_system_action(self, action, description):
        """Log system actions for audit trail"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO schedule_history (schedule_id, action, new_values, changed_by, change_date)
        VALUES (NULL, ?, ?, 'system', CURRENT_TIMESTAMP)
        ''', (action, description))

        conn.commit()
        conn.close()
