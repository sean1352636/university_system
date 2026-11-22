"""Thin coordinator for grade-management workflows."""
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import messagebox

from .grades.schema import init_basic_database, init_enhanced_grades_db
from .grades.scale import (
    GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage,
    percentage_to_letter,
)
from .grades.ui.grade_view import safe_combo_update, safe_grab_set
from .grades.ui.grade_view import GradeViewMixin
from .grades.scale import GradeScaleMixin
from .grades.notifications import GradeNotificationMixin
from .grades.ui.add_dialog import AddGradeDialogMixin
from .grades.ui.edit_dialog import EditGradeDialogMixin
from .grades.repository import GradeRepositoryMixin
from .grades.imports import GradeImportMixin
from .grades.ui.batch_dialog import BatchGradeDialogMixin
from .grades.statistics import GradeStatisticsMixin
from .grades.ui.statistics_dialog import StatisticsDialogMixin
from .grades.exam_integration import ExamIntegrationMixin

class GradeManager(
    GradeViewMixin,
    GradeScaleMixin,
    GradeNotificationMixin,
    AddGradeDialogMixin,
    EditGradeDialogMixin,
    GradeRepositoryMixin,
    GradeImportMixin,
    BatchGradeDialogMixin,
    GradeStatisticsMixin,
    StatisticsDialogMixin,
    ExamIntegrationMixin,
):
    """Coordinates extracted grade workflows."""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth
        self.conn = app.conn

    @property
    def content_frame(self):
        """Dynamically get content frame from layout"""
        if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'content_frame'):
            return self.app.layout.content_frame
        return None

    def get_safe_cursor(self):
        """Get a safe database cursor, checking connection validity"""
        if self.conn is None:
            # Try to get connection from app
            if hasattr(self.app, 'conn') and self.app.conn is not None:
                self.conn = self.app.conn
            else:
                raise ConnectionError("Database connection is not available. Please restart the application.")

        try:
            return self.conn.cursor()
        except Exception as e:
            raise ConnectionError(f"Failed to create database cursor: {e}")

    def safe_commit(self):
        """Safely commit database changes"""
        if self.conn is None:
            # Try to get connection from app
            if hasattr(self.app, 'conn') and self.app.conn is not None:
                self.conn = self.app.conn
            else:
                raise ConnectionError("Database connection is not available. Please restart the application.")

        try:
            self.conn.commit()
        except Exception as e:
            raise ConnectionError(f"Failed to commit database changes: {e}")

    def authorize_grade_mutation(self, action, *, assessment_id=None,
                                 assignment_id=None, grade_id=None, student_id=None,
                                 cursor=None, submission_id=None):
        """Fail-closed permission and module-scope check for grade writes.

        When ``student_id`` is supplied, additionally require the student to be
        enrolled in the module (non-admins only) — a grade must not be written
        for a student not enrolled in the assessment's module.
        """
        user = getattr(self.auth, 'current_user', None) if self.auth else None
        if not user:
            return False
        role = str(user.get('role', '')).lower()
        if role == 'admin':
            return True
        required = {
            'create': ('manage_grades', 'enter_grades'),
            'update': ('manage_grades', 'edit_grades'),
            'delete': ('manage_grades',),
            'import': ('manage_grades', 'enter_grades'),
        }.get(action, ())
        try:
            if role not in {'staff', 'instructor', 'faculty'} or not any(
                    self.auth.check_permission(permission) for permission in required):
                return False
        except Exception:
            return False

        cursor = cursor or self.get_safe_cursor()
        username = str(user.get('username') or '')
        user_id = str(user.get('id') or '')
        try:
            if grade_id is not None:
                cursor.execute(
                    "SELECT a.module_code FROM grades g JOIN assessments a "
                    "ON a.assessment_id=g.assessment_id WHERE g.grade_id=?",
                    (grade_id,),
                )
            elif assignment_id is not None:
                cursor.execute("SELECT module_code FROM assignments WHERE id=?", (assignment_id,))
            else:
                cursor.execute("SELECT module_code FROM assessments WHERE assessment_id=?", (assessment_id,))
            row = cursor.fetchone()
            if not row:
                return False
            module_code = row[0]
            cursor.execute(
                "SELECT 1 FROM modules m WHERE m.module_code=? AND m.instructor IN (?, ?) "
                "UNION SELECT 1 FROM module_schedule ms WHERE ms.module_code=? "
                "AND CAST(ms.instructor_id AS TEXT) IN (?, ?) LIMIT 1",
                (module_code, username, user_id, module_code, username, user_id),
            )
            if cursor.fetchone() is None:
                return False
            if student_id is not None:
                cursor.execute(
                    "SELECT 1 FROM student_modules WHERE student_id=? AND module_code=? "
                    "AND LOWER(status)='enrolled' LIMIT 1",
                    (student_id, module_code),
                )
                if cursor.fetchone() is None:
                    return False
            return True
        except Exception:
            return False

    def require_grade_mutation(self, action, **scope):
        allowed = self.authorize_grade_mutation(action, **scope)
        if not allowed:
            messagebox.showerror("Access denied", "You are not authorised to change these grades.")
            return False
        locked = self._board_lock_message(**scope)
        if locked:
            messagebox.showerror("Marks locked", locked)
            return False
        return True

    def _board_lock_message(self, *, grade_id=None, assessment_id=None, assignment_id=None,
                            student_id=None, submission_id=None, cursor=None):
        """Explain a ratified-result lock before the write is attempted.

        The database triggers enforce the lock for every writer; this only
        turns their refusal into a message staff can act on. Resit components
        are never locked.
        """
        from .grades.marking_rules import locked_message
        cursor = cursor or self.get_safe_cursor()
        try:
            if grade_id is not None:
                row = cursor.execute(
                    "SELECT g.student_id, a.module_code, a.reassessment_of FROM grades g "
                    "JOIN assessments a ON a.assessment_id = g.assessment_id WHERE g.grade_id = ?",
                    (grade_id,)).fetchone()
            elif submission_id is not None:
                row = cursor.execute(
                    "SELECT s.student_id, a.module_code, a.reassessment_of FROM assignment_submissions s "
                    "JOIN assignments a ON a.id = s.assignment_id WHERE s.id = ?",
                    (submission_id,)).fetchone()
            elif student_id is not None and assessment_id is not None:
                row = cursor.execute(
                    "SELECT ?, module_code, reassessment_of FROM assessments WHERE assessment_id = ?",
                    (student_id, assessment_id)).fetchone()
            elif student_id is not None and assignment_id is not None:
                row = cursor.execute(
                    "SELECT ?, module_code, reassessment_of FROM assignments WHERE id = ?",
                    (student_id, assignment_id)).fetchone()
            else:
                return None
        except Exception:
            return None
        if not row or row[2] is not None:
            return None
        return locked_message(cursor, row[0], row[1])

__all__ = [
    "GradeManager", "GRADE_SYSTEMS", "percentage_to_letter",
    "letter_to_percentage", "letter_to_gpa", "init_basic_database",
    "init_enhanced_grades_db", "safe_grab_set", "safe_combo_update",
]
