"""Who may see whose health data, and the record of every look.

Health data is UK GDPR special-category data, so:

* **Clinicians** (roles in :data:`CLINICAL_ROLES`) and administrators see
  any student's record.
* **A student** sees only their own — matched on ``current_user['student_id']``
  (the student number), never the account's numeric ``id``.
* **Everyone else** (other staff, instructors, parents, alumni) sees nothing,
  unless they use **break-glass** access for one student with a written
  reason (:func:`break_glass`), which is logged and reported to the health
  administrators.

Every view is written to the immutable audit log (:func:`record_view`). If
the audit entry cannot be written the view is refused — an unrecorded look
at a health record must not happen.
"""

from __future__ import annotations

from dataclasses import dataclass

ADMIN_ROLES = ("admin", "administrator", "superadmin")
CLINICAL_ROLES = ("nurse", "doctor", "clinician", "first_aider", "dentist", "health_admin")
BREAK_GLASS_MINUTES = 60
_GRANTS: dict = {}          # (username, student_id) -> expiry (this process)


@dataclass(frozen=True)
class HealthUser:
    username: str
    role: str
    user_id: object = None
    student_id: str | None = None

    @property
    def is_clinician(self) -> bool:
        return self.role in CLINICAL_ROLES or self.role in ADMIN_ROLES

    @property
    def is_student(self) -> bool:
        return self.role == "student"


def from_user(current_user: dict | None) -> HealthUser | None:
    if not current_user or not current_user.get("username"):
        return None
    return HealthUser(str(current_user["username"]), str(current_user.get("role") or "").lower(),
                      current_user.get("id"), current_user.get("student_id"))


def scope(who: HealthUser | None) -> str | None:
    """``None`` = may see every student; a student number = only that one.
    Anyone else raises ``PermissionError``."""
    if who is None:
        raise PermissionError("Sign in to use the health portal")
    if who.is_clinician:
        return None
    if who.is_student and who.student_id:
        return str(who.student_id)
    raise PermissionError("Health records are for the health team and the student themselves")


# Counselling and wellbeing notes have their own practitioners, who are not
# clinicians for the rest of the health record (and clinicians outside those
# teams still see them, as before).
AREA_ROLES = {
    "counselling": ("counsellor", "counselor"),
    "wellbeing": ("counsellor", "counselor", "wellness_officer", "wellbeing_officer"),
}


def scope_area(who: HealthUser | None, area: str) -> str | None:
    """:func:`scope` for one area (``'counselling'`` / ``'wellbeing'``): the
    area's own practitioners (:data:`AREA_ROLES`) also see every student.
    ``None`` = every student; a student number = only that one; anyone else
    raises ``PermissionError``."""
    if area not in AREA_ROLES:
        raise ValueError(f"Unknown health area {area!r}")
    if who is not None and who.role in AREA_ROLES[area]:
        return None
    return scope(who)


def may_view(who: HealthUser | None, student_id) -> bool:
    try:
        allowed = scope(who)
    except PermissionError:
        return _granted(who, student_id)
    return allowed is None or str(student_id) == allowed or _granted(who, student_id)


def require_view(who: HealthUser | None, student_id) -> None:
    if not may_view(who, student_id):
        raise PermissionError("You cannot see this student's health record")


def require_clinician(who: HealthUser | None, what="do this") -> None:
    if who is None or not who.is_clinician:
        raise PermissionError(f"Only the health team can {what}")


def record_view(who: HealthUser, area: str, *, student_id=None, record_id=None,
                reason: str | None = None, conn=None) -> None:
    """Write the view to the immutable audit log, or raise (fail closed)."""
    from education_system.systems.university.infrastructure.security.immutable_audit_log import (
        AuditAction, log_security_event,
    )
    try:
        log_security_event(
            user_id=who.username, action=AuditAction.DATA_VIEW,
            resource_type=f"health_{area}",
            resource_id=None if record_id is None else str(record_id),
            details={"student_id": None if student_id is None else str(student_id),
                     "role": who.role, "reason": reason}, conn=conn)
    except Exception as exc:
        raise PermissionError(f"The access could not be recorded, so it was refused ({exc})") \
            from None


def break_glass(who: HealthUser, student_id, reason: str) -> list[tuple]:
    """Emergency access to one student's record for :data:`BREAK_GLASS_MINUTES`
    by someone outside the health team. Needs a real reason; logged as such.
    Returns e-mails for the health administrators (send after commit)."""
    from datetime import datetime, timedelta
    if who is None:
        raise PermissionError("Sign in first")
    reason = str(reason or "").strip()
    if len(reason) < 15:
        raise ValueError("Explain the emergency (at least a sentence)")
    record_view(who, "break_glass", student_id=student_id, reason=reason)
    _GRANTS[(who.username, str(student_id))] = datetime.now() + timedelta(
        minutes=BREAK_GLASS_MINUTES)
    return [(address, "Health record opened with break-glass access",
             f"{who.username} ({who.role}) opened student {student_id}'s health record "
             f"without a clinical role. Reason given: {reason}")
            for address in _health_admin_emails()]


def _granted(who, student_id) -> bool:
    from datetime import datetime
    if who is None or student_id is None:
        return False
    expiry = _GRANTS.get((who.username, str(student_id)))
    return bool(expiry and expiry > datetime.now())


def _health_admin_emails() -> list[str]:
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection(row_factory=False)
        try:
            marks = ",".join("?" * 2)
            return [r[0] for r in conn.execute(
                f"SELECT email FROM users WHERE LOWER(role) IN ({marks}) "  # nosec B608
                "AND COALESCE(email, '') <> ''", ("health_admin", "admin"))]
        finally:
            conn.close()
    except Exception:
        return []
