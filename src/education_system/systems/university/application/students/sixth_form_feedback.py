"""Tell a learner's sixth form how they got on at university.

The sixth form records each leaver's destination and whether it was
*sustained* (still there through the following year). Until now it could
only find out by asking the learner. Once the university holds the facts it
publishes them on the cross-system bus:

* ``university.student.progressed`` — when a progression board's decision
  that the student continues to the next year is ratified
  (:func:`publish_board_progressions`, called by ``boards.service.ratify``).
* ``university.student.withdrawn`` — when a withdrawal is recorded in the
  student lifecycle (:func:`publish_withdrawn`, called after commit by
  ``student_lifecycle._publish`` and by the plain-status fallback in
  ``student_lifecycle_service``).

Only learners whose journey includes the sixth form are reported, decided
through the platform identity registry (the ``college`` slot of
``student_journey``) — the university never imports the sixth form.

What crosses is deliberately thin: ids, years, dates and a reason
*category*. Withdrawal reasons in the lifecycle are free text and may hold
health or personal detail, so they are never sent; the category is
``"academic"`` when a ratified-or-recorded board decision withdrew the
student, otherwise ``"not_disclosed"``.

Every function here is best-effort: the university decision is already
committed, and failing to tell the college must never undo or block it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)

EVENT_PROGRESSED = "university.student.progressed"
EVENT_WITHDRAWN = "university.student.withdrawn"

#: The only reason categories that ever leave the university.
REASON_ACADEMIC = "academic"
REASON_NOT_DISCLOSED = "not_disclosed"
REASON_CATEGORIES = (REASON_ACADEMIC, REASON_NOT_DISCLOSED)

_SOURCE_MODULE = "learners.sixth_form_feedback"


def _connection(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path)


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}  # nosec B608 - fixed names


def _table_exists(conn, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)).fetchone() is not None


def sixth_form_journey(conn, student_id: str) -> str | None:
    """The live journey id of *student_id* if that journey includes the
    sixth form, else ``None``. Uses the platform identity registry."""
    try:
        from education_system.platform.cross_system import identity_service
    except Exception:
        logger.debug("identity service unavailable", exc_info=True)
        return None
    journey_id = None
    if "journey_id" in _columns(conn, "students"):
        row = conn.execute("SELECT journey_id FROM students WHERE student_id = ?",
                           (str(student_id),)).fetchone()
        journey_id = (row[0] if row else None) or None
    try:
        record = None
        if journey_id:
            live = identity_service.resolve_journey_id(journey_id)
            record = identity_service.get(live) if live else None
        if record is None:
            record = identity_service.find_by_student("university", str(student_id))
    except Exception:
        logger.debug("journey lookup failed for %s", student_id, exc_info=True)
        return None
    if not record or not record.get("college_student_id"):
        return None
    return record.get("journey_id")


def _year_of_study(conn, student_id: str) -> int | None:
    from education_system.systems.university.application.modules import (
        registration as module_registration,
    )
    cols = _columns(conn, "students")
    enrolled = None
    if "enrollment_date" in cols:
        row = conn.execute("SELECT enrollment_date FROM students WHERE student_id = ?",
                           (str(student_id),)).fetchone()
        enrolled = row[0] if row else None
    try:
        return module_registration.year_of_study(
            conn, {"student_id": str(student_id), "enrollment_date": enrolled})
    except Exception:
        logger.debug("year of study unknown for %s", student_id, exc_info=True)
        return None


def _iso_day(value: Any) -> str:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return date.today().isoformat()


def _publish(event_name: str, *, journey_id: str, idempotency_key: str,
             **payload: Any) -> str | None:
    try:
        from education_system.platform.integrations.external.cross_system_bus import (
            publish_cross_system,
        )
        # ``journey_id`` is a keyword of publish_cross_system, so it travels
        # on the envelope (envelope["journey_id"]), not inside the payload.
        return publish_cross_system(
            event_name, source_system="university", source_module=_SOURCE_MODULE,
            journey_id=journey_id, target_system="sixth_form",
            idempotency_key=idempotency_key, **payload)
    except Exception:
        logger.warning("could not publish %s for journey %s", event_name, journey_id,
                       exc_info=True)
        return None


# ── withdrawal ──────────────────────────────────────────────────────────


def withdrawal_reason_category(conn, student_id: str) -> str:
    """``academic`` when an assessment board decided to withdraw the
    student, else ``not_disclosed``. Free-text reasons are never read."""
    if _table_exists(conn, "assessment_board_decisions"):
        row = conn.execute(
            "SELECT 1 FROM assessment_board_decisions WHERE student_id = ? "
            "AND decision_type = 'withdraw' AND module_code IS NULL LIMIT 1",
            (str(student_id),)).fetchone()
        if row:
            return REASON_ACADEMIC
    return REASON_NOT_DISCLOSED


def publish_withdrawn(student_id: str, *, history_id: int | None = None,
                      db_path=None) -> str | None:
    """Publish ``university.student.withdrawn`` for a committed withdrawal.

    Returns the event id, or ``None`` when the learner did not come from
    the sixth form (or anything failed)."""
    try:
        conn = _connection(db_path)
    except Exception:
        logger.warning("withdrawal feedback: no database", exc_info=True)
        return None
    try:
        journey_id = sixth_form_journey(conn, student_id)
        if not journey_id:
            return None
        withdrawn_on = None
        if history_id is not None and _table_exists(conn, "student_lifecycle_history"):
            row = conn.execute(
                "SELECT effective_date FROM student_lifecycle_history WHERE history_id = ?",
                (history_id,)).fetchone()
            withdrawn_on = row[0] if row else None
        withdrawn_on = _iso_day(withdrawn_on)
        from_year = _year_of_study(conn, student_id)
        category = withdrawal_reason_category(conn, student_id)
    except Exception:
        logger.warning("withdrawal feedback for %s failed", student_id, exc_info=True)
        return None
    finally:
        conn.close()
    return _publish(
        EVENT_WITHDRAWN, journey_id=journey_id,
        idempotency_key=f"university.withdrawn:{student_id}:{withdrawn_on}",
        university_student_id=str(student_id), from_year=from_year,
        withdrawn_on=withdrawn_on, reason_category=category,
        recorded_on=datetime.now().date().isoformat())


# ── progression ─────────────────────────────────────────────────────────


def continuing_students(conn, board_id: int) -> list[str]:
    """Students whose latest student-level decision on *board_id* is
    ``continue`` (progress to the next year)."""
    rows = conn.execute(
        """SELECT d.student_id, d.decision_type FROM assessment_board_decisions d
            WHERE d.board_id = ? AND d.module_code IS NULL
              AND d.decision_id = (SELECT MAX(x.decision_id) FROM assessment_board_decisions x
                                    WHERE x.board_id = d.board_id
                                      AND x.student_id = d.student_id
                                      AND x.module_code IS NULL)""",
        (board_id,)).fetchall()
    return [str(r[0]) for r in rows if r[1] == "continue"]


def publish_board_progressions(board_id: int, *, db_path=None) -> list[str]:
    """After a progression board is ratified, publish
    ``university.student.progressed`` for every sixth-form learner it
    progressed. Returns the event ids published."""
    try:
        conn = _connection(db_path)
    except Exception:
        logger.warning("progression feedback: no database", exc_info=True)
        return []
    plans: list[dict[str, Any]] = []
    try:
        board = conn.execute(
            "SELECT board_type, ratified_at FROM assessment_boards WHERE board_id = ?",
            (board_id,)).fetchone()
        if board is None or board[0] != "progression_award":
            return []
        recorded_on = _iso_day(board[1])
        for student_id in continuing_students(conn, board_id):
            journey_id = sixth_form_journey(conn, student_id)
            if not journey_id:
                continue
            from_year = _year_of_study(conn, student_id)
            if not from_year:
                continue
            plans.append({"journey_id": journey_id, "student_id": student_id,
                          "from_year": from_year, "to_year": from_year + 1,
                          "recorded_on": recorded_on})
    except Exception:
        logger.warning("progression feedback for board %s failed", board_id, exc_info=True)
        return []
    finally:
        conn.close()
    out = []
    for p in plans:
        event_id = _publish(
            EVENT_PROGRESSED, journey_id=p["journey_id"],
            idempotency_key=(f"university.progressed:{p['student_id']}:"
                             f"{p['from_year']}:{p['to_year']}"),
            university_student_id=p["student_id"], from_year=p["from_year"],
            to_year=p["to_year"], reason_category=None, recorded_on=p["recorded_on"])
        if event_id:
            out.append(event_id)
    return out


__all__ = [
    "EVENT_PROGRESSED", "EVENT_WITHDRAWN", "REASON_CATEGORIES",
    "continuing_students", "publish_board_progressions", "publish_withdrawn",
    "sixth_form_journey", "withdrawal_reason_category",
]
