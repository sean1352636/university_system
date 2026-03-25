from education_system.university_system.infrastructure.database.db import sqlite3, ensure_parent_dir
from education_system.university_system.core.sql_safety import validate_table_name
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import shutil
import zipfile


class MaintenanceMixin:
    """Mixin providing backup, cleanup, archiving, and data export."""

    def backup_system_data(self):
        """Create system backup"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(self.submission_dir, 'backups', f'backup_{timestamp}')
            os.makedirs(backup_dir, exist_ok=True)

            print(f"\nCreating backup in: {backup_dir}")

            # Backup database
            db_backup_path = os.path.join(backup_dir, 'database.db')
            shutil.copy2(self.db_path, db_backup_path)
            print("Database backed up")

            # Backup submission files
            submissions_backup = os.path.join(backup_dir, 'submissions')
            if os.path.exists(self.submission_dir):
                shutil.copytree(
                    os.path.join(self.submission_dir, 'submitted'),
                    submissions_backup,
                    ignore=shutil.ignore_patterns('*.tmp', '.DS_Store')
                )
                print("Submission files backed up")

            # Create backup info file
            info = {
                'backup_date': timestamp,
                'database_size': os.path.getsize(db_backup_path),
                'files_count': sum(1 for _ in Path(submissions_backup).rglob('*') if _.is_file()) if os.path.exists(submissions_backup) else 0,
                'backup_type': 'full'
            }

            with open(os.path.join(backup_dir, 'backup_info.json'), 'w') as f:
                json.dump(info, f, indent=2)

            # Log backup
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                total_size = sum(f.stat().st_size for f in Path(backup_dir).rglob('*') if f.is_file())

                cursor.execute('''
                INSERT INTO backup_history (backup_type, file_path, size_bytes, created_at)
                VALUES (?, ?, ?, ?)
                ''', ('full', backup_dir, total_size, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
            finally:
                conn.close()

            print(f"Backup completed successfully!")
            print(f"Backup size: {total_size / (1024*1024):.1f} MB")

        except Exception as e:
            print(f"Error creating backup: {e}")

    def run_due_date_reminders(self):
        """Send due date reminders (should be run as scheduled task)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            day_after = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            SELECT a.id, a.title, a.due_date, a.module_code
            FROM assignments a
            WHERE a.due_date BETWEEN ? AND ? AND a.is_active = 1
            ''', (tomorrow, day_after))

            upcoming_assignments = cursor.fetchall()

            for assignment in upcoming_assignments:
                aid, title, due_date, module_code = assignment

                cursor.execute('''
                SELECT u.id FROM users u
                JOIN students s ON u.student_id = s.student_id
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ''', (module_code,))

                students = cursor.fetchall()

                for (user_id,) in students:
                    cursor.execute('''
                    SELECT COUNT(*) FROM assignment_submissions
                    WHERE assignment_id = ? AND student_id = (
                        SELECT student_id FROM users WHERE id = ?
                    ) AND status = 'submitted'
                    ''', (aid, user_id))

                    if cursor.fetchone()[0] == 0:
                        self._send_notification(
                            user_id,
                            "Assignment Due Reminder",
                            f"Reminder: '{title}' is due on {due_date}",
                            "due_reminder",
                            aid
                        )

            conn.close()
            print(f"Sent reminders for {len(upcoming_assignments)} assignments.")

        except Exception as e:
            print(f"Error sending reminders: {e}")

    def cleanup_old_data(self):
        """Clean up old data (run periodically)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Clean old notifications (older than 30 days)
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('DELETE FROM notifications WHERE created_at < ? AND is_read = 1', (cutoff_date,))
            deleted_notifications = cursor.rowcount

            # Clean old analytics cache (older than 7 days)
            cache_cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM analytics_cache WHERE expires_at < ?', (cache_cutoff,))
            deleted_cache = cursor.rowcount

            # Clean old audit logs (older than 1 year)
            audit_cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM audit_log WHERE timestamp < ?', (audit_cutoff,))
            deleted_audit = cursor.rowcount

            conn.commit()
            conn.close()

            print(f"Cleanup completed:")
            print(f"- Deleted {deleted_notifications} old notifications")
            print(f"- Deleted {deleted_cache} old cache entries")
            print(f"- Deleted {deleted_audit} old audit logs")

        except Exception as e:
            print(f"Error during cleanup: {e}")

    def archive_submissions(self, assignment_id, archive_path=None):
        """Archive all submissions for an assignment"""
        try:
            if not archive_path:
                archive_path = os.path.join(self.submission_dir, 'backups', f'archive_{assignment_id}_{datetime.now().strftime("%Y%m%d")}.zip')

            ensure_parent_dir(archive_path)

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT file_path, student_id, file_name
                    FROM assignment_submissions
                    WHERE assignment_id = ?
                ''', (assignment_id,))

                submissions = cursor.fetchall()
            finally:
                conn.close()

            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, student_id, file_name in submissions:
                    if os.path.exists(file_path):
                        arcname = f"{student_id}/{file_name}"
                        zipf.write(file_path, arcname)

            print(f"Submissions archived to: {archive_path}")
            return archive_path

        except Exception as e:
            print(f"Error archiving submissions: {e}")
            return None

    def export_system_data(self, export_path=None):
        """Export all system data to JSON"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'system_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

            ensure_parent_dir(export_path)

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                export_data = {}

                tables = ['assignments', 'assignment_submissions', 'assignment_groups',
                         'rubrics', 'assignment_templates', 'extension_requests',
                         'peer_review_assignments', 'notifications', 'messages']

                for table in tables:
                    safe_table = validate_table_name(table)
                    cursor.execute('SELECT * FROM [' + safe_table + ']')
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    export_data[table] = [dict(zip(columns, row)) for row in rows]

            finally:
                conn.close()

            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            print(f"System data exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting system data: {e}")
            return None
