"""Canonical writes for the course catalogue.

Students already have :mod:`student_lifecycle_service`; courses did not. The
GUI (``course_management_gui/courses/course_crud.py``) and the CLI
(``domain/services/course_management/courses.py``) each carried their own copy
of the rules, written straight against sqlite3, so they could drift apart and
a third adapter would have meant a third copy. This service holds those rules
once:

* a course code is unique case-insensitively, across BOTH the legacy ``code``
  column and the newer ``course_code`` one;
* every write fills both column families, because different parts of the
  system read different ones - student enrolment looks up ``course_code``
  while older catalogue screens read ``code``;
* an edit snapshots the previous catalogue entry first;
* a change publishes ``course.changed`` so open GUIs refresh;
* destructive deletion reports its blast radius and refuses to run blind.

The GUI and CLI still have their own copies. Migrating them onto this service
is the follow-up that makes the guarantee real.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from education_system.systems.university.infrastructure.database.db import transaction

logger = logging.getLogger(__name__)

#: Canonical course statuses, lower-case.
#:
#: The catalogue had a split brain: this column held ``'active'`` on 20 rows
#: and ``'Inactive'`` on one, the status dialog offered title-case
#: ``Active/Inactive/Archived/Cancelled``, and student enrolment matched
#: ``status='active'`` exactly - so a course saved as ``'Active'`` became
#: invisible to enrolment. Two call sites had already grown
#: ``(status='Active' OR status='active')`` workarounds.
#:
#: Lower-case wins because enrolment already depends on it and 20 of 21 rows
#: were already that way. Writes normalise; reads compare case-insensitively
#: so rows written before this still resolve.
ACTIVE = "active"
INACTIVE = "inactive"
ARCHIVED = "archived"
CANCELLED = "cancelled"

#: Every status the catalogue recognises. Only ACTIVE is offered to students.
STATUSES = (ACTIVE, INACTIVE, ARCHIVED, CANCELLED)


def normalise_status(value: str | None) -> str:
    """Fold any casing onto the canonical form, defaulting to active."""
    text = str(value or "").strip().lower()
    return text if text in STATUSES else (ACTIVE if not text else text)

#: Columns an edit may touch. Deliberately excludes ``id``, ``code``/
#: ``course_code`` (identity), ``current_enrollment`` (derived) and ``status``
#: (owned by archive/restore).
EDITABLE = {
    "course_name", "description", "level", "department", "credit_hours",
    "max_enrollment", "course_type", "course_fee", "lab_required",
    "online_available", "contact_hours_per_week", "min_ucas_tariff",
    "learning_outcomes", "assessment_methods", "required_textbooks",
    "duration", "tags", "availability_periods",
}

#: Child tables a destructive delete clears, in FK-safe order. Mirrors the
#: GUI and CLI cascades, which between them cover these five.
CASCADE_TABLES = (
    ("course_prerequisites", "course_id = ? OR prerequisite_course_id = ?", 2),
    ("course_schedule", "course_id = ?", 1),
    ("course_waitlist", "course_id = ?", 1),
    ("course_history", "course_id = ?", 1),
    ("course_analytics", "course_id = ?", 1),
)


#: 2-4 letters, then up to four optional digits: CS, ENGL, CIS109.
#:
#: Three rules were in play before this service existed. The GUI dialog used
#: this one; ``core/validation.validate_course_code`` demanded 2-3 digits,
#: which rejects 20 of the 21 codes actually in the catalogue; and the
#: infrastructure validator has a third. The live data settles it - digits are
#: optional - so migrating the CLI onto this rule fixes course creation there
#: rather than constraining it.
COURSE_CODE_RE = re.compile(r"^[A-Z]{2,4}\d{0,4}$")


class CourseValidationError(ValueError):
    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("; ".join(f"{k}: {v}" for k, v in self.errors.items()))


class CourseImpactError(RuntimeError):
    """A destructive delete was attempted without acknowledging its impact."""

    def __init__(self, message: str, impact: Mapping[str, int]):
        self.impact = dict(impact)
        super().__init__(message)


@dataclass(frozen=True)
class CourseCommand:
    course_code: str
    course_name: str
    credit_hours: int = 3
    description: str = ""
    level: str = ""
    department: str = ""
    max_enrollment: int = 30
    course_type: str = "Core"
    course_fee: float = 0.0
    lab_required: bool = False
    online_available: bool = False
    min_ucas_tariff: int = 0


@dataclass(frozen=True)
class CourseResult:
    course_id: str
    course_code: str
    status: str
    changed_fields: tuple[str, ...] = ()


def _require_text(value: Any, field: str, errors: dict[str, str]) -> str:
    text = str(value or "").strip()
    if not text:
        errors[field] = "is required"
    return text


def _require_int(value: Any, field: str, errors: dict[str, str],
                 *, minimum: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors[field] = "must be a whole number"
        return minimum
    if number < minimum:
        errors[field] = f"must be at least {minimum}"
    return number


def validate_course_command(command: CourseCommand) -> CourseCommand:
    errors: dict[str, str] = {}
    code = _require_text(command.course_code, "course_code", errors).upper()
    if code and not COURSE_CODE_RE.match(code):
        errors["course_code"] = (
            "must be 2-4 letters, optionally followed by up to 4 digits "
            "(e.g. CS, ENGL, CIS109)")
    name = _require_text(command.course_name, "course_name", errors)
    credit_hours = _require_int(command.credit_hours, "credit_hours", errors, minimum=1)
    max_enrollment = _require_int(command.max_enrollment, "max_enrollment", errors, minimum=1)
    try:
        fee = float(command.course_fee or 0)
    except (TypeError, ValueError):
        errors["course_fee"] = "must be a number"
        fee = 0.0
    if fee < 0:
        errors["course_fee"] = "cannot be negative"
    if errors:
        raise CourseValidationError(errors)
    from dataclasses import replace
    return replace(command, course_code=code, course_name=name,
                   credit_hours=credit_hours, max_enrollment=max_enrollment,
                   course_fee=fee)


def _publish_changed(course_code: str, action: str) -> None:
    """Tell open GUIs a course moved. Never fatal - it is a refresh hint."""
    try:
        from education_system.systems.university.infrastructure.event_bus import (
            EVENT_COURSE_CHANGED,
            publish,
        )
        publish(EVENT_COURSE_CHANGED, course_code=course_code, action=action)
    except Exception:
        logger.debug("course.changed not published", exc_info=True)


class CourseLifecycleService:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    # ── helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _find(conn, course_ref: str):
        """Resolve by uuid id or by course code, whichever the caller has.

        The catalogue is keyed by a uuid ``id`` but every human-facing screen
        works in course codes, so both are accepted.
        """
        return conn.execute(
            """SELECT * FROM courses
                 WHERE id = ?
                    OR UPPER(COALESCE(NULLIF(TRIM(course_code), ''), code)) = UPPER(?)""",
            (course_ref, course_ref),
        ).fetchone()

    # ── reads ────────────────────────────────────────────────────────
    def get(self, course_ref: str) -> dict[str, Any]:
        with transaction(self.db_path) as conn:
            row = self._find(conn, course_ref)
            if row is None:
                raise CourseValidationError({"course": "does not exist"})
            return {key: row[key] for key in row.keys()}

    def list(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        clause = ("" if include_archived
                  else " WHERE LOWER(COALESCE(NULLIF(TRIM(status), ''), 'active')) = 'active'")
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM courses{clause} ORDER BY COALESCE(NULLIF(TRIM(course_code), ''), code)"  # nosec B608
            ).fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]

    def impact(self, course_ref: str) -> dict[str, int]:
        """What a destructive delete would take with it.

        The same counts the GUI's confirmation dialog and the CLI's warning
        show before asking for ``DELETE CONFIRMED``.
        """
        with transaction(self.db_path) as conn:
            row = self._find(conn, course_ref)
            if row is None:
                raise CourseValidationError({"course": "does not exist"})
            course_id = row["id"]
            code = row["course_code"] or row["code"]
            counts = {
                "students_enrolled": int(conn.execute(
                    "SELECT COUNT(*) FROM students WHERE course = ?", (code,)
                ).fetchone()[0]),
                "dependent_courses": int(conn.execute(
                    "SELECT COUNT(*) FROM course_prerequisites WHERE prerequisite_course_id = ?",
                    (course_id,),
                ).fetchone()[0]),
            }
            for table, where, params in CASCADE_TABLES:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                (table,)).fetchone() is None:
                    counts[table] = 0
                    continue
                counts[table] = int(conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {where}",  # nosec B608
                    (course_id,) * params,
                ).fetchone()[0])
            return counts

    # ── writes ───────────────────────────────────────────────────────
    def create(self, command: CourseCommand, *, actor_id: str) -> CourseResult:
        command = validate_course_command(command)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # courses.id is TEXT and 20 of the 21 catalogue rows use the course
        # code as their id; the single uuid row is a GUI-created outlier. The
        # CLI's "enter a course id" prompts list these ids, so following the
        # dominant convention keeps them usable. id is the PK and code is
        # UNIQUE, so this simply enforces the same uniqueness twice.
        course_id = command.course_code
        with transaction(self.db_path) as conn:
            clash = conn.execute(
                """SELECT 1 FROM courses
                     WHERE UPPER(COALESCE(NULLIF(TRIM(course_code), ''), code)) = ?""",
                (command.course_code,),
            ).fetchone()
            if clash:
                raise CourseValidationError(
                    {"course_code": f"'{command.course_code}' already exists"})
            conn.execute(
                """INSERT INTO courses (
                       id, code, name, credits, date_added,
                       course_code, course_name, description, level, department,
                       credit_hours, max_enrollment, course_type, course_fee,
                       lab_required, online_available, min_ucas_tariff,
                       status, current_enrollment, created_at, updated_at)
                   VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?, ?,?,?, ?,0,?,?)""",
                (course_id, command.course_code, command.course_name,
                 command.credit_hours, now,
                 command.course_code, command.course_name, command.description,
                 command.level, command.department,
                 command.credit_hours, command.max_enrollment,
                 command.course_type, command.course_fee,
                 int(command.lab_required), int(command.online_available),
                 command.min_ucas_tariff, ACTIVE, now, now),
            )
        logger.info("course %s created by %s", command.course_code, actor_id)
        _publish_changed(command.course_code, "create")
        return CourseResult(course_id, command.course_code, ACTIVE)

    def update(self, course_ref: str, changes: Mapping[str, Any], *,
               actor_id: str, reason: str) -> CourseResult:
        unknown = set(changes) - EDITABLE
        if unknown:
            raise CourseValidationError({key: "cannot be updated" for key in unknown})
        if not str(reason or "").strip():
            raise CourseValidationError({"reason": "is required"})
        if not changes:
            raise CourseValidationError({"changes": "no fields to update"})
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with transaction(self.db_path) as conn:
            row = self._find(conn, course_ref)
            if row is None:
                raise CourseValidationError({"course": "does not exist"})
            course_id = row["id"]
            code = row["course_code"] or row["code"]
            self._snapshot(conn, code, reason, actor_id)
            applied = {key: value for key, value in changes.items()
                       if str(row[key] if key in row.keys() else "") != str(value)}
            if not applied:
                return CourseResult(course_id, code, row["status"] or ACTIVE)
            assignments = ", ".join(f"{key} = ?" for key in applied)
            params = [*applied.values(), now, course_id]
            conn.execute(
                f"UPDATE courses SET {assignments}, updated_at = ? WHERE id = ?",  # nosec B608
                params,
            )
            # course_name is mirrored by the legacy ``name`` column.
            if "course_name" in applied:
                conn.execute("UPDATE courses SET name = ? WHERE id = ?",
                             (applied["course_name"], course_id))
            if "credit_hours" in applied:
                conn.execute("UPDATE courses SET credits = ? WHERE id = ?",
                             (applied["credit_hours"], course_id))
        logger.info("course %s updated by %s (%s)", code, actor_id, reason)
        _publish_changed(code, "update")
        return CourseResult(course_id, code, row["status"] or ACTIVE,
                            tuple(sorted(applied)))

    @staticmethod
    def _snapshot(conn, course_code: str, reason: str, actor_id: str) -> None:
        """Version the entry before it changes. Best-effort, as in the GUI."""
        try:
            from education_system.systems.university.services.bus.course_versions import (
                snapshot_course,
            )
            snapshot_course(course_code, change_reason=reason,
                            created_by=actor_id, conn=conn)
        except Exception:
            logger.warning("could not record a course catalogue version",
                           exc_info=True)

    def set_status(self, course_ref: str, status: str, *, actor_id: str,
                   reason: str) -> CourseResult:
        status = normalise_status(status)
        if status not in STATUSES:
            raise CourseValidationError(
                {"status": "must be one of " + ", ".join(STATUSES)})
        if not str(reason or "").strip():
            raise CourseValidationError({"reason": "is required"})
        with transaction(self.db_path) as conn:
            row = self._find(conn, course_ref)
            if row is None:
                raise CourseValidationError({"course": "does not exist"})
            course_id = row["id"]
            code = row["course_code"] or row["code"]
            conn.execute("UPDATE courses SET status = ?, updated_at = ? WHERE id = ?",
                         (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), course_id))
        logger.info("course %s set to %s by %s (%s)", code, status, actor_id, reason)
        _publish_changed(code, status)
        return CourseResult(course_id, code, status)

    def archive(self, course_ref: str, *, actor_id: str, reason: str) -> CourseResult:
        """Retire a course without destroying it - the safe 'delete'.

        An archived course drops out of the active catalogue, so student
        enrolment stops offering it, while every existing record keeps
        resolving.
        """
        return self.set_status(course_ref, ARCHIVED, actor_id=actor_id, reason=reason)

    def restore(self, course_ref: str, *, actor_id: str, reason: str) -> CourseResult:
        return self.set_status(course_ref, ACTIVE, actor_id=actor_id, reason=reason)

    def delete(self, course_ref: str, *, actor_id: str, reason: str,
               acknowledged_impact: bool = False) -> CourseResult:
        """Destructive delete with the cascade the GUI and CLI perform.

        Refuses when the course still has enrolled students or dependent
        courses unless *acknowledged_impact* is set - the API equivalent of
        the CLI's ``DELETE CONFIRMED`` prompt. Note this does NOT reassign
        enrolled students; archive is the right call for a live course.
        """
        if not str(reason or "").strip():
            raise CourseValidationError({"reason": "is required"})
        impact = self.impact(course_ref)
        blocking = impact["students_enrolled"] + impact["dependent_courses"]
        if blocking and not acknowledged_impact:
            raise CourseImpactError(
                f"{impact['students_enrolled']} enrolled student(s) and "
                f"{impact['dependent_courses']} dependent course(s) would be "
                "affected; archive instead, or resend with "
                "acknowledged_impact=true",
                impact,
            )
        with transaction(self.db_path) as conn:
            row = self._find(conn, course_ref)
            if row is None:
                raise CourseValidationError({"course": "does not exist"})
            course_id = row["id"]
            code = row["course_code"] or row["code"]
            for table, where, params in CASCADE_TABLES:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                (table,)).fetchone() is None:
                    continue
                conn.execute(f"DELETE FROM {table} WHERE {where}",  # nosec B608
                             (course_id,) * params)
            conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        logger.warning("course %s DELETED by %s (%s); impact=%s",
                       code, actor_id, reason, impact)
        _publish_changed(code, "delete")
        return CourseResult(course_id, code, "deleted")


__all__ = ["ACTIVE", "ARCHIVED", "CANCELLED", "INACTIVE", "STATUSES",
           "CourseCommand", "CourseImpactError", "CourseLifecycleService",
           "CourseResult", "CourseValidationError", "EDITABLE",
           "normalise_status", "validate_course_command"]
