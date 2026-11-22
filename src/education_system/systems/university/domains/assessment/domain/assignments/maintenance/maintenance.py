from education_system.systems.university.infrastructure.database.db import sqlite3, ensure_parent_dir
from education_system.systems.university.infrastructure.sql_safety import validate_table_name
from education_system.paths import (
    UNIVERSITY_BACKUP_SUBMISSIONS_DIR,
    UNIVERSITY_DATABASE_BACKUP_FILENAME,
)
from education_system.systems.university.domains.assessment.domain.assignments.core.constants import (
    SUBDIR_EXPORTS, SUBDIR_SUBMITTED,
)
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
            # Submission backups now live under the project-wide backups
            # tree (matching BACKUP_DATABASE_DIR / BACKUP_ATTENDANCE_DIR /
            # ... etc.) rather than nested inside the submissions data
            # tree. See core/paths.py BACKUP_SUBMISSIONS_DIR.
            backup_dir = os.path.join(str(UNIVERSITY_BACKUP_SUBMISSIONS_DIR), f'backup_{timestamp}')
            os.makedirs(backup_dir, exist_ok=True)

            print(f"\nCreating backup in: {backup_dir}")

            # Backup database
            db_backup_path = os.path.join(backup_dir, UNIVERSITY_DATABASE_BACKUP_FILENAME)
            shutil.copy2(self.db_path, db_backup_path)
            print("Database backed up")

            # Backup submission files
            submissions_backup = os.path.join(backup_dir, 'submissions')
            if os.path.exists(self.submission_dir):
                shutil.copytree(
                    os.path.join(self.submission_dir, SUBDIR_SUBMITTED),
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

            print("Backup completed successfully!")
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
            return len(upcoming_assignments)

        except Exception as e:
            print(f"Error sending reminders: {e}")

    def cleanup_old_data(self):
        """Clean up old data (run periodically)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Clean old notifications (older than 30 days)
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

            from education_system.systems.university.domains.assessment.domain.assignments.notifications import inbox
            deleted_notifications = inbox.purge_deleted(conn, cutoff_date)

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

            print("Cleanup completed:")
            print(f"- Deleted {deleted_notifications} old notifications")
            print(f"- Deleted {deleted_cache} old cache entries")
            print(f"- Deleted {deleted_audit} old audit logs")

        except Exception as e:
            print(f"Error during cleanup: {e}")

    def archive_submissions(self, assignment_id, archive_path=None):
        """Archive all submissions for an assignment"""
        try:
            if not archive_path:
                archive_path = os.path.join(
                    str(UNIVERSITY_BACKUP_SUBMISSIONS_DIR),
                    f'archive_{assignment_id}_{datetime.now().strftime("%Y%m%d")}.zip')

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
                export_path = os.path.join(self.submission_dir, SUBDIR_EXPORTS, f'system_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')

            ensure_parent_dir(export_path)

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                export_data = {}

                tables = ['assignments', 'assignment_submissions', 'groups', 'group_members',
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

    def system_maintenance(self):
        """Maintenance menu: backups, reminders, integrity check, archive, export, cleanup."""
        if not self._check_permission('manage_assignments'):
            return
        actions = (
            ("Back up database and submission files", self.backup_system_data),
            ("Send due-date reminders now", self.run_due_date_reminders),
            ("Check submission integrity (missing or altered files)", self.check_submission_integrity),
            ("Archive one assignment's submissions to a zip", self._archive_submissions_prompt),
            ("Export system data", self.export_system_data),
            ("Show assignment data statistics", self.show_assignment_data_stats),
            ("Clean up old notifications, cache and audit entries", self._cleanup_prompt),
        )
        while True:
            print("\nSystem Maintenance")
            print("-" * 30)
            for i, (label, _) in enumerate(actions, 1):
                print(f"{i}. {label}")
            print("0. Back")
            choice = input("Choice: ").strip()
            if choice == '0' or not choice:
                return
            if choice.isdigit() and 0 < int(choice) <= len(actions):
                result = actions[int(choice) - 1][1]()
                if isinstance(result, str):
                    print(f"Written to {result}")
            else:
                print("Invalid choice.")

    def _archive_submissions_prompt(self):
        aid = input("Assignment ID to archive: ").strip()
        if not aid.isdigit():
            print("Invalid assignment ID.")
            return None
        return self.archive_submissions(int(aid))

    def _cleanup_prompt(self):
        print("This permanently deletes read notifications older than 30 days, expired analytics "
              "cache older than 7 days, and audit-log entries older than one year.")
        if input("Continue? (y/n): ").strip().lower() == 'y':
            self.cleanup_old_data()

    def check_submission_integrity(self):
        """Compare every stored submission with its file on disk."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT s.id, s.student_id, a.title, s.file_path, s.file_hash "
                "FROM assignment_submissions s LEFT JOIN assignments a ON a.id = s.assignment_id "
                "WHERE s.file_path IS NOT NULL AND s.file_path <> ''").fetchall()
            orphans = conn.execute(
                "SELECT COUNT(*) FROM assignment_submissions s "
                "WHERE NOT EXISTS (SELECT 1 FROM assignments a WHERE a.id = s.assignment_id)").fetchone()[0]
        finally:
            conn.close()
        missing, altered, ok = [], [], 0
        for sid, student, title, path, stored_hash in rows:
            if not os.path.isfile(path):
                missing.append((sid, student, title, path))
                continue
            if stored_hash:
                try:
                    if self._calculate_file_hash(path) != stored_hash:
                        altered.append((sid, student, title, path))
                        continue
                except OSError:
                    missing.append((sid, student, title, path))
                    continue
            ok += 1
        print(f"\nChecked {len(rows)} submission file(s): {ok} intact, {len(missing)} missing, "
              f"{len(altered)} changed since submission.")
        if orphans:
            print(f"{orphans} submission row(s) belong to assignments that no longer exist.")
        for label, items in (("Missing", missing), ("Changed", altered)):
            for sid, student, title, path in items[:20]:
                print(f"  {label}: submission {sid} ({student}, {title}) -> {path}")
            if len(items) > 20:
                print(f"  ... and {len(items) - 20} more")

    def show_assignment_data_stats(self):
        """Row counts for the assignment tables and the size of the submissions folder."""
        tables = ("assignments", "assignment_submissions", "rubrics", "rubric_criteria", "groups",
                  "group_members", "peer_reviews", "extension_requests", "assignment_moderation",
                  "assignment_non_submissions", "assignment_reassessments", "notifications", "audit_log")
        conn = sqlite3.connect(self.db_path)
        try:
            existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            print(f"\n{'Table':<30} {'Rows':>8}")
            print("-" * 40)
            for table in tables:
                if table in existing:
                    # ``table`` comes from the fixed tuple above and exists in sqlite_master.
                    count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]  # nosec B608
                    print(f"{table:<30} {count:>8}")
                else:
                    print(f"{table:<30} {'(none)':>8}")
        finally:
            conn.close()
        total = files = 0
        for root, _dirs, names in os.walk(self.submission_dir):
            for name in names:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                    files += 1
                except OSError:
                    pass
        print(f"\nSubmissions folder: {self.submission_dir}")
        print(f"  {files} file(s), {total / (1024 * 1024):.1f} MB")
        try:
            print(f"Database file: {os.path.getsize(self.db_path) / (1024 * 1024):.1f} MB")
        except OSError:
            pass
