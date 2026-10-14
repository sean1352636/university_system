"""Formal, effective-dated student registration and status lifecycle.

Every change updates the authoritative ``students`` row, appends an immutable
history record, creates downstream reconciliation work, and publishes one
coordinated enrolment event.  Consumer systems can retry their own work without
rolling back the student-record decision.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schema_version import (
    require_tables,
)
from education_system.systems.university.services.operations import (
    OperationResult,
    OperationalIssue,
)
from education_system.systems.university.services.boundary_errors import (
    EnrolmentBoundaryError,
)

ACTIVE = "Active"
REGISTRATION_PENDING = "Registration Pending"
INTERRUPTED = "Interrupted"
WITHDRAWN = "Withdrawn"
DEFERRED = "Deferred"
SUSPENDED = "Suspended"
COMPLETED = "Completed"
CLOSED = "Closed"

DOWNSTREAM_SYSTEMS = (
    "finance", "module_enrolments", "visa_monitoring",
    "accommodation", "library", "student_account",
)

_STATUS_ACTIONS: dict[str, tuple[frozenset[str], str]] = {
    "interrupt": (frozenset({ACTIVE}), INTERRUPTED),
    "withdraw": (
        frozenset({ACTIVE, REGISTRATION_PENDING, INTERRUPTED, SUSPENDED}),
        WITHDRAWN,
    ),
    "defer": (frozenset({ACTIVE, REGISTRATION_PENDING}), DEFERRED),
    "suspend": (frozenset({ACTIVE}), SUSPENDED),
    "resume": (frozenset({INTERRUPTED, SUSPENDED, DEFERRED}), ACTIVE),
    "complete": (frozenset({ACTIVE}), COMPLETED),
    "close": (frozenset({COMPLETED, WITHDRAWN}), CLOSED),
}


def available_actions(status: str | None) -> tuple[str, ...]:
    """Lifecycle actions legal from *status*, in declaration order.

    The transition table is the domain's business rule, so callers (the
    records GUI, the API) ask for it rather than re-deriving it. An
    unknown or legacy status - anything outside the vocabulary above,
    e.g. a hand-set 'Graduated' - yields no actions rather than raising,
    so a caller can explain the record is outside the state machine.
    """
    return tuple(
        action for action, (sources, _target) in _STATUS_ACTIONS.items()
        if status in sources
    )


def target_status(action: str) -> str | None:
    """The status *action* moves a student to, or None if unknown."""
    entry = _STATUS_ACTIONS.get(action.strip().lower())
    return entry[1] if entry else None


def ensure_schema() -> None:
    """Validate the migration-owned lifecycle schema without mutating it."""
    require_tables(
        (
            "students",
            frozenset({
                "student_id", "academic_year", "mode_of_study",
                "campus_code", "expected_return_date", "record_closed_at",
            }),
        ),
        (
            "student_registrations",
            frozenset({"registration_id", "student_id", "academic_year"}),
        ),
        (
            "student_lifecycle_history",
            frozenset({"history_id", "student_id", "action", "effective_date"}),
        ),
        (
            "student_lifecycle_actions",
            frozenset({"action_id", "history_id", "target_system", "status"}),
        ),
    )


def _student(conn, student_id: str):
    row = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if row is None:
        raise EnrolmentBoundaryError(f"Student {student_id!r} does not exist")
    return row


def _regulation_version(conn, programme_code: str | None, academic_year: str) -> int | None:
    if not programme_code:
        return None
    try:
        row = conn.execute(
            """SELECT v.version_id
                 FROM governed_programmes p
                 JOIN programme_versions v ON v.programme_id=p.programme_id
                WHERE p.programme_code=? AND v.status='approved'
                  AND v.effective_academic_year<=?
                  AND (v.end_academic_year IS NULL OR v.end_academic_year>=?)
                ORDER BY v.effective_academic_year DESC LIMIT 1""",
            (programme_code, academic_year, academic_year),
        ).fetchone()
        governed = conn.execute(
            "SELECT 1 FROM governed_programmes WHERE programme_code=?",
            (programme_code,),
        ).fetchone()
    except Exception:
        return None
    if governed and row is None:
        raise EnrolmentBoundaryError(
            f"No approved regulation version is effective for {programme_code}"
        )
    return int(row["version_id"]) if row else None


def _record(conn, student, *, action: str, actor_id: str, reason: str,
            effective_date: str, to_status: str | None = None,
            academic_year: str | None = None,
            new_programme: str | None = None, new_mode: str | None = None,
            new_campus: str | None = None, repeat_year: int | None = None,
            expected_return_date: str | None = None) -> int:
    cur = conn.execute(
        """INSERT INTO student_lifecycle_history
             (student_id, action, from_status, to_status, effective_date,
              academic_year, old_programme, new_programme, old_mode, new_mode,
              old_campus, new_campus, repeat_year, expected_return_date,
              reason, actor_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            student["student_id"], action, student["status"], to_status,
            effective_date, academic_year, student["course"], new_programme,
            student["mode_of_study"], new_mode, student["campus_code"],
            new_campus, repeat_year, expected_return_date, reason, actor_id,
        ),
    )
    history_id = int(cur.lastrowid)
    payload = json.dumps({
        "history_id": history_id,
        "student_id": student["student_id"],
        "action": action,
        "from_status": student["status"],
        "to_status": to_status,
        "effective_date": effective_date,
        "academic_year": academic_year,
        "programme": new_programme,
        "mode": new_mode,
        "campus": new_campus,
        "repeat_year": repeat_year,
        "expected_return_date": expected_return_date,
        "reason": reason,
    })
    for target in DOWNSTREAM_SYSTEMS:
        conn.execute(
            """INSERT INTO student_lifecycle_actions
                 (history_id, student_id, target_system, action, payload_json)
               VALUES (?, ?, ?, ?, ?)""",
            (history_id, student["student_id"], target, action, payload),
        )
    return history_id


def _publish(
    student_id: str, action: str, history_id: int, **payload: Any
) -> OperationResult[str]:
    """Publish durably without making an already-committed decision disappear."""
    try:
        from education_system.platform.integrations.external.cross_system_bus import (
            publish_cross_system,
        )
        event_id = publish_cross_system(
            "enrolment.changed",
            source_system="university",
            source_module="student_lifecycle",
            journey_id=student_id,
            target_system="university",
            action=action,
            student_id=student_id,
            history_id=history_id,
            **payload,
        )
        return OperationResult.success(event_id)
    except Exception as exc:
        # ``student_lifecycle_actions`` is the durable reconciliation source of
        # truth. Return a visible degraded result so API/workers can report it.
        return OperationResult.failure(
            OperationalIssue.from_exception(
                exc,
                component="cross_system_event_outbox",
                retryable=True,
            )
        )


def register(student_id: str, academic_year: str, *, actor_id: str,
             mode_of_study: str | None = None,
             programme_code: str | None = None, campus_code: str | None = None,
             declarations: dict[str, Any] | None = None,
             returning: bool = False) -> int:
    """Complete annual registration or re-registration."""
    ensure_schema()
    kind = "re-registration" if returning else "annual_registration"
    now = datetime.now().date().isoformat()
    with transaction() as conn:
        student = _student(conn, student_id)
        if student["status"] in {WITHDRAWN, CLOSED}:
            raise EnrolmentBoundaryError(f"Cannot register a {student['status'].lower()} student")
        selected_programme = programme_code or student["course"]
        regulation_version = _regulation_version(
            conn, selected_programme, academic_year
        )
        registration_columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(student_registrations)"
            ).fetchall()
        }
        if "regulation_version_id" in registration_columns:
            cur = conn.execute(
                """INSERT INTO student_registrations
                     (student_id, academic_year, registration_type,
                      mode_of_study, programme_code, campus_code,
                      registered_by, declarations_json, regulation_version_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    student_id, academic_year, kind,
                    mode_of_study or student["mode_of_study"], selected_programme,
                    campus_code or student["campus_code"], actor_id,
                    json.dumps(declarations or {}), regulation_version,
                ),
            )
        else:
            cur = conn.execute(
                """INSERT INTO student_registrations
                     (student_id, academic_year, registration_type,
                      mode_of_study, programme_code, campus_code,
                      registered_by, declarations_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    student_id, academic_year, kind,
                    mode_of_study or student["mode_of_study"], selected_programme,
                    campus_code or student["campus_code"], actor_id,
                    json.dumps(declarations or {}),
                ),
            )
        if regulation_version is not None:
            programme = conn.execute(
                "SELECT programme_id FROM programme_versions WHERE version_id=?",
                (regulation_version,),
            ).fetchone()
            conn.execute(
                "UPDATE student_regulation_assignments SET active=0 "
                "WHERE student_id=? AND active=1",
                (student_id,),
            )
            conn.execute(
                """INSERT INTO student_regulation_assignments
                     (student_id, programme_id, version_id, assigned_by, reason)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    student_id, programme["programme_id"], regulation_version,
                    actor_id, f"{kind} {academic_year}",
                ),
            )
        history_id = _record(
            conn, student, action=kind, actor_id=actor_id,
            reason=f"{academic_year} registration completed",
            effective_date=now, to_status=ACTIVE,
            academic_year=academic_year,
            new_programme=programme_code or student["course"],
            new_mode=mode_of_study or student["mode_of_study"],
            new_campus=campus_code or student["campus_code"],
        )
        conn.execute(
            """UPDATE students SET status = ?, academic_year = ?,
                   mode_of_study = COALESCE(?, mode_of_study),
                   course = COALESCE(?, course),
                   campus_code = COALESCE(?, campus_code),
                   expected_return_date = NULL
               WHERE student_id = ?""",
            (ACTIVE, academic_year, mode_of_study, programme_code,
             campus_code, student_id),
        )
        registration_id = int(cur.lastrowid)
        from education_system.systems.university.infrastructure.events import (
            transactional_publisher,
        )
        transactional_publisher.publish(
            conn,
            "enrolment.registration.recorded",
            {
                "student_id": student_id,
                "action": kind,
                "history_id": history_id,
                "academic_year": academic_year,
                "registration_id": registration_id,
            },
            aggregate_id=student_id,
            idempotency_key=f"enrolment:{history_id}",
        )
    return registration_id


def select_module(
    student_id: str,
    module_code: str,
    *,
    academic_year: str,
    actor_id: str,
    teaching_period: str | None = None,
) -> int:
    """Create a canonical module enrolment under the current registration."""
    ensure_schema()
    with transaction() as conn:
        registration = conn.execute(
            """SELECT registration_id FROM programme_registrations
                WHERE student_id = ? AND academic_year = ?
                  AND status IN ('registered', 'active', 'completed')
                ORDER BY registration_id DESC LIMIT 1""",
            (student_id, academic_year),
        ).fetchone()
        if registration is None:
            # During migration, mirror the formal annual registration into the
            # canonical programme registration before accepting selections.
            student = _student(conn, student_id)
            cursor = conn.execute(
                """INSERT INTO programme_registrations
                     (student_id, programme_code, academic_year,
                      occurrence_code, mode_of_study, status, effective_from,
                      registered_at, registered_by)
                   VALUES (?, ?, ?, 'MAIN', ?, 'registered', ?, ?, ?)""",
                (
                    student_id,
                    student["course"],
                    academic_year,
                    student["mode_of_study"],
                    datetime.now().date().isoformat(),
                    datetime.now().isoformat(),
                    actor_id,
                ),
            )
            registration_id = int(cursor.lastrowid)
        else:
            registration_id = int(registration["registration_id"])
        module = conn.execute(
            "SELECT module_code FROM modules WHERE module_code = ?",
            (module_code,),
        ).fetchone()
        if module is None:
            raise EnrolmentBoundaryError(f"Module {module_code!r} does not exist")
        cursor = conn.execute(
            """INSERT INTO module_enrolments
                 (registration_id, student_id, module_code, academic_year,
                  teaching_period, attempt_number, status, effective_from)
               VALUES (?, ?, ?, ?, ?, 1, 'enrolled', ?)""",
            (
                registration_id,
                student_id,
                module_code,
                academic_year,
                teaching_period,
                datetime.now().date().isoformat(),
            ),
        )
        return int(cursor.lastrowid)


def change_status(student_id: str, action: str, *, actor_id: str, reason: str,
                  effective_date: str | None = None,
                  expected_return_date: str | None = None) -> int:
    """Interrupt, withdraw, defer, suspend, resume, complete or close."""
    ensure_schema()
    action = action.strip().lower()
    if action not in _STATUS_ACTIONS:
        raise EnrolmentBoundaryError(f"Unknown lifecycle action {action!r}")
    sources, target = _STATUS_ACTIONS[action]
    effective = effective_date or datetime.now().date().isoformat()
    with transaction() as conn:
        student = _student(conn, student_id)
        if student["status"] not in sources:
            raise EnrolmentBoundaryError(
                f"Cannot {action} student in status {student['status']!r}"
            )
        history_id = _record(
            conn, student, action=action, actor_id=actor_id, reason=reason,
            effective_date=effective, to_status=target,
            expected_return_date=expected_return_date,
        )
        conn.execute(
            """UPDATE students SET status = ?, is_active = ?,
                   expected_return_date = ?,
                   record_closed_at = CASE WHEN ? = 'Closed'
                                           THEN ? ELSE record_closed_at END
               WHERE student_id = ?""",
            (target, int(target == ACTIVE), expected_return_date, target,
             datetime.now().isoformat(), student_id),
        )
        if action in {"interrupt", "withdraw", "suspend", "complete", "close"}:
            module_status = {
                "interrupt": "Paused", "suspend": "Paused",
                "withdraw": "Withdrawn", "complete": "Completed",
                "close": "Closed",
            }[action]
            conn.execute(
                "UPDATE student_modules SET status = ? "
                "WHERE student_id = ? AND status = 'Enrolled'",
                (module_status, student_id),
            )
        elif action == "resume":
            conn.execute(
                "UPDATE student_modules SET status = 'Enrolled' "
                "WHERE student_id = ? AND status = 'Paused'",
                (student_id,),
            )
    _publish(
        student_id, action, history_id, status=target,
        expected_return_date=expected_return_date,
    )
    return history_id


def change_study(student_id: str, *, actor_id: str, reason: str,
                 programme_code: str | None = None,
                 mode_of_study: str | None = None,
                 campus_code: str | None = None,
                 repeat_year: int | None = None,
                 academic_year: str | None = None) -> int:
    """Apply programme, mode, campus or repeat-year changes."""
    ensure_schema()
    supplied = [
        programme_code is not None, mode_of_study is not None,
        campus_code is not None, repeat_year is not None,
    ]
    if sum(supplied) != 1:
        raise EnrolmentBoundaryError("Supply exactly one study change")
    action = (
        "programme_transfer" if programme_code is not None else
        "mode_change" if mode_of_study is not None else
        "campus_change" if campus_code is not None else "repeat_year"
    )
    with transaction() as conn:
        student = _student(conn, student_id)
        if student["status"] not in {ACTIVE, INTERRUPTED, SUSPENDED}:
            raise EnrolmentBoundaryError("Study details cannot be changed in this status")
        history_id = _record(
            conn, student, action=action, actor_id=actor_id, reason=reason,
            effective_date=datetime.now().date().isoformat(),
            academic_year=academic_year, new_programme=programme_code,
            new_mode=mode_of_study, new_campus=campus_code,
            repeat_year=repeat_year,
        )
        conn.execute(
            """UPDATE students SET course = COALESCE(?, course),
                   mode_of_study = COALESCE(?, mode_of_study),
                   campus_code = COALESCE(?, campus_code),
                   grade_level = COALESCE(?, grade_level),
                   academic_year = COALESCE(?, academic_year)
               WHERE student_id = ?""",
            (programme_code, mode_of_study, campus_code,
             str(repeat_year) if repeat_year is not None else None,
             academic_year, student_id),
        )
    _publish(student_id, action, history_id)
    return history_id


def pending_actions(*, target_system: str | None = None) -> list[dict[str, Any]]:
    ensure_schema()
    with get_connection() as conn:
        sql = "SELECT * FROM student_lifecycle_actions WHERE status = 'pending'"
        params: tuple[Any, ...] = ()
        if target_system:
            sql += " AND target_system = ?"
            params = (target_system,)
        return [dict(row) for row in conn.execute(
            sql + " ORDER BY action_id", params
        ).fetchall()]


def complete_action(action_id: int, *, error: str | None = None) -> None:
    ensure_schema()
    with transaction() as conn:
        cur = conn.execute(
            """UPDATE student_lifecycle_actions
                  SET status = ?, attempts = attempts + 1, last_error = ?,
                      completed_at = CASE WHEN ? IS NULL
                                          THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE action_id = ?""",
            ("failed" if error else "completed", error, error, action_id),
        )
        if cur.rowcount != 1:
            raise EnrolmentBoundaryError(f"Lifecycle action {action_id} does not exist")


def reverse_change(
    history_id: int, *, reason: str, requested_by: str, approved_by: str
) -> int:
    """Reverse a lifecycle decision under independent dual control."""
    ensure_schema()
    if requested_by == approved_by or not reason.strip():
        raise EnrolmentBoundaryError(
            "Lifecycle reversal requires a reason and independent approval"
        )
    with transaction() as conn:
        original = conn.execute(
            "SELECT * FROM student_lifecycle_history WHERE history_id=?",
            (history_id,),
        ).fetchone()
        if original is None:
            raise EnrolmentBoundaryError(f"Lifecycle history {history_id} does not exist")
        student = _student(conn, original["student_id"])
        reversal_id = _record(
            conn,
            student,
            action=f"reverse:{original['action']}",
            actor_id=approved_by,
            reason=reason,
            effective_date=datetime.now().date().isoformat(),
            to_status=original["from_status"],
            academic_year=original["academic_year"],
            new_programme=original["old_programme"],
            new_mode=original["old_mode"],
            new_campus=original["old_campus"],
        )
        conn.execute(
            """UPDATE students SET status=COALESCE(?, status),
                   is_active=CASE WHEN COALESCE(?, status)=? THEN 1 ELSE 0 END,
                   course=COALESCE(?, course), mode_of_study=COALESCE(?, mode_of_study),
                   campus_code=COALESCE(?, campus_code)
               WHERE student_id=?""",
            (
                original["from_status"], original["from_status"], ACTIVE,
                original["old_programme"],
                original["old_mode"], original["old_campus"],
                original["student_id"],
            ),
        )
        conn.execute(
            """INSERT INTO student_lifecycle_corrections
                 (history_id, reversal_history_id, reason, requested_by, approved_by)
               VALUES (?, ?, ?, ?, ?)""",
            (history_id, reversal_id, reason, requested_by, approved_by),
        )
        from education_system.systems.university.infrastructure.events import (
            transactional_publisher,
        )
        transactional_publisher.publish(
            conn,
            "enrolment.change.reversed",
            {
                "student_id": original["student_id"],
                "history_id": history_id,
                "reversal_history_id": reversal_id,
                "reason": reason,
            },
            aggregate_id=str(original["student_id"]),
            idempotency_key=f"enrolment:{history_id}:reversed",
        )
        return reversal_id


def reconciliation_dashboard() -> dict[str, Any]:
    """Operator view of outstanding, failed and completed downstream work."""
    ensure_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT target_system, status, COUNT(*) AS count,
                      MAX(attempts) AS max_attempts,
                      MIN(created_at) AS oldest
                 FROM student_lifecycle_actions
                GROUP BY target_system, status
                ORDER BY target_system, status"""
        ).fetchall()
        failures = [
            dict(row) for row in conn.execute(
                """SELECT * FROM student_lifecycle_actions
                    WHERE status='failed' ORDER BY created_at, action_id"""
            ).fetchall()
        ]
        return {"summary": [dict(row) for row in rows], "failures": failures}


def history(student_id: str) -> list[dict[str, Any]]:
    ensure_schema()
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM student_lifecycle_history WHERE student_id = ? "
            "ORDER BY history_id", (student_id,)
        ).fetchall()]


__all__ = [
    "register", "change_status", "change_study", "pending_actions",
    "complete_action", "history", "reverse_change", "reconciliation_dashboard",
    "ensure_schema", "available_actions", "target_status",
    "DOWNSTREAM_SYSTEMS",
]
