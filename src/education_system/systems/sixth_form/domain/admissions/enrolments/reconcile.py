"""Data check: drift between student records, enrolments and learning aims.

The student record, its enrolments and its learning aims are kept in
step by the lifecycle functions (``withdraw_enrolment``, ``learner_left``,
``rollover``…). Rows written before those existed, or changed by hand,
can disagree. :func:`check` reports every disagreement it can see and
changes nothing; :func:`fix` repairs the ones chosen — **only** through
the proper domain functions, so each repair lands in the enrolment
history, the aim change log and the leaver steps exactly as if staff had
done it on the screen:

=============================  =============================================
kind                           repaired by
=============================  =============================================
``left_with_live_enrolment``   ``leaving.learner_left`` (ILR reason 98 —
                               not known — on the record's leaving date)
``two_live_years``             ``enrolments.complete_enrolment`` on the
                               earlier year (its own aims only)
``superseded_live_enrolment``  ``complete_enrolment`` (Enrolled) or
                               ``withdraw_enrolment`` reason 98 (Pending)
``aim_without_live_enrolment`` ``learning_aims.complete_aim`` when the last
                               enrolment completed, else ``withdraw_aim``
``tutor_group_mismatch``       the enrolment tutor-group sync (membership
                               follows the current live enrolment)
=============================  =============================================

Some issues are report-only (``fixable`` False) — an enrolment naming a
tutor group that does not exist, say — because the right answer needs a
person.

Reading is open; :func:`fix` needs the enrolment writer capabilities
(``admissions`` or ``students.manage``).
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any, Iterable

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _enrolments,
)

logger = logging.getLogger(__name__)

LEFT_WITH_LIVE = "left_with_live_enrolment"
TWO_LIVE_YEARS = "two_live_years"
SUPERSEDED = "superseded_live_enrolment"
AIM_WITHOUT_ENROLMENT = "aim_without_live_enrolment"
TUTOR_GROUP_MISMATCH = "tutor_group_mismatch"

#: Every kind, in the order :func:`fix` repairs them: closing a leaver's
#: enrolments ends their aims too, so the aim check runs after.
KINDS: tuple[str, ...] = (LEFT_WITH_LIVE, TWO_LIVE_YEARS, SUPERSEDED,
                          AIM_WITHOUT_ENROLMENT, TUTOR_GROUP_MISMATCH)

KIND_LABELS: dict[str, str] = {
    LEFT_WITH_LIVE: "Left / not on roll but still enrolled",
    TWO_LIVE_YEARS: "Enrolled in two academic years at once",
    SUPERSEDED: "Earlier year still open after a later one",
    AIM_WITHOUT_ENROLMENT: "Active learning aim with no live enrolment",
    TUTOR_GROUP_MISMATCH: "Enrolment tutor group differs from membership",
}

#: ILR withdrawal reason used for a repair: 98 = not known.
REPAIR_REASON = "98"


@dataclass(frozen=True)
class Issue:
    kind: str
    student_id: str
    enrolment_id: int | None
    detail: str
    fix_hint: str
    aim_id: int | None = None
    fixable: bool = True

    @property
    def issue_id(self) -> str:
        """Stable id for :func:`fix` (kind, learner, enrolment, aim)."""
        return ":".join((self.kind, self.student_id,
                         "" if self.enrolment_id is None else str(self.enrolment_id),
                         "" if self.aim_id is None else str(self.aim_id)))

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)


# ── Reads ──────────────────────────────────────────────────────────

def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _s,
    )
    return _s


def _aims():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as _a,
    )
    return _a


def _tutor_groups():
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _tg,
    )
    return _tg


def _memberships() -> dict[str, str]:
    """student_id -> tutor group name, read in one pass."""
    tg = _tutor_groups()
    tg.init_db()
    with tg._connect() as conn:
        return {r["student_id"]: r["name"] for r in conn.execute(
            "SELECT m.student_id, g.name FROM tutor_group_students m "
            "JOIN tutor_groups g ON g.tutor_group_id = m.tutor_group_id")}


def _group_names() -> set[str]:
    return {g.name for g in _tutor_groups().list_groups()}


def _current(rows: list[Any]) -> Any | None:
    """The enrolments.current_enrolment rule over rows already read:
    newest academic year, an Enrolled row preferred."""
    if not rows:
        return None
    return sorted(rows, key=lambda e: (e.academic_year,
                                       e.status == "Enrolled"))[-1]


def _label(e: Any) -> str:
    return f"#{e.enrolment_id} {e.academic_year} Year {e.year_group} ({e.status})"


def check(*, student_id: str | None = None) -> list[Issue]:
    """Every drift found, across all learners or just *student_id*.
    Changes nothing."""
    st = _students()
    _enrolments.init_db()
    students = ([s for s in [st.get_student(student_id)] if s is not None]
                if student_id else st.list_students())
    enrols: dict[str, list[Any]] = {}
    for e in _enrolments.list_enrolments(student_id=student_id):
        enrols.setdefault(e.student_id, []).append(e)
    aims: dict[str, list[Any]] = {}
    for a in _aims().list_all_aims(status="Active"):
        if student_id is None or a.student_id == student_id:
            aims.setdefault(a.student_id, []).append(a)
    members = _memberships()
    groups = _group_names()

    issues: list[Issue] = []
    for s in students:
        rows = enrols.get(s.student_id, [])
        live = [e for e in rows if e.is_live]
        if s.status not in st.ON_ROLL_STATUSES:
            for e in live:
                issues.append(Issue(
                    LEFT_WITH_LIVE, s.student_id, e.enrolment_id,
                    f"{s.full_name} is {s.status} on the student record but "
                    f"enrolment {_label(e)} is still open",
                    "Close the learner's open enrolments as a leaver "
                    f"(ILR reason {REPAIR_REASON}, on "
                    f"{s.leaving_date or 'today'}); their aims end with them"))
        else:
            issues += _year_drift(s, rows, live)
        if not live:
            last = _current(rows)
            for a in aims.get(s.student_id, []):
                ended = (f"last enrolment {_label(last)}" if last is not None
                         else "no enrolment at all")
                done = last is not None and last.status == "Completed"
                issues.append(Issue(
                    AIM_WITHOUT_ENROLMENT, s.student_id,
                    last.enrolment_id if last is not None else None,
                    f"{a.label} (aim #{a.aim_id}) is Active but "
                    f"{s.full_name} has {ended}",
                    ("Complete the aim on the enrolment's completion date"
                     if done else "Withdraw the aim (reason: no live "
                     "enrolment) on the last day in learning"),
                    aim_id=a.aim_id))
        issues += _tutor_drift(s, rows, members, groups)
    return issues


def _year_drift(s: Any, rows: list[Any], live: list[Any]) -> list[Issue]:
    out: list[Issue] = []
    enrolled = sorted((e for e in live if e.status == "Enrolled"),
                      key=lambda e: e.academic_year)
    paired: set[int] = set()
    for i, e in enumerate(enrolled[:-1]):
        later = [o for o in enrolled[i + 1:] if o.academic_year > e.academic_year]
        if not later:
            continue
        paired.add(e.enrolment_id)
        started = _any_started(later)
        out.append(Issue(
            TWO_LIVE_YEARS, s.student_id, e.enrolment_id,
            f"{s.full_name} is Enrolled in {_label(e)} and in "
            + ", ".join(_label(o) for o in later),
            (f"Complete {e.academic_year} (aims running on stay with the "
             "later year)") if started else _FUTURE_HINT,
            fixable=started))
    for e in live:
        if e.enrolment_id in paired:
            continue
        later = [o for o in rows if o.academic_year > e.academic_year
                 and o.enrolment_id != e.enrolment_id]
        if not later:
            continue
        started = _any_started(later)
        hint = (f"Complete {e.academic_year}" if e.status == "Enrolled"
                else f"Withdraw the pending {e.academic_year} enrolment "
                     f"(ILR reason {REPAIR_REASON})")
        out.append(Issue(
            SUPERSEDED, s.student_id, e.enrolment_id,
            f"{_label(e)} is still open though {s.full_name} already has "
            + ", ".join(_label(o) for o in later),
            hint if started else _FUTURE_HINT, fixable=started))
    return out


#: When the later year has not begun, which row is wrong (an early
#: rollover, or a mistaken future enrolment) is a person's call.
_FUTURE_HINT = ("The later year has not started yet: finish this year "
                "(Rollover at year end) or withdraw the future enrolment "
                "if it was made by mistake")


def _any_started(rows: list[Any]) -> bool:
    """Whether any of *rows*' academic years has begun."""
    today = _dt.date.today().isoformat()
    for o in rows:
        try:
            first, _last = _enrolments.academic_year_dates(o.academic_year)
        except Exception:  # noqa: BLE001 — a malformed year counts as begun
            return True
        if first <= today:
            return True
    return False


def _tutor_drift(s: Any, rows: list[Any], members: dict[str, str],
                 groups: set[str]) -> list[Issue]:
    if s.status not in _students().ON_ROLL_STATUSES:
        return []
    cur = _current(rows)
    if cur is None or not cur.is_live:
        return []
    text = (cur.tutor_group or "").strip()
    member = members.get(s.student_id)
    if not text:
        return []
    if text not in groups:
        return [Issue(
            TUTOR_GROUP_MISMATCH, s.student_id, cur.enrolment_id,
            f"Enrolment {_label(cur)} names tutor group {text!r}, which "
            "does not exist"
            + (f" (member of {member})" if member else ""),
            "Edit the enrolment to a real tutor group (or create the group)",
            fixable=False)]
    if member == text:
        return []
    return [Issue(
        TUTOR_GROUP_MISMATCH, s.student_id, cur.enrolment_id,
        f"Enrolment {_label(cur)} says tutor group {text} but "
        + (f"{s.full_name} is a member of {member}" if member
           else f"{s.full_name} is in no tutor group"),
        f"Move the learner into {text} (the current enrolment's group)")]


def summary(issues: Iterable[Issue] | None = None) -> dict[str, int]:
    """kind -> number of issues."""
    out = {k: 0 for k in KINDS}
    for i in (check() if issues is None else issues):
        out[i.kind] = out.get(i.kind, 0) + 1
    return out


# ── Fixes ──────────────────────────────────────────────────────────

def _today() -> str:
    return _dt.date.today().isoformat()


def _not_after_today(day: str | None) -> str:
    today = _today()
    return min(day, today) if day else today


def fix(selection: Iterable[str] | None = None, *,
        kinds: Iterable[str] | None = None,
        issues: list[Issue] | None = None) -> list[str]:
    """Repair the chosen issues; returns one line per outcome.

    *selection* is issue ids (:attr:`Issue.issue_id`) and/or kind names;
    *kinds* is kinds only. With neither, nothing is changed. The check is
    re-run first (or *issues* given) so a stale id is reported, not
    acted on. Report-only issues are listed as skipped.
    """
    _enrolments._require_writer("repairing enrolment data")
    wanted = {str(x) for x in (selection or ())}
    wanted_kinds = {k for k in wanted if k in KINDS} | set(kinds or ())
    wanted_ids = wanted - set(KINDS)
    unknown = set(kinds or ()) - set(KINDS)
    if unknown:
        raise _enrolments.ValidationError(
            f"Unknown check(s): {', '.join(sorted(unknown))}")
    found = check() if issues is None else issues
    chosen = [i for i in found
              if i.kind in wanted_kinds or i.issue_id in wanted_ids]
    lines: list[str] = []
    for missing in sorted(wanted_ids - {i.issue_id for i in found}):
        lines.append(f"{missing}: no longer found — nothing to do")
    handled_leavers: set[str] = set()
    for kind in KINDS:
        for issue in (i for i in chosen if i.kind == kind):
            if not issue.fixable:
                lines.append(f"{issue.student_id}: skipped (needs a person) — "
                             f"{issue.detail}")
                continue
            try:
                lines += _FIXERS[kind](issue, handled_leavers)
            except Exception as exc:  # noqa: BLE001 — reported per issue
                logger.exception("Reconcile fix %s failed", issue.issue_id)
                lines.append(f"{issue.student_id}: not fixed — {exc}")
    logger.info("Enrolment reconcile: %d issue(s) chosen, %d line(s)",
                len(chosen), len(lines))
    return lines


def _fix_leaver(issue: Issue, done: set[str]) -> list[str]:
    if issue.student_id in done:
        return []
    done.add(issue.student_id)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        leaving,
    )
    s = _students().get_student(issue.student_id)
    day = _not_after_today(s.leaving_date if s is not None else None)
    res = leaving.learner_left(
        issue.student_id, leaving_date=day, reason_code=REPAIR_REASON,
        detail="Data check: the student record had already left")
    return [f"{issue.student_id}: {line}" for line in res.lines()] or [
        f"{issue.student_id}: nothing was open"]


def _get_live(issue: Issue) -> Any | None:
    e = _enrolments.get_enrolment(int(issue.enrolment_id or 0))
    return e if e is not None and e.is_live else None


def _fix_earlier_year(issue: Issue, _done: set[str]) -> list[str]:
    e = _get_live(issue)
    if e is None:
        return [f"{issue.student_id}: enrolment #{issue.enrolment_id} is no "
                "longer open — nothing to do"]
    _first, last = _enrolments.academic_year_dates(e.academic_year)
    if e.status == "Enrolled":
        out, problems = _enrolments.complete_enrolment(
            e.enrolment_id, completed_on=_not_after_today(last))
        return ([f"{issue.student_id}: completed {_label(out)}"]
                + [f"{issue.student_id}: aim — {p}" for p in problems])
    day = _not_after_today(last)
    if e.start_date and day < e.start_date:
        day = e.start_date
    w = _enrolments.withdraw_enrolment(
        e.enrolment_id, withdrawal_date=day, reason=REPAIR_REASON,
        detail="Data check: superseded by a later academic year",
        update_student=False)
    return ([f"{issue.student_id}: withdrew {_label(w.enrolment)} "
             f"({len(w.aims_ended)} aim(s) ended)"]
            + [f"{issue.student_id}: aim — {p}" for p in w.aim_problems])


def _fix_aim(issue: Issue, _done: set[str]) -> list[str]:
    aims = _aims()
    aim = aims.get_aim(int(issue.aim_id or 0))
    if aim is None or aim.status != "Active":
        return [f"{issue.student_id}: aim #{issue.aim_id} is no longer "
                "active — nothing to do"]
    last = (_enrolments.get_enrolment(issue.enrolment_id)
            if issue.enrolment_id else None)
    from education_system.systems.sixth_form.domain.admissions import _guard
    who = _guard.actor()
    if last is not None and last.status == "Completed":
        end = max(aim.start_date, _not_after_today(last.completed_at))
        aims.complete_aim(aim.aim_id, end_date=end, recorded_by=who)
        return [f"{issue.student_id}: completed {aim.label} on {end}"]
    s = _students().get_student(issue.student_id)
    end_hint = (last.withdrawal_date if last is not None
                and last.status == "Withdrawn" else None) or (
        s.leaving_date if s is not None else None)
    end = max(aim.start_date, _not_after_today(end_hint))
    chk = aims.withdraw_aim(
        aim.aim_id, effective_date=end,
        reason="Data check: no live enrolment", approved_by=who or "system",
        recorded_by=who)
    return [f"{issue.student_id}: withdrew {aim.label} on {end}"
            + ("" if chk.met else " (before the funding qualifying period)")]


def _fix_tutor_group(issue: Issue, _done: set[str]) -> list[str]:
    note = _enrolments._sync_tutor_membership(issue.student_id)
    return [f"{issue.student_id}: {note}" if note else
            f"{issue.student_id}: tutor group not changed — check the "
            "enrolment's group"]


_FIXERS = {
    LEFT_WITH_LIVE: _fix_leaver,
    TWO_LIVE_YEARS: _fix_earlier_year,
    SUPERSEDED: _fix_earlier_year,
    AIM_WITHOUT_ENROLMENT: _fix_aim,
    TUTOR_GROUP_MISMATCH: _fix_tutor_group,
}
