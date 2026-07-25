"""Exam day → attendance row.

Step 3 of the attendance/absence/exam closed loop. When invigilators
enter exam results (or mark exam-day attendance directly), mirror
each student's presence into the canonical ``attendance_records``
table — keyed by the exam's module — so exam attendance contributes
to the % the eligibility gate (step 1) reads.

Public API:

  record_exam_attendance(exam_id, student_id, status, *, recorded_by,
                         notes=None) -> bool
      Insert (or refresh) one attendance row. ``status`` should be
      one of 'Present' / 'Absent' / 'Late' / 'Excused' to match the
      values ``compute_exam_eligibility`` already counts.

  record_exam_attendance_bulk(exam, present_ids, *, recorded_by,
                              absent_ids=None) -> dict
      Convenience wrapper for the common "mark every enrolled
      student as Present or Absent based on whether they got a
      result" flow. ``absent_ids=None`` means "any enrolled student
      not in present_ids", computed from ``exam.enrolled_student_ids``.

Each row is uniquely keyed by (student, module, session_id) where
``session_id = 'EXAM-<exam_id>'`` so re-running the writer (e.g.
results re-saved) updates instead of duplicating.

After a successful bulk write, the writer:
  * publishes ``EVENT_ENROLMENT_CHANGED`` on the cross-GUI bus so
    open Attendance / Absence / Exam windows refresh,
  * recomputes ``exam_eligibility`` for every affected student via
    the canonical adapter so the eligibility tab stays in sync.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection

logger = logging.getLogger(__name__)

_VALID_STATUSES = {"Present", "Absent", "Late", "Excused"}


def _exam_session_id(exam_id: int | str) -> str:
    return f"EXAM-{int(exam_id)}"


def _normalise_status(status: str) -> str:
    """Accept various casings; map to the canonical capitalised form."""
    if not status:
        return "Absent"
    norm = status.strip().capitalize()
    if norm not in _VALID_STATUSES:
        return "Absent"
    return norm


def record_exam_attendance(
    exam_id: int,
    student_id: str | int,
    status: str,
    *,
    module_code: str | None = None,
    exam_date: str | None = None,
    recorded_by: str = "exam_invigilation",
    notes: str | None = None,
) -> bool:
    """Upsert one ``attendance_records`` row for an exam day.

    ``module_code`` and ``exam_date`` are looked up from ``exams``
    when not supplied so callers can stay terse.
    """
    sid = str(student_id)
    norm_status = _normalise_status(status)
    session_id = _exam_session_id(exam_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_connection() as conn:
            if not module_code or not exam_date:
                row = conn.execute(
                    "SELECT module_code, date FROM exams WHERE id = ?",
                    (int(exam_id),),
                ).fetchone()
                if not row:
                    return False
                module_code = module_code or row[0]
                exam_date = exam_date or row[1]
            if not module_code or not exam_date:
                return False

            # Idempotent on (student, module, date, session_id) so
            # re-saving exam results refreshes instead of duplicating.
            existing = conn.execute(
                "SELECT id FROM attendance_records "
                "WHERE student_id = ? AND module_code = ? "
                "  AND date = ? AND session_id = ?",
                (sid, module_code, exam_date, session_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE attendance_records "
                    "SET status = ?, notes = COALESCE(?, notes), "
                    "    recorded_by = ?, recorded_at = ?, "
                    "    check_in_method = 'exam_invigilation' "
                    "WHERE id = ?",
                    (norm_status, notes, recorded_by, now, existing[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO attendance_records "
                    "(student_id, module_code, date, status, notes, "
                    " recorded_by, recorded_at, check_in_method, session_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'exam_invigilation', ?)",
                    (sid, module_code, exam_date, norm_status, notes,
                     recorded_by, now, session_id),
                )
            conn.commit()
            return True
    except Exception as exc:
        logger.warning(
            "record_exam_attendance(exam=%s, student=%s) failed: %s",
            exam_id, sid, exc,
        )
        return False


def record_exam_attendance_bulk(
    exam: Any,
    present_ids: Iterable[str | int],
    *,
    recorded_by: str = "exam_invigilation",
    absent_ids: Iterable[str | int] | None = None,
) -> dict[str, int]:
    """Mark every enrolled student Present or Absent in one call.

    ``exam`` accepts either an ``Exam`` dataclass instance or a dict
    with at least ``id``, ``module_code``, ``date``, and
    ``enrolled_student_ids`` (list).

    When ``absent_ids`` is None, every enrolled student not in
    ``present_ids`` is treated as absent — the typical "results
    were entered for some students" flow.

    Returns ``{written, failed, present_count, absent_count}``.
    """
    # Tolerate dict, dataclass, or sqlite3.Row
    def _get(field: str, default=None):
        if isinstance(exam, dict):
            return exam.get(field, default)
        try:
            return getattr(exam, field)
        except AttributeError:
            try:
                return exam[field]
            except (KeyError, IndexError, TypeError):
                return default

    exam_id = _get("id")
    module_code = _get("module_code")
    exam_date = _get("date")
    raw_roster = _get("enrolled_student_ids", []) or []
    if isinstance(raw_roster, str):
        try:
            import json
            raw_roster = json.loads(raw_roster) or []
        except Exception:
            raw_roster = []

    enrolled = {str(x) for x in raw_roster}
    present = {str(x) for x in (present_ids or [])}
    if absent_ids is None:
        absent = enrolled - present
    else:
        absent = {str(x) for x in absent_ids}

    written = failed = 0
    affected: set[str] = set()
    for sid in present:
        ok = record_exam_attendance(
            exam_id, sid, "Present",
            module_code=module_code, exam_date=exam_date,
            recorded_by=recorded_by,
            notes="Marked Present from exam results entry.",
        )
        written += int(ok); failed += int(not ok)
        if ok:
            affected.add(sid)
    for sid in absent:
        ok = record_exam_attendance(
            exam_id, sid, "Absent",
            module_code=module_code, exam_date=exam_date,
            recorded_by=recorded_by,
            notes="Auto-marked Absent (not in exam results).",
        )
        written += int(ok); failed += int(not ok)
        if ok:
            affected.add(sid)

    # Cross-GUI: refresh + eligibility re-sync
    if affected:
        try:
            from education_system.systems.university.interfaces.gui.academics._event_bus import (
                publish, EVENT_ENROLMENT_CHANGED,
            )
            publish(EVENT_ENROLMENT_CHANGED,
                    exam_id=int(exam_id) if exam_id else None,
                    module_code=module_code,
                    action="exam_attendance_recorded")
        except Exception:
            pass
        try:
            from education_system.systems.university.interfaces.gui.academics._attendance_eligibility import (
                bulk_recompute_for_exam,
            )
            if exam_id:
                bulk_recompute_for_exam(int(exam_id))
        except Exception:
            pass

    return {
        "written": written,
        "failed": failed,
        "present_count": len(present),
        "absent_count": len(absent),
    }


__all__ = [
    "record_exam_attendance",
    "record_exam_attendance_bulk",
]
