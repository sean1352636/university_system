"""What the pupil and parent portals show (read by both the GUI and the CLI).

Every function takes the signed-in principal and a pupil id and checks the
link first (:func:`portal_accounts.require_pupil`), so a portal can never
read another child's record. Only what is meant for families is returned:
marked gradebook work, *published* assessment points, *released* mock
results, events for pupils / parents / the pupil's year (never drafts or
staff-only), and none of the staff notes, SEN or safeguarding details.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log

logger = logging.getLogger(__name__)

SECTIONS = ("Home", "Timetable", "Homework", "Attendance", "Grades", "Reports", "Exams",
            "Library", "Clubs", "Options", "Sixth Form", "Calendar", "My details", "Behaviour",
            "Messages", "Money", "Wellbeing")
#: Sections only pupils see (a parent can't check in on their child's behalf).
PUPIL_ONLY = frozenset({"Wellbeing"})

PermissionDenied = PA.PermissionDenied
ValidationError = PA.ValidationError
NotFound = PA.NotFound


def sections_for(principal: Principal) -> tuple[str, ...]:
    return tuple(x for x in SECTIONS if principal.is_student or x not in PUPIL_ONLY)


def kind_for(principal: Principal) -> str:
    return "pupil" if principal.is_student else "parent"


def pupils(principal: Principal) -> list[P.Pupil]:
    return PA.pupils_for(principal, kind_for(principal))


def _pupil(principal: Principal, pupil_id: int, section: str) -> P.Pupil:
    p = PA.require_pupil(principal, pupil_id, kind_for(principal))
    activity_log.record("portal.view", target=p.admission_no, principal=principal,
                        section=section, kind=kind_for(principal))
    return p


def _safe(label: str, fn, default):
    """One section failing (a table not created yet) mustn't stop the portal."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        logger.exception("Portal section %s failed", label)
        return default


# ── Sections ─────────────────────────────────────────────────────────

def timetable_today(pupil_id: int, day: _dt.date | None = None) -> tuple[list, str]:
    from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
    return TT.lessons_on(day or _today(), pupil_id=pupil_id)


def timetable(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """The pupil's week(s): {periods, weeks, grid {(week, day, period): [lesson]}}."""
    from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
    _pupil(principal, pupil_id, "timetable")
    lessons = _safe("timetable", lambda: TT.list_lessons(pupil_id=pupil_id), [])
    return {"periods": _safe("periods", TT.periods, []),
            "weeks": _safe("weeks", TT.cycle_weeks, 1),
            "this_week": _safe("week", lambda: TT.week_for(_today()), 1),
            "grid": TT.grid(lessons), "lessons": lessons}


def homework(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """{due: [(task, work)], done: [(task, work)], summary} - set homework only."""
    from education_system.systems.secondary.modules.curriculum.domain import homework as HW
    _pupil(principal, pupil_id, "homework")
    rows = _safe("homework", lambda: HW.for_pupil(pupil_id), [])
    tasks: dict[int, Any] = {}
    out_due, out_done = [], []
    for w in rows:
        t = tasks.get(w.task_id) or _safe("task", lambda: HW.get(w.task_id), None)
        if t is None:
            continue
        tasks[w.task_id] = t
        (out_due if w.status in ("Pending", "Missing") and t.status == "Set"
         else out_done).append((t, w))
    out_due.sort(key=lambda x: x[0].due_date)
    return {"due": out_due, "done": out_done,
            "summary": _safe("hw summary", lambda: HW.pupil_summary(pupil_id), None)}


def attendance(principal: Principal, pupil_id: int, *, days: int = 60) -> dict[str, Any]:
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    _pupil(principal, pupil_id, "attendance")
    start = P.academic_year_start(_today())
    summary = _safe("attendance", lambda: AT.pupil_summary(pupil_id, start, _today()), None)
    since = max(start, _today() - _dt.timedelta(days=days))
    marks = _safe("marks", lambda: AT.pupil_history(pupil_id, since, _today()), [])
    return {"summary": summary, "since": start, "recent": sorted(
        marks, key=lambda m: (m.date, m.session), reverse=True),
        "absences": [m for m in marks if AT.category_of(m.code) in ("authorised",
                                                                    "unauthorised")]}


def grades(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """Marked gradebook work this year: per-subject overview and each mark."""
    from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
    from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
    _pupil(principal, pupil_id, "grades")
    year = TG.current_year(_today())
    entries = _safe("entries", lambda: GB.list_entries(pupil_id=pupil_id, academic_year=year),
                    [])
    return {"overview": _safe("overview", lambda: GB.pupil_overview(pupil_id), []),
            "entries": [e for e in entries if e.status == "Marked"], "year": year}


def reports(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """Published assessment-point grades, targets with progress, and released
    mock results."""
    from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
    from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    _pupil(principal, pupil_id, "reports")

    def point():
        got = AP.for_pupil(pupil_id)
        return got if got and got[0].status == "Published" else None

    def mocks():
        rows = MX.results_for_pupil(pupil_id, released_only=True)
        if not rows:
            return None
        s = rows[0][0]
        return {"series": s, "subjects": MX.subject_results(s.series_id, pupil_id=pupil_id),
                "papers": [(p, r) for x, p, r in rows if x.series_id == s.series_id]}

    def targets():
        # A target's "now" grade can come from an unpublished assessment point
        # or an unreleased mock series: families don't see those yet.
        series = MX.list_series()
        points = AP.list_points()
        hidden = ({x.name for x in series if not x.released}
                  | {x.name for x in points if x.status != "Published"})
        hidden -= {x.name for x in series if x.released}
        hidden -= {x.name for x in points if x.status == "Published"}
        return [{**r, "current": None, "from": None, "status": "No data"}
                if r["from"] in hidden else r for r in TGR.progress(pupil_id=pupil_id)]
    def issued():
        from education_system.systems.secondary.modules.assessment.domain import (
            reports_to_parents as RP,
        )
        return RP.for_family(pupil_id)
    return {"point": _safe("point", point, None), "targets": _safe("targets", targets, []),
            "mocks": _safe("mocks", mocks, None), "issued": _safe("issued", issued, [])}


def school_report(principal: Principal, pupil_id: int, report_id: int) -> dict[str, Any]:
    """One issued report to parents (frozen as it was sent); a parent opening
    it is recorded."""
    from education_system.systems.secondary.modules.assessment.domain import (
        reports_to_parents as RP,
    )
    _pupil(principal, pupil_id, "school_report")
    got = RP.family_view(report_id, pupil_id, principal=principal)
    return {**got, "text": RP.render_text(got["content"])}


def acknowledge_report(principal: Principal, pupil_id: int, report_id: int):
    from education_system.systems.secondary.modules.assessment.domain import (
        reports_to_parents as RP,
    )
    _pupil(principal, pupil_id, "school_report")
    return RP.acknowledge(report_id, pupil_id, principal=principal)


def exams(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """The candidate number and statement of entry for each series that isn't
    archived: confirmed (Final) entries only - provisional plans stay with
    the school."""
    from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
    _pupil(principal, pupil_id, "exams")

    def build() -> dict[str, Any]:
        from education_system.systems.secondary.modules.examinations.domain import (
            exam_results as ER,
        )
        c = EE.candidate(pupil_id)
        out = []
        for s in EE.list_series():
            if s.status == "Archived":
                continue
            st = EE.statement(pupil_id, s.series_id)
            if st["entries"]:
                out.append(st)
        return {"candidate": c, "statements": out,
                "results": _safe("results", lambda: ER.released_for_pupil(pupil_id), [])}
    return _safe("exams", build, {"candidate": None, "statements": [], "results": []})


def behaviour(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """Entries the school has shared this year, positive points, house,
    reward levels, detentions (upcoming and past) and suspensions."""
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
    from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
    _pupil(principal, pupil_id, "behaviour")
    return _safe("behaviour", lambda: {**BH.for_family(pupil_id),
                                       "detentions": DT.for_family(pupil_id),
                                       "exclusions": EX.for_family(pupil_id)},
                 {"entries": [], "positive_points": 0, "house": None,
                  "next": {"points": 0, "next": None, "needed": 0}, "milestones": [],
                  "detentions": {"upcoming": [], "past": []}, "exclusions": []})


def library(principal: Principal, pupil_id: int) -> dict[str, Any]:
    from education_system.systems.secondary.modules.library.domain import library as LIB
    _pupil(principal, pupil_id, "library")
    return _safe("library", lambda: LIB.for_pupil(pupil_id),
                 {"out": [], "overdue": [], "holds": [], "total": 0})


def clubs(principal: Principal, pupil_id: int) -> list[tuple[Any, Any]]:
    """[(membership, club)] - current and waiting-list clubs."""
    from education_system.systems.secondary.modules.curriculum.domain import enrichment as EN
    _pupil(principal, pupil_id, "clubs")
    out = []
    for m in _safe("clubs", lambda: EN.for_pupil(pupil_id), []):
        if m.status == "Left":
            continue
        club = _safe("club", lambda: EN.get_club(m.club_id), None)
        out.append((m, club))
    return out


def options(principal: Principal, pupil_id: int) -> list[dict[str, Any]]:
    """Options rounds for the pupil's year: subjects, the pupil's choices,
    results once finalised, and whether choices can be made now."""
    from education_system.systems.secondary.modules.curriculum.domain import options as OPT
    pupil = _pupil(principal, pupil_id, "options")
    out = []
    for r in _safe("rounds", lambda: OPT.list_rounds(year_group=pupil.year_group), []):
        if r.status == "Draft":
            continue
        open_now = r.status == "Open" and not (r.closes_on
                                               and _today().isoformat() > r.closes_on)
        out.append({"round": r, "subjects": _safe("subjects", lambda: OPT.list_round_subjects(
            r.round_id), []), "guidance": _safe("guidance", lambda: OPT.guidance(r.round_id), {}),
            "rules": _safe("rules", lambda: OPT.list_rules(r.round_id), []),
            "choices": _safe("choices", lambda: OPT.get_choices(r.round_id, pupil_id), None),
            "allocations": _safe("alloc", lambda: OPT.allocations(r.round_id, pupil_id), [])
            if r.status == "Finalised" else [], "can_choose": open_now})
    return out


def submit_options(principal: Principal, pupil_id: int, round_id: int, choices: list[int],
                   reserves: list[int]) -> Any:
    from education_system.systems.secondary.modules.curriculum.domain import options as OPT
    _pupil(principal, pupil_id, "options")
    return OPT.submit_choices(round_id, pupil_id, choices, reserves, actor=principal)


def sixth_form(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """The pupil's three A-level choices for the sixth form, checked against
    the sixth form's entry requirements with their released results; once
    results are in, the courses they can choose from instead. ``can_choose``
    is True for the pupil themselves (parents only look)."""
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_choices as SC,
    )
    _pupil(principal, pupil_id, "sixth_form")
    st = SC.status(pupil_id)
    st["can_choose"] = principal.is_student and st["locked"] is None
    st["summary"] = SC.summary(st)
    return st


def choose_sixth_form(principal: Principal, pupil_id: int, courses: list[str]
                      ) -> dict[str, Any]:
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_choices as SC,
    )
    _pupil(principal, pupil_id, "sixth_form")
    if not principal.is_student:
        raise PermissionDenied("Only the pupil can choose their A-levels here.")
    return SC.save(pupil_id, courses, actor=principal)


def audiences_for(principal: Principal, pupil: P.Pupil) -> set[str]:
    who = "Pupils" if principal.is_student else "Parents"
    return {"All", who, f"Year {pupil.year_group}"}


def calendar(principal: Principal, pupil_id: int, *, days: int = 60) -> list[Any]:
    from education_system.systems.secondary.modules.curriculum.domain import calendar_events as CAL
    pupil = _pupil(principal, pupil_id, "calendar")
    want = audiences_for(principal, pupil)
    start = _today()
    end = start + _dt.timedelta(days=days)
    rows = _safe("calendar", lambda: CAL.list_events(start=start.isoformat(),
                                                     end=end.isoformat()), [])
    return [e for e in rows if e.audience in want and e.status != "Draft"]


def term_dates(principal: Principal, pupil_id: int) -> list[tuple[str, str, str]]:
    """(name, start, end) for this year's terms and holidays."""
    from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
    _pupil(principal, pupil_id, "calendar")

    def rows():
        y = AY.current_year()
        if y is None:
            return []
        out = [(t.name, t.start_date, t.end_date) for t in AY.list_terms(y.year_id)]
        out += [(b.name, b.start_date, b.end_date) for b in AY.list_breaks(y.year_id)
                if b.closes_school]
        return sorted(out, key=lambda x: x[1])
    return _safe("terms", rows, [])


def details(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """The pupil's own details, form and (for parents) the contacts on record."""
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    pupil = _pupil(principal, pupil_id, "details")
    out: dict[str, Any] = {"pupil": pupil, "form": _safe("form", lambda: FG.details_for(pupil),
                                                         {})}
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    acct = _safe("account", lambda: pupil_accounts.get_for_pupil(pupil_id), None)
    out["school_email"] = acct.school_email if acct and acct.status == "active" else None
    if not principal.is_student:
        out["contacts"] = _safe("contacts", lambda: C.list_for_pupil(pupil_id), [])
    return out


# ── Messages: announcements, letters home, parents' evenings ─────────

def announcements(principal: Principal) -> dict[str, list]:
    """Live announcements for this login, with which are unread and which
    still need an "I have read this"."""
    from education_system.systems.secondary.modules.communication.domain import announcements as AN
    return {"active": _safe("announcements", lambda: AN.active_for(principal), []),
            "unread": _safe("unread", lambda: AN.unread_for(principal), []),
            "to_acknowledge": _safe("acknowledge",
                                    lambda: AN.needs_acknowledgement(principal), [])}


def read_announcement(principal: Principal, announcement_id: int, *,
                      acknowledge: bool = False) -> None:
    from education_system.systems.secondary.modules.communication.domain import announcements as AN
    AN.mark_read(announcement_id, principal)
    if acknowledge:
        AN.acknowledge(announcement_id, principal)


def letters(principal: Principal, pupil_id: int) -> list[Any]:
    """Letters home about the child, with any reply slip (parents only)."""
    from education_system.systems.secondary.modules.communication.domain import letters as L
    _pupil(principal, pupil_id, "letters")
    if principal.is_student:
        return []
    return _safe("letters", lambda: L.for_family(principal, pupil_id), [])


def reply_to_letter(principal: Principal, recipient_id: int, reply: Any,
                    note: str | None = None) -> Any:
    from education_system.systems.secondary.modules.communication.domain import letters as L
    return L.reply_for_family(principal, recipient_id, reply, note)


def parents_evenings(principal: Principal, pupil_id: int) -> list[dict[str, Any]]:
    """Upcoming parents' evenings for the child's year: each teacher with the
    booking made or the free slots (parents only - pupils see nothing here)."""
    from education_system.systems.secondary.modules.communication.domain import (
        parents_evenings as PE,
    )
    _pupil(principal, pupil_id, "parents_evenings")
    if principal.is_student:
        return []
    return _safe("parents evenings", lambda: PE.family_overview(principal, pupil_id), [])


def book_parents_evening(principal: Principal, event_id: int, pupil_id: int,
                         teacher_key: str, slot_time: str) -> Any:
    from education_system.systems.secondary.modules.communication.domain import (
        parents_evenings as PE,
    )
    return PE.book_for_family(principal, event_id, pupil_id, teacher_key, slot_time)


def cancel_parents_evening(principal: Principal, booking_id: int) -> Any:
    from education_system.systems.secondary.modules.communication.domain import (
        parents_evenings as PE,
    )
    return PE.cancel_for_family(principal, booking_id)


def messages(principal: Principal, pupil_id: int) -> dict[str, Any]:
    _pupil(principal, pupil_id, "messages")
    return {"announcements": announcements(principal),
            "letters": letters(principal, pupil_id),
            "parents_evenings": parents_evenings(principal, pupil_id)}


# ── Money: trips and dinner money ────────────────────────────────────

_NO_DINNER = {"balance": "-", "balance_pence": 0, "overdrawn": False, "low": False,
              "fsm": False, "recent": []}


def trips(principal: Principal, pupil_id: int) -> list[dict[str, Any]]:
    from education_system.systems.secondary.modules.trips.domain import trips as TR
    _pupil(principal, pupil_id, "trips")
    return _safe("trips", lambda: TR.for_family(pupil_id), [])


def dinner_money(principal: Principal, pupil_id: int) -> dict[str, Any]:
    from education_system.systems.secondary.modules.finance.domain import dinner_money as DM
    _pupil(principal, pupil_id, "dinner_money")
    return _safe("dinner_money", lambda: DM.for_family(pupil_id), dict(_NO_DINNER))


# ── Wellbeing (the pupil checks in for themselves) ───────────────────

def wellbeing(principal: Principal, pupil_id: int) -> dict[str, Any]:
    from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
    pupil = _pupil(principal, pupil_id, "wellbeing")
    return {"surveys": _safe("surveys", lambda: WB.open_surveys_for(pupil), []),
            "can_check_in": principal.is_student,
            "scale": (WB.MIN_RATING, WB.MAX_RATING)}


def check_in(principal: Principal, pupil_id: int, data: dict[str, Any]) -> Any:
    from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
    return WB.self_check_in(principal, pupil_id, data)


def home(principal: Principal, pupil_id: int) -> dict[str, Any]:
    """Today at a glance: lessons, homework due this week, attendance, notices,
    library books due back."""
    _pupil(principal, pupil_id, "home")
    today = _today()
    lessons, label = _safe("today", lambda: timetable_today(pupil_id), ([], ""))
    hw = homework(principal, pupil_id)
    soon = (today + _dt.timedelta(days=7)).isoformat()
    lib = library(principal, pupil_id)
    att = attendance(principal, pupil_id, days=14)
    return {"day": today, "day_label": label, "lessons": lessons,
            "homework_due": [x for x in hw["due"] if x[0].due_date <= soon],
            "overdue_homework": [x for x in hw["due"] if x[0].due_date < today.isoformat()],
            "attendance": att["summary"], "events": calendar(principal, pupil_id, days=14),
            "books_due": [x for x in lib["out"] if x.due_date <= soon],
            "announcements": announcements(principal),
            "trips": trips(principal, pupil_id), "dinner": dinner_money(principal, pupil_id)}
