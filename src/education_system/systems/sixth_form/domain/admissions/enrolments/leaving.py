"""What happens to a learner's enrolments when the student record says
they have left.

``students.withdraw_student`` (left without moving on) and
``transfers.mark_transferred`` (moved on, usually to university) both end
here, so leaving through the Student Directory does the same as
withdrawing from the Enrolment screen:

* every live (Enrolled / Pending) enrolment is closed — a Year 13 learner
  leaving in the summer term **completes** (aims completed), anyone else
  is **withdrawn** through :func:`enrolments.withdraw_enrolment` with an
  ILR reason, so their learning aims end on the leaving date;
* the leaver steps owned by other areas (class groups, exam entries,
  bursary, free meals) run through :mod:`leaver_effects`.

The reverse — :func:`enrolments.withdraw_enrolment` on a learner's last
live enrolment — calls ``students.withdraw_student``, which comes back
here and finds nothing left open.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _enrolments,
)

logger = logging.getLogger(__name__)

#: ILR reason used when the student record gives none.
UNKNOWN_REASON = "98"
#: ILR reason for a learner moving on to another provider.
TRANSFERRED_REASON = "2"

#: A Year 13 learner leaving on or after this day of the last year of the
#: course (month, day) has finished, rather than withdrawn.
SUMMER_TERM_FROM: tuple[int, int] = (5, 1)


@dataclass
class LeaverResult:
    withdrawn: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        return ([f"Enrolment withdrawn: {x}" for x in self.withdrawn]
                + [f"Enrolment completed: {x}" for x in self.completed]
                + self.effects + [f"Problem: {x}" for x in self.problems])


def finishing(e: _enrolments.Enrolment, leaving_date: str) -> bool:
    """A Year 13 learner leaving in the summer term of their year."""
    if e.year_group != 13:
        return False
    _first, last = _enrolments.academic_year_dates(e.academic_year)
    from_day = _dt.date(int(last[:4]), *SUMMER_TERM_FROM).isoformat()
    return leaving_date >= from_day


def check_allowed() -> None:
    """Raise ``AccessDenied`` before anything changes when the signed-in
    user can't close enrolments. Nobody signed in (a background job, the
    university transfer drainer) is allowed: those run as the system."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    if _guard.actor() is None:
        return
    _enrolments._require_writer("closing a leaver's enrolments")


def learner_left(student_id: str, *, leaving_date: str | None,
                 reason_code: str | None = None, detail: str | None = None,
                 completing: bool | None = None) -> LeaverResult:
    """Close the learner's live enrolments and run the leaver steps.

    ``completing`` forces Completed (True) or Withdrawn (False); None
    decides per enrolment with :func:`finishing`.
    """
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    day = leaving_date or _dt.date.today().isoformat()
    code = (reason_code or "").strip() or UNKNOWN_REASON
    result = LeaverResult()

    def close() -> None:
        for e in _enrolments.list_for_student(student_id):
            if not e.is_live:
                continue
            label = f"{e.academic_year} Year {e.year_group}"
            try:
                done = completing if completing is not None \
                    else finishing(e, day)
                if done and e.status == "Enrolled":
                    _out, problems = _enrolments.complete_enrolment(
                        e.enrolment_id, completed_on=day)
                    result.completed.append(label)
                    result.problems += problems
                else:
                    w = _enrolments.withdraw_enrolment(
                        e.enrolment_id, withdrawal_date=day, reason=code,
                        detail=detail, update_student=False)
                    result.withdrawn.append(
                        f"{label} ({_enrolments.withdrawal_reason_label(code)}"
                        f", {len(w.aims_ended)} aim(s) ended)")
                    result.problems += w.aim_problems
            except Exception as exc:  # noqa: BLE001 — reported per enrolment
                logger.exception("Closing enrolment #%d of leaver %s",
                                 e.enrolment_id, student_id)
                result.problems.append(f"{label}: {exc}")

    if _guard.actor() is None:
        with _guard.system_actor("student leaving",
                                 (access.STUDENTS_MANAGE,)):
            close()
    else:
        close()

    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            leaver_effects,
        )
        result.effects = leaver_effects.on_left(student_id, day)
    except Exception as exc:  # noqa: BLE001 — reported, never blocks leaving
        logger.exception("Leaver steps for %s", student_id)
        result.problems.append(f"Leaver steps not run: {exc}")
    logger.info("Leaver %s on %s: %d withdrawn, %d completed, %d problem(s)",
                student_id, day, len(result.withdrawn), len(result.completed),
                len(result.problems))
    return result
