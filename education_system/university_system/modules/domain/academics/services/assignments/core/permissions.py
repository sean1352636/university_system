from education_system.university_system.infrastructure.database.db import sqlite3


class PermissionsMixin:
    """Mixin providing permission checks and student ID helpers."""

    def _check_permission(self, permission):
        """Check if the current user has the required permission"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to access this feature.")
            return False

        if not self.auth.check_permission(permission):
            print(f"You don't have permission to {permission.replace('_', ' ')}.")
            return False

        return True

    def _get_student_id(self):
        """Get the current user's student ID"""
        if not self.auth or not self.auth.current_user:
            return None

        # Check auth dict first (avoids unnecessary DB hit)
        sid = self.auth.current_user.get('student_id')
        if sid:
            return sid

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT student_id FROM users WHERE id = ?
            ''', (self.auth.current_user['id'],))

            result = cursor.fetchone()
            conn.close()

            return result[0] if result and result[0] else None

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def _get_student_modules(self, student_id):
        """Get all modules for a student"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT module_code, module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE student_id = ?
            ORDER BY module_code
            ''', (student_id,))

            modules = cursor.fetchall()
            conn.close()

            return modules

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
