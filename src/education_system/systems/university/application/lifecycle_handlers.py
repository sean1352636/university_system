"""What each downstream area does when a student's status changes.

``student_lifecycle`` records one ``student_lifecycle_actions`` row per
area for every change (withdraw, interrupt, suspend, resume, complete,
close, reinstate, defer and their ``reverse:`` corrections). The outbox
dispatcher drains them through :func:`drain`, each once
(``lifecycle_consumers.consume_action`` keeps a receipt):

* **module_enrolments** - the module move (Enrolled -> Withdrawn / Paused /
  Completed ...) is applied with the change itself; this re-applies it
  idempotently, and for a reversal moves the modules back.
* **finance** - on withdrawal, unpaid module fees for the withdrawn modules
  are cancelled (paid ones go through refunds, never here).
* **visa_monitoring** - a sponsored student's change opens the UKVI change
  of circumstance (10-day clock); not sponsored, nothing happens.
* **accommodation** - on withdrawal, interruption or suspension, an active
  room assignment's planned move-out is brought forward to the effective
  date, so the housing office sees it in its move-out list.
* **library** - a student leaving (withdrawn, interrupted, suspended,
  completed, closed) is told what they still need to return or pay.
* **student_account** - sign-in follows the new status: off when withdrawn,
  suspended or closed; on again when the student is active.

An action whose change was reversed before it ran is closed as
superseded, not run. A handler that raises leaves the action ``failed`` with the error, and the
next pass tries again.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from education_system.systems.university.application.lifecycle_consumers import (
    consume_action,
)
from education_system.systems.university.infrastructure.database.db import transaction

logger = logging.getLogger(__name__)

LEAVING = ("withdraw", "interrupt", "suspend", "complete", "close")
_MOVES = {
    "interrupt": ("Enrolled", "Paused"), "suspend": ("Enrolled", "Paused"),
    "withdraw": ("Enrolled", "Withdrawn"), "complete": ("Enrolled", "Completed"),
    "close": ("Enrolled", "Closed"), "resume": ("Paused", "Enrolled"),
    "reinstate": ("Withdrawn", "Enrolled"),
}
_LOGIN_OFF = ("Withdrawn", "Suspended", "Closed")


def _action(payload: Mapping[str, Any]) -> tuple[str, bool]:
    """``(base action, is a reversal)``."""
    action = str(payload.get("action") or "")
    if action.startswith("reverse:"):
        return action.split(":", 1)[1], True
    return action, False


def _has_table(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def module_enrolments(payload: Mapping[str, Any]) -> None:
    action, reversal = _action(payload)
    move = _MOVES.get(action)
    if not move:
        return
    source, target = (move[1], move[0]) if reversal else move
    with transaction() as conn:
        conn.execute(
            "UPDATE student_modules SET status = ? WHERE student_id = ? AND status = ?",
            (target, str(payload["student_id"]), source),
        )


def finance(payload: Mapping[str, Any]) -> None:
    action, reversal = _action(payload)
    if action != "withdraw" or reversal:
        return
    from education_system.systems.university.domains.finance.domain.services import (
        enrolment_fees,
    )

    sid = str(payload["student_id"])
    with transaction() as conn:
        modules = [r[0] for r in conn.execute(
            "SELECT DISTINCT module_code FROM student_modules "
            "WHERE student_id = ? AND status = 'Withdrawn'", (sid,))]
    for module_code in modules:
        enrolment_fees.cancel_module_enrolment_fee(
            sid, module_code, payload.get("academic_year"))


def visa_monitoring(payload: Mapping[str, Any]) -> None:
    to_status = payload.get("to_status")
    if not to_status:
        return
    from education_system.systems.university.domains.governance.domain.compliance.international_compliance.services import (  # noqa: E501
        visa_service,
    )

    visa_service.handle_student_status_change(
        str(payload["student_id"]), str(to_status),
        old_status=payload.get("from_status"),
        details=f"Lifecycle {payload.get('action')} effective "
                f"{payload.get('effective_date') or 'today'}",
    )


def accommodation(payload: Mapping[str, Any]) -> None:
    action, reversal = _action(payload)
    if reversal or action not in ("withdraw", "interrupt", "suspend"):
        return
    effective = str(payload.get("effective_date") or "")[:10] or None
    with transaction() as conn:
        if not effective or not _has_table(conn, "housing_assignments"):
            return
        conn.execute(
            "UPDATE housing_assignments SET planned_move_out_date = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE student_id = ? "
            "AND LOWER(COALESCE(status, '')) IN ('active', 'assigned', 'occupied') "
            "AND actual_move_out_date IS NULL "
            "AND (planned_move_out_date IS NULL OR planned_move_out_date > ?)",
            (effective, str(payload["student_id"]), effective),
        )


def library(payload: Mapping[str, Any]) -> None:
    action, reversal = _action(payload)
    if reversal or action not in LEAVING:
        return
    from education_system.systems.university.application.library import services

    with transaction() as conn:
        emails = services.notify_leaver(conn, str(payload["student_id"]))
    if emails:
        from education_system.systems.university.application.teaching import (
            occurrences as timetable_occurrences,
        )
        timetable_occurrences.send_emails(emails)


def student_account(payload: Mapping[str, Any]) -> None:
    to_status = str(payload.get("to_status") or "")
    if not to_status:
        return
    if to_status in _LOGIN_OFF:
        active = False
    elif to_status == "Active":
        active = True
    else:
        return
    from education_system.systems.university.services.student_provisioning import (
        set_student_login_active,
    )

    set_student_login_active(str(payload["student_id"]), active)


def research_pgr(payload: Mapping[str, Any]) -> None:
    """A research applicant became a student: open their PGR record and
    carry over the supervisors who agreed at admission.

    Idempotent - an existing project for the student and proposal title is
    reused, and a supervisor already on its team is not added twice. If the
    PGR tables are not in this database there is no supervision record to
    carry into, and nothing is done.
    """
    if str(payload.get("action") or "initial_registration") != "initial_registration":
        return
    from education_system.systems.university.domains.research.domain.research.pgr import (
        service as pgr,
    )
    try:
        pgr.ensure_schema()
    except Exception:
        logger.info("PGR tables absent; admissions supervisors not carried over")
        return
    student_id = str(payload["student_id"])
    title = str(payload.get("proposal_title") or "").strip() or "Research proposal"
    actor = str(payload.get("actor_id") or "admissions")
    with transaction() as conn:
        existing = conn.execute(
            "SELECT project_id FROM pgr_projects WHERE student_id = ? AND proposal_title = ?",
            (student_id, title),
        ).fetchone()
        team = set()
        if existing:
            team = {r[0] for r in conn.execute(
                "SELECT supervisor_id FROM pgr_supervision_team "
                "WHERE project_id = ? AND active = 1", (existing[0],)).fetchall()}
    project_id = int(existing[0]) if existing else pgr.create_project(
        student_id, title, str(payload.get("proposal_summary") or title),
        created_by=actor, start_date=datetime.now().date().isoformat(),
    )
    supervisors = [s for s in payload.get("supervisors") or [] if s.get("username")]
    share = round(1.0 / len(supervisors), 2) if supervisors else 0
    for sup in supervisors:
        if sup["username"] in team:
            continue
        role = sup.get("role") if sup.get("role") in ("primary", "secondary", "advisor") \
            else "secondary"
        pgr.add_supervisor(project_id, sup["username"], role, workload_fte=share,
                           start_date=datetime.now().date().isoformat())


HANDLERS = {
    "module_enrolments": module_enrolments,
    "finance": finance,
    "visa_monitoring": visa_monitoring,
    "accommodation": accommodation,
    "library": library,
    "student_account": student_account,
    "research_pgr": research_pgr,
}


def _record_failure(action_id: int, error: str) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE student_lifecycle_actions SET status = 'failed', "
            "attempts = attempts + 1, last_error = ? WHERE action_id = ?",
            (error[:500], action_id),
        )


def _reversed_history_ids(conn) -> set:
    if not _has_table(conn, "student_lifecycle_corrections"):
        return set()
    return {r[0] for r in conn.execute("SELECT history_id FROM student_lifecycle_corrections")}


def _record_superseded(action_id: int) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE student_lifecycle_actions SET status = 'completed', "
            "completed_at = CURRENT_TIMESTAMP, last_error = 'superseded by a reversal' "
            "WHERE action_id = ?", (action_id,))


def drain(limit: int = 100) -> dict[str, int]:
    """Run every pending (or failed) lifecycle action once."""
    with transaction() as conn:
        if not _has_table(conn, "student_lifecycle_actions"):
            return {"completed": 0, "failed": 0}
        rows = conn.execute(
            "SELECT action_id, target_system, history_id FROM student_lifecycle_actions "
            "WHERE status IN ('pending', 'failed') ORDER BY action_id LIMIT ?",
            (limit,),
        ).fetchall()
        reversed_ids = _reversed_history_ids(conn)
    done = failed = 0
    for action_id, target, history_id in ((int(r[0]), str(r[1]), r[2]) for r in rows):
        handler = HANDLERS.get(target)
        if handler is None:
            continue
        if history_id in reversed_ids:
            # The change was reversed before this area acted on it: acting
            # now (cancelling fees, telling the library) would be wrong.
            _record_superseded(action_id)
            continue
        try:
            if consume_action(action_id, target, handler):
                done += 1
        except Exception as exc:
            logger.warning("Lifecycle action %s (%s) failed: %s", action_id, target, exc)
            _record_failure(action_id, str(exc))
            failed += 1
    return {"completed": done, "failed": failed}


__all__ = ["HANDLERS", "drain"]
