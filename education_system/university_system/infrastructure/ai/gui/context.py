import time
import logging

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

logger = logging.getLogger(__name__)


class ContextMixin:
    """Mixin for user context and authentication setup."""

    def setup_current_user(self):
        """Setup current user from central authentication system"""
        try:
            # Get current user from central auth system
            auth_user = self.auth_system.current_user

            if auth_user:
                # auth_user is already a dictionary from UserAuth system
                self.current_user = {
                    "username": auth_user.get('username', 'Unknown'),
                    "role": auth_user.get('role', 'user'),
                    "permissions": auth_user.get('permissions', [])
                }
                self.session_id = f"gui_{self.current_user['username']}_{int(time.time())}"
                print(f"✓ Chatbot GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                # Should not reach here since we check auth in __init__
                raise RuntimeError("No authenticated user found")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            raise

    def get_user_context(self):
        """Get context-aware information from database for current user"""
        try:
            if not self.current_user:
                return {}

            context = {
                'courses': [],
                'grades': [],
                'schedule': [],
                'notifications': []
            }

            username = self.current_user.get('username', '')
            role = self.current_user.get('role', '')

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get user's courses (if student)
                if role == 'student':
                    cursor.execute('''
                        SELECT DISTINCT c.id, c.course_name, c.credits
                        FROM courses c
                        JOIN student_modules sm ON c.code = sm.module_code
                        WHERE sm.student_id = ?
                        AND LOWER(sm.status) = 'enrolled'
                        LIMIT 10
                    ''', (username,))
                    courses = cursor.fetchall()
                    context['courses'] = [{'id': c[0], 'name': c[1], 'credits': c[2]} for c in courses]

                    # Get recent grades
                    cursor.execute('''
                        SELECT sm.module_name, g.letter_grade, g.score, g.submission_date
                        FROM grades g
                        JOIN student_modules sm ON g.student_id = sm.student_id
                        WHERE g.student_id = ?
                        ORDER BY g.submission_date DESC
                        LIMIT 5
                    ''', (username,))
                    grades = cursor.fetchall()
                    context['grades'] = [{'course': g[0], 'grade': g[1], 'points': g[2], 'date': g[3]} for g in grades]

                # Get instructor's courses
                elif role == 'instructor':
                    cursor.execute('''
                        SELECT id, course_name, credits
                        FROM courses
                        WHERE instructor_id = ?
                        LIMIT 10
                    ''', (username,))
                    courses = cursor.fetchall()
                    context['courses'] = [{'id': c[0], 'name': c[1], 'credits': c[2]} for c in courses]

                # Get pending notifications/tasks
                try:
                    cursor.execute('''
                        SELECT message, created_at
                        FROM notifications
                        WHERE user_id = ? AND is_read = 0
                        ORDER BY created_at DESC
                        LIMIT 5
                    ''', (username,))
                    notifications = cursor.fetchall()
                    context['notifications'] = [{'message': n[0], 'date': n[1]} for n in notifications]
                except Exception:
                    pass  # Table might not exist

            return context

        except Exception as e:
            print(f"Error getting user context: {e}")
            return {}
