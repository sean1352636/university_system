"""Fail-closed authorization for the legacy grade dialogs.

The ``dialogs/*.py`` dialogs predate the GradeManager-based authorization and
receive no auth handle, so they historically wrote grades with no permission,
ownership, or enrolment check at all. They are currently unreachable (nothing
instantiates them) but remain exported, so this gives them defense-in-depth:
any grade write they attempt is authorized against the shared university auth
context and re-checks module ownership. If the auth context is unavailable the
write is DENIED, never allowed — the correct outcome for a code path whose auth
wiring is absent.

Mirrors ``GradeManager.authorize_grade_mutation`` but resolves the acting user
from ``shared_context`` rather than an injected ``self.auth``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_REQUIRED = {
    "create": ("manage_grades", "enter_grades"),
    "update": ("manage_grades", "edit_grades"),
    "delete": ("manage_grades",),
    "import": ("manage_grades", "enter_grades"),
}
_STAFF_ROLES = {"staff", "instructor", "faculty"}


def _current_user():
    try:
        from education_system.systems.university.infrastructure import shared_context

        return shared_context.get_current_user()
    except Exception:
        # No initialised auth context -> fail closed.
        return None


def _check_permission(permission: str) -> bool:
    try:
        from education_system.systems.university.infrastructure import shared_context

        return bool(shared_context.check_permission(permission))
    except Exception:
        return False


def _owns_module(cursor, module_code, username, user_id) -> bool:
    cursor.execute(
        "SELECT 1 FROM modules m WHERE m.module_code=? AND m.instructor IN (?, ?) "
        "UNION SELECT 1 FROM module_schedule ms WHERE ms.module_code=? "
        "AND CAST(ms.instructor_id AS TEXT) IN (?, ?) LIMIT 1",
        (module_code, username, user_id, module_code, username, user_id),
    )
    return cursor.fetchone() is not None


def module_code_for(cursor, *, grade_id=None, assessment_id=None, assignment_id=None):
    """Resolve the module_code a grade/assessment/assignment belongs to, or None."""
    try:
        if grade_id is not None:
            cursor.execute(
                "SELECT a.module_code FROM grades g JOIN assessments a "
                "ON a.assessment_id=g.assessment_id WHERE g.grade_id=?",
                (grade_id,),
            )
        elif assignment_id is not None:
            cursor.execute("SELECT module_code FROM assignments WHERE id=?", (assignment_id,))
        elif assessment_id is not None:
            cursor.execute(
                "SELECT module_code FROM assessments WHERE assessment_id=?", (assessment_id,)
            )
        else:
            return None
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        logger.exception("module_code resolution failed")
        return None


def is_student_enrolled(cursor, student_id, module_code) -> bool:
    """True only if *student_id* is actively enrolled in *module_code*.

    Grading a student who is not enrolled in the module is a data-integrity
    breach regardless of who performs it, so callers check this per student
    inside the same transaction as the write. Fails closed on any error.
    """
    if not student_id or not module_code:
        return False
    try:
        cursor.execute(
            "SELECT 1 FROM student_modules "
            "WHERE student_id=? AND module_code=? AND LOWER(status)='enrolled' LIMIT 1",
            (student_id, module_code),
        )
        return cursor.fetchone() is not None
    except Exception:
        logger.exception("enrolment check failed closed")
        return False


def authorize_grade_mutation(
    action, *, cursor, grade_id=None, assessment_id=None, assignment_id=None, student_id=None
) -> bool:
    """Fail-closed permission + module-ownership check for a grade write.

    When *student_id* is supplied, additionally require that the student is
    enrolled in the module (skipped for admins, who may override).
    """
    user = _current_user()
    if not user:
        return False
    role = str(user.get("role", "")).lower()
    if role == "admin":
        return True
    required = _REQUIRED.get(action, ())
    if role not in _STAFF_ROLES or not any(_check_permission(p) for p in required):
        return False
    username = str(user.get("username") or "")
    user_id = str(user.get("id") or "")
    try:
        module_code = module_code_for(
            cursor, grade_id=grade_id, assessment_id=assessment_id, assignment_id=assignment_id
        )
        if not module_code:
            return False
        if not _owns_module(cursor, module_code, username, user_id):
            return False
        if student_id is not None and not is_student_enrolled(cursor, student_id, module_code):
            return False
        return True
    except Exception:
        logger.exception("legacy grade authorization failed closed")
        return False


def authorize_module_change(*, cursor, module_code) -> bool:
    """Fail-closed check for enrolment changes on a module (staff-owned)."""
    user = _current_user()
    if not user:
        return False
    role = str(user.get("role", "")).lower()
    if role == "admin":
        return True
    if role not in _STAFF_ROLES:
        return False
    try:
        return _owns_module(
            cursor, module_code, str(user.get("username") or ""), str(user.get("id") or "")
        )
    except Exception:
        logger.exception("legacy enrolment authorization failed closed")
        return False


def require_grade_mutation(action, *, cursor, **scope) -> bool:
    """Authorize and, on denial, show an error dialog. Returns the decision."""
    allowed = authorize_grade_mutation(action, cursor=cursor, **scope)
    if not allowed:
        _deny_message()
    return allowed


def require_module_change(*, cursor, module_code) -> bool:
    allowed = authorize_module_change(cursor=cursor, module_code=module_code)
    if not allowed:
        _deny_message()
    return allowed


def _deny_message() -> None:
    try:
        from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking._dialogs import messagebox

        messagebox.showerror("Access denied", "You are not authorised to change these records.")
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)


__all__ = [
    "authorize_grade_mutation",
    "authorize_module_change",
    "require_grade_mutation",
    "require_module_change",
    "is_student_enrolled",
    "module_code_for",
]
