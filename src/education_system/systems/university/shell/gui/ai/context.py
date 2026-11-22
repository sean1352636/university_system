import time
import logging

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
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
                # auth_user is already a dictionary from UserAuth system.
                # student_id is carried through deliberately: the login name and
                # the student number are separate id spaces, and every record
                # lookup below keys on the student number. Dropping it here
                # forced the queries to guess with the username.
                self.current_user = {
                    "username": auth_user.get('username', 'Unknown'),
                    "role": auth_user.get('role', 'user'),
                    "permissions": auth_user.get('permissions', []),
                    "student_id": auth_user.get('student_id'),
                    "display_name": auth_user.get('display_name')
                        or auth_user.get('username', 'Unknown'),
                }
                self.session_id = f"gui_{self.current_user['username']}_{int(time.time())}"
                print(f"✓ Chatbot GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                # Should not reach here since we check auth in __init__
                raise RuntimeError("No authenticated user found")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            raise

    def _record_id(self):
        """The id the academic tables key on, not the login name.

        ``student_id`` when the session carries one, falling back to the
        username (most seeded student logins use their student number as their
        username, so the fallback is usually right, but it is a guess).
        """
        return self.current_user.get('student_id') or self.current_user.get('username', '')

    def get_user_context(self):
        """Get context-aware information from database for current user"""
        try:
            if not self.current_user:
                return {}

            context = {
                'programme': None,
                'courses': [],
                'grades': [],
                'schedule': [],
                'notifications': []
            }

            username = self.current_user.get('username', '')
            record_id = self._record_id()
            role = self.current_user.get('role', '')

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get user's courses (if student)
                if role == 'student':
                    # ``courses`` is the *programme* table — 21 degrees, keyed
                    # 'CS' / 'DS' / 'ACC'. ``student_modules.module_code`` holds
                    # *module* codes ('CIS0001'), which live in ``modules``.
                    # This used to join courses.code = student_modules.module_code,
                    # two vocabularies that can never match, so it returned zero
                    # rows for every student and the chatbot told fully enrolled
                    # students they were "not enrolled in any courses".
                    cursor.execute('''
                        SELECT sm.module_code,
                               COALESCE(m.module_name, sm.module_name, sm.module_code),
                               COALESCE(m.credits, 0)
                        FROM student_modules sm
                        LEFT JOIN modules m ON m.module_code = sm.module_code
                        WHERE sm.student_id = ?
                        AND LOWER(sm.status) = 'enrolled'
                        ORDER BY sm.module_code
                        LIMIT 10
                    ''', (record_id,))
                    courses = cursor.fetchall()
                    context['courses'] = [{'id': c[0], 'name': c[1], 'credits': c[2]} for c in courses]

                    # The degree programme is a separate question from the
                    # modules, and it is what the student's academic record
                    # shows. Surface both rather than conflating them.
                    cursor.execute('''
                        SELECT co.code, COALESCE(co.course_name, co.name), co.credits
                        FROM students s
                        JOIN courses co ON co.code = s.course
                        WHERE s.student_id = ?
                    ''', (record_id,))
                    prog = cursor.fetchone()
                    if prog:
                        context['programme'] = {'id': prog[0], 'name': prog[1], 'credits': prog[2]}

                    # Get recent grades.
                    # This used to join grades to student_modules on student_id
                    # ALONE — a cartesian product that paired every grade with
                    # every module the student was enrolled on. A student with a
                    # single 100/A+ was shown that same mark against five
                    # different modules they had never been graded on.
                    # Attribute each grade to its own module instead: via
                    # module_grades directly, and via grades -> assessments for
                    # per-assessment marks. UNION (not UNION ALL) so a result
                    # recorded in both places is reported once.
                    cursor.execute('''
                        SELECT module, letter, score, awarded FROM (
                            SELECT COALESCE(m.module_name, mg.module_code) AS module,
                                   mg.final_grade AS letter,
                                   mg.final_score AS score,
                                   COALESCE(mg.completion_date, mg.date_recorded) AS awarded
                            FROM module_grades mg
                            LEFT JOIN modules m ON m.module_code = mg.module_code
                            WHERE mg.student_id = ?
                            UNION
                            SELECT COALESCE(m.module_name, a.module_code),
                                   g.letter_grade, g.score, g.submission_date
                            FROM grades g
                            JOIN assessments a ON a.assessment_id = g.assessment_id
                            LEFT JOIN modules m ON m.module_code = a.module_code
                            WHERE g.student_id = ?
                        )
                        ORDER BY awarded DESC
                        LIMIT 5
                    ''', (record_id, record_id))
                    grades = cursor.fetchall()
                    context['grades'] = [{'course': g[0], 'grade': g[1], 'points': g[2], 'date': g[3]} for g in grades]

                # Get instructor's courses
                elif role == 'instructor':
                    # Same conflation as the student branch: instructors teach
                    # modules, not degree programmes, and courses.instructor_id
                    # is unpopulated in any case. Resolve through the three
                    # links the rest of the codebase uses (DashboardService
                    # .get_instructor_dashboard_data agrees).
                    cursor.execute('''
                        SELECT DISTINCT m.module_code, m.module_name, COALESCE(m.credits, 0)
                        FROM modules m
                        LEFT JOIN module_schedule ms ON ms.module_code = m.module_code
                        WHERE m.instructor = ?
                           OR ms.instructor_id = ?
                           OR m.module_code IN (
                               SELECT module_code FROM instructor_modules
                               WHERE instructor_id = ?
                           )
                        ORDER BY m.module_code
                        LIMIT 10
                    ''', (record_id, record_id, record_id))
                    courses = cursor.fetchall()
                    context['courses'] = [{'id': c[0], 'name': c[1], 'credits': c[2]} for c in courses]

                # Get pending notifications/tasks
                try:
                    cursor.execute('''
                        SELECT COALESCE(m.message, m.content), m.sent_at
                        FROM messages m
                        JOIN users u ON u.id = m.recipient_id
                        WHERE u.username = ? AND m.is_read = 0
                          AND COALESCE(m.is_deleted_by_recipient, 0) = 0
                        ORDER BY m.sent_at DESC
                        LIMIT 5
                    ''', (username,))
                    notifications = cursor.fetchall()
                    context['notifications'] = [{'message': n[0], 'date': n[1]} for n in notifications]
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            return context

        except Exception as e:
            print(f"Error getting user context: {e}")
            return {}
