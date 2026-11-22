"""The staff portal ("My Day"): one member of staff's day at a glance.

Everything is read from the areas that own it, filtered to the signed-in
person: their lessons today (with whether the register is taken), the form
they tutor, cover they are doing or that is arranged for them, homework and
marks waiting, assessment-point grades and mock marks still to enter, their
clubs today, and staff / whole-school events. Nothing here changes data -
each item opens the screen that does.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log

logger = logging.getLogger(__name__)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _safe(label: str, fn, default):
    try:
        return fn()
    except Exception:  # noqa: BLE001 - one area failing mustn't stop the page
        logger.exception("My Day section %s failed", label)
        return default


def _me(principal: Principal) -> dict[str, Any]:
    login = _safe("login", lambda: accounts.find_login(principal.username), None) or {}
    return {"email": (login.get("email") or "").lower(),
            "name": (login.get("display_name") or "").lower()}


def my_forms(principal: Principal) -> list[Any]:
    """Forms whose tutor or co-tutor is this person (matched on e-mail or name)."""
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    me = _me(principal)
    out = []
    for f in _safe("forms", FG.list_forms, []):
        email = (f.tutor_email or "").lower()
        names = {(f.tutor_name or "").lower(), (f.co_tutor_name or "").lower()} - {""}
        if (me["email"] and email == me["email"]) or (me["name"] and me["name"] in names) \
                or principal.username.lower() in names:
            out.append(f)
    return out


def lessons(principal: Principal, day: _dt.date | None = None) -> tuple[list, str]:
    """[(lesson, register taken?)] for my lessons on *day*, and the day's label."""
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    return _safe("lessons", lambda: AT.lessons_due(day or _today(),
                                                   teacher=principal.username), ([], ""))


def form_registers(principal: Principal, day: _dt.date | None = None) -> list[dict[str, Any]]:
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    d = day or _today()
    forms = my_forms(principal)
    if not forms:
        return []
    out = []
    for session in AT.SESSIONS:
        status = {(r.year_group, r.form_group.upper()): r
                  for r in _safe("registers", lambda s=session: AT.register_status(d, s), [])}
        for f in forms:
            r = status.get((f.year_group, f.name.upper()))
            out.append({"form": f, "session": session, "on_roll": r.on_roll if r else 0,
                        "marked": r.marked if r else 0,
                        "complete": bool(r and r.complete)})
    return out


def cover(principal: Principal, *, days: int = 7) -> dict[str, list]:
    """{doing: cover I'm down for, mine: cover arranged for my lessons}."""
    from education_system.systems.secondary.modules.curriculum.domain import cover as CV
    start = _today()
    end = start + _dt.timedelta(days=days)
    kw = {"date_from": start.isoformat(), "date_to": end.isoformat(),
          "include_cancelled": False}
    return {"doing": _safe("cover", lambda: CV.list_covers(cover=principal.username, **kw), []),
            "mine": _safe("my cover", lambda: CV.list_covers(absent=principal.username, **kw),
                          [])}


def marking(principal: Principal) -> dict[str, list]:
    """Homework handed in to mark, gradebook marks missing, assessment-point
    grades to enter and mock marks to enter - all mine only."""
    from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
    from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
    from education_system.systems.secondary.modules.curriculum.domain import homework as HW

    def points():
        out = []
        for pt in AP.list_points(status="Open"):
            for row in AP.completion(pt.point_id, teacher=principal.username):
                if row["done"] < row["pupils"]:
                    out.append((pt, row))
        return out
    return {"homework": _safe("hw", lambda: HW.to_mark(principal), []),
            "gradebook": _safe("gb", lambda: GB.missing_marks(principal), []),
            "points": _safe("points", points, []),
            "mocks": _safe("mocks", lambda: mock_marks(principal), [])}


def mock_marks(principal: Principal) -> list[tuple[Any, Any, int]]:
    """(series, paper, how many of my pupils have no mark) for mock series
    being marked."""
    from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
    out = []
    for s in MX.list_series():
        if s.status != "InProgress":
            continue
        for paper, missing in MX.missing_marks(s.series_id):
            mine = [p for p in missing if MX.teaches(principal, p.pupil_id, paper.subject_id,
                                                     s.academic_year)]
            if mine:
                out.append((s, paper, len(mine)))
    return out


def homework_set(principal: Principal, *, days: int = 7) -> list[Any]:
    """Homework I've set that is due in the next *days* days."""
    from education_system.systems.secondary.modules.curriculum.domain import homework as HW
    end = (_today() + _dt.timedelta(days=days)).isoformat()
    return [t for t in _safe("my hw", lambda: HW.my_homework(principal, status="Set"), [])
            if t.due_date <= end]


def clubs_today(principal: Principal, day: _dt.date | None = None) -> list[Any]:
    from education_system.systems.secondary.modules.curriculum.domain import enrichment as EN
    name = WEEKDAYS[(day or _today()).weekday()].lower()
    return [c for c in _safe("clubs", lambda: EN.my_clubs(principal), [])
            if (c.day_of_week or "").strip().lower() in (name, name[:3])]


def detentions_today(principal: Principal, day: _dt.date | None = None) -> list[Any]:
    """Detentions I'm supervising today, still to be marked."""
    from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
    return _safe("detentions", lambda: DT.supervising(principal, day), [])


def suspended_today(principal: Principal, day: _dt.date | None = None) -> list[Any]:
    """Pupils in my form(s) out today on a suspension or exclusion."""
    from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
    forms = my_forms(principal)
    if not forms:
        return []
    names = {n.upper() for f in forms for n in (f.name, f"{f.year_group}{f.name}")}
    return [c for c in _safe("suspended", lambda: EX.out_on(day), [])
            if (c.form_group or "").upper() in names]


def events(*, days: int = 7) -> list[Any]:
    from education_system.systems.secondary.modules.curriculum.domain import calendar_events as CAL
    start = _today()
    end = start + _dt.timedelta(days=days)
    rows = _safe("events", lambda: CAL.list_events(start=start.isoformat(),
                                                   end=end.isoformat()), [])
    return [e for e in rows if e.audience in ("All", "Staff") and e.status != "Draft"]


# ── Linked areas (safeguarding, absence, finance, communication, pastoral) ──
def safeguarding(principal: Principal) -> dict[str, int] | None:
    """New / urgent / overdue counts for a safeguarding lead (None otherwise)."""
    from education_system.systems.secondary.modules.safeguarding.domain import (
        safeguarding_reports as SGR,
    )
    return _safe("safeguarding", lambda: SGR.my_day(actor=principal), None)


def my_absence(principal: Principal) -> dict[str, list]:
    from education_system.systems.secondary.modules.staff.domain import staff_absence as SA
    return _safe("my absence", lambda: SA.my_absence(principal),
                 {"off_now": [], "requests": [], "rtw_due": []})


def expenses(principal: Principal) -> dict[str, list]:
    """{to_approve: claims waiting for me, to_fix: my drafts / rejected claims,
    overspends: budget lines I hold that are over}."""
    from education_system.systems.secondary.modules.finance.domain import budgets as B
    from education_system.systems.secondary.modules.finance.domain import expense_claims as X
    return {"to_approve": _safe("claims queue", lambda: X.approval_queue(principal), []),
            "to_fix": _safe("my claims", lambda: [c for c in X.my_claims(principal)
                                                  if c.status in ("Draft", "Rejected")], []),
            "overspends": _safe("overspends", lambda: B.overspends(actor=principal), [])}


def announcements(principal: Principal) -> dict[str, list]:
    from education_system.systems.secondary.modules.communication.domain import announcements as AN
    return {"active": _safe("announcements", lambda: AN.active_for(principal), []),
            "unread": _safe("unread", lambda: AN.unread_for(principal), []),
            "to_acknowledge": _safe("acknowledge",
                                    lambda: AN.needs_acknowledgement(principal), [])}


def parents_evenings(principal: Principal) -> list[tuple[Any, Any]]:
    from education_system.systems.secondary.modules.communication.domain import (
        parents_evenings as PE,
    )
    return _safe("parents evenings", lambda: PE.my_events(principal), [])


def pastoral(principal: Principal) -> dict[str, list]:
    """Attendance cases for my forms / year and wellbeing follow-ups due."""
    from education_system.systems.secondary.modules.attendance.domain import (
        attendance_concerns as AC,
    )
    from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
    return {"attendance_cases": _safe("attendance cases", lambda: AC.for_staff(principal), []),
            "wellbeing_follow_ups": _safe(
                "wellbeing", lambda: WB.follow_ups(actor=principal, include_future=False), [])}


def my_pupils_needs(principal: Principal) -> dict[str, list]:
    """SEND strategies and the medical care list for the pupils I teach."""
    from education_system.systems.secondary.modules.medical.domain import medical as M
    from education_system.systems.secondary.modules.send.domain import send as S
    return {"send": _safe("send", lambda: S.strategies(actor=principal, mine=True), []),
            "medical": _safe("medical", lambda: M.care_list(
                actor=principal, pupil_ids=sorted(S.my_pupil_ids(principal))), [])}


def leads_due(principal: Principal) -> dict[str, Any]:
    """For the SENCO / medical / pupil premium leads: reviews, deadlines and
    expiries due (None for a lead role this person doesn't hold)."""
    from education_system.systems.secondary.modules.medical.domain import medical as M
    from education_system.systems.secondary.modules.medical.domain import medical_common as MC
    from education_system.systems.secondary.modules.finance.domain import pupil_premium as PP
    from education_system.systems.secondary.modules.send.domain import send as S
    from education_system.systems.secondary.modules.send.domain import send_common as SC
    return {"send": _safe("send due", S.due, []) if SC.is_editor(principal) else None,
            "medical": _safe("medical due", M.due, []) if MC.is_editor(principal) else None,
            "pp_without_activities": _safe(
                "pp", lambda: PP.cohort_summary()["pp_without_activities"], 0)
            if PP.is_editor(principal) else None}


def on_trip_today(principal: Principal, day: _dt.date | None = None) -> list[Any]:
    """Pupils in my form(s) away on a trip today (so the register isn't chased)."""
    from education_system.systems.secondary.modules.trips.domain import trips as TR
    forms = my_forms(principal)
    if not forms:
        return []
    names = {n.upper() for f in forms for n in (f.name, f"{f.year_group}{f.name}")}
    return [b for b in _safe("trips", lambda: TR.on_trip((day or _today()).isoformat()), [])
            if (b.form_group or "").upper() in names]


def day(principal: Principal) -> dict[str, Any]:
    """Everything on the My Day page."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    activity_log.record("my_day.view", principal=principal)
    today_lessons, label = lessons(principal)
    return {"day": _today(), "label": label, "lessons": today_lessons,
            "forms": my_forms(principal), "registers": form_registers(principal),
            "cover": cover(principal), "marking": marking(principal),
            "homework_set": homework_set(principal), "clubs": clubs_today(principal),
            "detentions": detentions_today(principal),
            "suspended": suspended_today(principal),
            "events": events(),
            "safeguarding": safeguarding(principal), "absence": my_absence(principal),
            "expenses": expenses(principal), "announcements": announcements(principal),
            "parents_evenings": parents_evenings(principal),
            "pastoral": pastoral(principal), "needs": my_pupils_needs(principal),
            "leads_due": leads_due(principal),
            "trips": on_trip_today(principal),
            "children": _safe("children", lambda: PA.pupils_for(principal, "parent"), [])}
