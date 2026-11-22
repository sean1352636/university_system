"""Learner-safe reads shared by the student portal and the parent portal.

Every function takes a bare ``student_id`` and returns plain dicts. They
do **no** scoping of their own — that is the caller's job, and both
callers do it before arriving here:

* the student portal only ever passes ``principal.student_id``;
* the parent portal passes a child only after
  :func:`.parent_portal.is_linked` has confirmed the link.

What is deliberately left out or filtered:

* exam results are read with ``released_only=True`` — a results-day
  embargo holds here whatever the signed-in role;
* predicted grades have no "shareable" flag of their own, so the only
  predictions shown are those on the learner's latest *published*
  report card (approved by the head of sixth form) — see
  :func:`report_cards.published_predictions`. If a share flag column is
  ever added to ``predicted_grades`` it is honoured as well;
* coursework marks only once released (``assignments_feedback``);
* no staff-only notes, safeguarding, medical or internal workflow state.

Each section is independent: one failing module costs that section, not
the page (the caller shows "unavailable").
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as db

logger = logging.getLogger(__name__)

#: Columns that, if ever added to ``predicted_grades``, mark a row as
#: shareable with the learner and their parents.
_PREDICTION_SHARE_COLUMNS: tuple[str, ...] = (
    "shared_with_student", "shareable", "student_visible",
    "visible_to_student", "share_with_student",
)


def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(paths.SIXTH_FORM_STUDENTS_DB))
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _today() -> str:
    return _dt.date.today().isoformat()


# ── Identity ────────────────────────────────────────────────────────

def student_identity(student_id: str) -> dict[str, Any]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    s = _students.get_student(student_id)
    if s is None:
        raise LookupError(f"No student {student_id}")
    tutor_group = None
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT g.name, g.tutor FROM tutor_group_students t
                     JOIN tutor_groups g ON g.tutor_group_id = t.tutor_group_id
                    WHERE t.student_id = ?""", (student_id,)).fetchone()
        if r:
            tutor_group = {"name": r["name"], "tutor": r["tutor"]}
    except db.Error:
        logger.debug("Tutor group unavailable for %s", student_id, exc_info=True)
    return {"student_id": s.student_id, "full_name": s.full_name,
            "email": s.email, "status": s.status, "tutor_group": tutor_group}


# ── Timetable ───────────────────────────────────────────────────────

def timetable(student_id: str) -> list[dict[str, Any]]:
    """The learner's weekly lessons, Monday period 1 first."""
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    slots = _tt.list_slots(student_id=student_id)
    if not slots:
        return []
    group_ids = sorted({s.group_id for s in slots})
    info: dict[int, db.Row] = {}
    with _connect() as conn:
        marks = ",".join("?" * len(group_ids))
        for r in conn.execute(
                f"""SELECT g.group_id, g.group_name,
                           COALESCE(NULLIF(g.teacher, ''), c.teacher) AS teacher,
                           c.subject, c.title, g.room
                      FROM class_groups g
                      LEFT JOIN courses c ON c.course_id = g.course_id
                     WHERE g.group_id IN ({marks})""", group_ids):  # DBW001: only placeholders are interpolated
            info[r["group_id"]] = r
    out = []
    for s in slots:
        g = info.get(s.group_id)
        out.append({
            "day": s.day, "day_name": _tt.day_name(s.day), "period": s.period,
            "start_time": s.start_time or _tt.DEFAULT_PERIOD_TIMES.get(s.period, ("", ""))[0],
            "end_time": s.end_time or _tt.DEFAULT_PERIOD_TIMES.get(s.period, ("", ""))[1],
            "subject": (g["subject"] or g["title"]) if g else "—",
            "group": g["group_name"] if g else str(s.group_id),
            "teacher": g["teacher"] if g else None,
            "room": s.room or (g["room"] if g else None),
        })
    out.sort(key=lambda d: (d["day"], d["period"]))
    return out


# ── Attendance ──────────────────────────────────────────────────────

def attendance(student_id: str, *, days: int = 120) -> dict[str, Any]:
    """Headline % plus the individual marks behind it (newest first)."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    start = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    summary = _att.summary_for_student(student_id, date_from=start)
    year = _att.summary_for_student(student_id)
    records = _att.list_records(student_id=student_id, date_from=start)
    subjects: dict[int, str] = {}
    slot_ids = sorted({r.slot_id for r in records if r.slot_id})
    if slot_ids:
        with _connect() as conn:
            marks = ",".join("?" * len(slot_ids))
            try:
                for r in conn.execute(
                        f"""SELECT t.slot_id, COALESCE(c.subject, g.group_name) AS subj
                              FROM timetable_slots t
                              JOIN class_groups g ON g.group_id = t.group_id
                              LEFT JOIN courses c ON c.course_id = g.course_id
                             WHERE t.slot_id IN ({marks})""", slot_ids):  # DBW001: only placeholders are interpolated
                    subjects[r["slot_id"]] = r["subj"]
            except db.OperationalError:
                pass
    return {
        "days": days,
        "percentage": summary.percentage,
        "overall_percentage": year.percentage,
        "counts": {"Present": summary.present, "Late": summary.late,
                   "Absent": summary.absent, "Authorised": summary.authorised},
        "marks": [{"date": r.date, "session": r.session,
                   "subject": subjects.get(r.slot_id, "—"),
                   "status": r.status, "code": r.code,
                   "minutes_late": r.minutes_late} for r in records],
    }


# ── Learning aims, grades and results ───────────────────────────────

def learning_aims(student_id: str) -> list[dict[str, Any]]:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as _aims,
    )
    return [{"subject": a.subject, "qualification_type": a.qualification_type,
             "awarding_body": a.awarding_body, "academic_year": a.academic_year,
             "start_date": a.start_date, "planned_end_date": a.planned_end_date,
             "status": a.status} for a in _aims.list_aims(student_id)]


def released_results(student_id: str) -> list[dict[str, Any]]:
    """Exam results the learner has had released — never embargoed ones."""
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _er,
    )
    return [{"subject": r.subject, "board": r.exam_board,
             "paper": r.paper_title or r.paper_code, "season": r.season,
             "year": r.year, "grade": r.result.grade, "marks": r.result.marks,
             "ums": r.result.ums, "released_at": r.result.released_at}
            for r in _er.results_for_student(student_id, released_only=True)]


def _flagged_predictions(student_id: str) -> dict[str, str]:
    """Predictions explicitly marked shareable, if the table has a flag."""
    try:
        with _connect() as conn:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(predicted_grades)")}
            flag = next((c for c in _PREDICTION_SHARE_COLUMNS if c in cols), None)
            if flag is None:
                return {}
            return {r["subject"]: r["grade"] for r in conn.execute(
                f"SELECT subject, grade FROM predicted_grades "  # DBW001: flag is from a fixed allow-list
                f"WHERE student_id=? AND {flag}=1", (student_id,))}
    except db.Error:
        return {}


def shareable_predictions(student_id: str) -> dict[str, str]:
    from education_system.systems.sixth_form.domain.assessment.report_cards import (
        report_cards as _rc,
    )
    out = dict(_rc.published_predictions(student_id))
    out.update(_flagged_predictions(student_id))
    return out


def grades(student_id: str) -> list[dict[str, Any]]:
    """Per subject: target grades, current working grade, shareable prediction."""
    from education_system.systems.sixth_form.domain.assessment.target_setting import (
        target_setting as _ts,
    )
    predictions = shareable_predictions(student_id)
    rows: dict[str, dict[str, Any]] = {}
    for t in _ts.list_targets(student_id=student_id):
        rows[t.subject_name] = {
            "subject": t.subject_name, "target": t.mte_grade,
            "aspirational": t.aspirational_grade, "current": t.current_grade,
            "status": t.status, "predicted": predictions.get(t.subject_name)}
    for subject, grade in predictions.items():
        rows.setdefault(subject, {"subject": subject, "target": None,
                                  "aspirational": None, "current": None,
                                  "status": None, "predicted": grade})
    return sorted(rows.values(), key=lambda d: d["subject"])


# ── Coursework and homework ─────────────────────────────────────────

def coursework(student_id: str) -> list[dict[str, Any]]:
    """Assignments set to the learner, marks only once released to them."""
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_feedback as _fb,
    )
    from education_system.systems.sixth_form.domain.academics.assignments import (
        store as assignments_store,
        submissions as assignments_submissions,
    )
    today = _today()
    out = []
    for sub in assignments_store.list_submissions(student_id=student_id):
        a = assignments_store.get_assignment(sub.assignment_id)
        if a is None or (a.status == "Draft" and not a.published_on):
            continue
        due = assignments_submissions.effective_due_date(sub, a)
        visible = False
        try:
            visible = _fb.is_visible_to_student(sub, a, today=today)
        except Exception:
            logger.debug("Release state unavailable for #%s", sub.submission_id,
                         exc_info=True)
        out.append({
            "kind": "Assignment", "title": a.title, "subject": a.subject_name,
            "teacher": a.teacher, "due_date": due, "status": sub.status,
            "submitted": sub.is_done, "overdue": bool(due and due < today
                                                      and not sub.is_done),
            "mark": (sub.grade or (f"{sub.marks}/{a.max_marks}" if sub.marks is not None
                                   and a.max_marks else sub.marks)) if visible else None,
            "feedback": sub.feedback if visible else None,
        })
    out.extend(_homework(student_id))
    out.sort(key=lambda d: d["due_date"] or "9999-12-31")
    return out


def _homework(student_id: str) -> list[dict[str, Any]]:
    from education_system.systems.sixth_form.domain.academics.homework import (
        homework as _hw,
    )
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    groups = {g.group_id: g for g in _cg.groups_for_student(student_id)}
    subs = {s.assignment_id: s for s in _hw.list_submissions(student_id=student_id)}
    today = _today()
    out = []
    for gid, g in groups.items():
        for a in _hw.list_assignments(group_id=gid):
            sub = subs.get(a.assignment_id)
            done = bool(sub and sub.status in ("Submitted", "Late", "Excused"))
            out.append({
                "kind": "Homework", "title": a.title, "subject": g.group_name,
                "teacher": g.teacher, "due_date": a.due_date,
                "status": sub.status if sub else "Set", "submitted": done,
                "overdue": bool(a.due_date and a.due_date < today and not done),
                "mark": (f"{sub.marks}/{a.max_marks}" if sub and sub.marks is not None
                         and a.max_marks else (sub.marks if sub else None)),
                "feedback": sub.feedback if sub else None,
            })
    return out


# ── Report cards ────────────────────────────────────────────────────

def report_cards(student_id: str) -> list[dict[str, Any]]:
    from education_system.systems.sixth_form.domain.assessment.report_cards import (
        report_cards as _rc,
    )
    return _rc.published_cards_for_student(student_id)


def report_card_text(student_id: str, card_id: int) -> str:
    from education_system.systems.sixth_form.domain.assessment.report_cards import (
        report_cards as _rc,
    )
    return _rc.published_text(student_id, card_id)


# ── UCAS ────────────────────────────────────────────────────────────

def ucas(student_id: str) -> dict[str, Any] | None:
    """Application status, choices, pipeline stages and deadlines.

    Each choice also carries its offer terms, structured conditions (where
    the university issued them, or staff entered them in Offers),
    reply-by date and decision date; ``tracker`` is the step-by-step view
    of the move to university (:func:`ucas_tracker`). While the learner's
    results are embargoed, results-day outcomes on the Firm / Insurance
    choices are held back (:func:`_embargo`).
    """
    from education_system.systems.sixth_form.domain.progression.university import (
        ucas as _ucas,
        workflow as _wf,
    )
    app = _ucas.get_application_for_student(student_id)
    if app is None:
        return None
    raw_choices = _ucas.list_choices(app.application_id)
    embargo = _embargo(student_id, _results_year(app, raw_choices))
    choices = [_choice_view(c, embargo) for c in raw_choices]
    pipeline = None
    try:
        pipeline = _wf.get_pipeline(student_id, app.cycle_year)
    except Exception:
        logger.debug("UCAS pipeline unavailable for %s", student_id, exc_info=True)
    deadline = None
    try:
        from education_system.systems.sixth_form.domain.progression.university import (
            deadlines as _dl,
        )
        d = _dl.application_deadline(app.application_id)
        deadline = {"deadline": d.deadline.isoformat(), "reason": d.reason,
                    "internal_date": d.internal_date.isoformat(),
                    "next": f"{d.next_key} {d.next_deadline.isoformat()}",
                    "state": d.state, "days_to_internal": d.days_to_internal,
                    "outstanding": list(d.outstanding)}
    except Exception:
        logger.debug("UCAS deadline unavailable for %s", student_id, exc_info=True)
    tracker = None
    try:
        tracker = ucas_tracker(student_id, _app=app, _choices=raw_choices,
                               _embargo_state=embargo)
    except Exception:
        logger.debug("UCAS tracker unavailable for %s", student_id, exc_info=True)
    return {"cycle_year": app.cycle_year, "status": app.status,
            "ucas_id": app.ucas_id, "submitted_at": app.submitted_at,
            "choices": choices, "pipeline": pipeline, "deadline": deadline,
            "tracker": tracker, "results_embargoed": embargo["active"]}


# ── UCAS: offer detail and the move-to-university tracker ───────────

#: Outcomes UCAS settles on results day: while results are embargoed these
#: on a Firm / Insurance choice would tell the learner how they did.
_RESULTS_DAY_DECISIONS = ("Unconditional Offer", "Rejected")
_HELD = "Held until your results are released"


def _results_year(app, choices) -> int:
    """The summer whose results decide the offers: the Firm choice's entry
    year, else the application's cycle year."""
    firm = next((c for c in choices if c.final_decision == "Firm"), None)
    year = getattr(firm, "entry_year", None) or app.cycle_year
    try:
        return int(year)
    except (TypeError, ValueError):
        return _dt.date.today().year


def _embargo(student_id: str, year: int) -> dict[str, Any]:
    """``{"active", "year", "any_results", "released"}`` — whether any of
    the learner's results for *year* are still embargoed (exists but not
    visible to them)."""
    out = {"active": False, "year": year, "any_results": False, "released": False}
    try:
        from education_system.systems.sixth_form.domain.assessment.exam_results import (
            exam_results as _er,
        )
        everything = _er.results_for_student(student_id, year=year, released_only=False)
        visible = _er.results_for_student(student_id, year=year, released_only=True)
    except Exception:
        logger.debug("Exam results unavailable for %s", student_id, exc_info=True)
        return out
    out["any_results"] = bool(everything)
    out["released"] = bool(visible) and len(visible) == len(everything)
    out["active"] = len(everything) > len(visible)
    return out


def _condition_text(c: Any) -> str:
    if isinstance(c, dict) and c.get("kind"):
        from education_system.platform.cross_system import (
            offer_conditions as _oc,
        )
        try:
            return _oc.describe(c)
        except Exception:
            pass
    if isinstance(c, dict):
        return str(c.get("description") or c.get("text") or ", ".join(
            f"{k}: {v}" for k, v in c.items() if v not in (None, "")))
    return str(c)


def _offer_conditions(choice) -> list[str]:
    """Structured conditions: those the university published on the choice,
    else the grade requirement / alternative recorded in Offers."""
    published = getattr(choice, "conditions", None)
    if isinstance(published, list) and published:
        return [t for t in (_condition_text(c) for c in published) if t]
    try:
        from education_system.systems.sixth_form.domain.progression.university import (
            offers as _offers,
        )
        details = _offers.get_details_for_choice(choice.choice_id)
    except Exception:
        logger.debug("Offer details unavailable for choice %s", choice.choice_id,
                     exc_info=True)
        details = None
    if details is None:
        return []
    out = []
    if details.grade_requirement:
        out.append(f"Grades: {details.grade_requirement}")
    if details.grade_alternative:
        out.append(f"Or: {details.grade_alternative}")
    if details.scholarship:
        out.append(f"Scholarship: {details.scholarship}")
    return out


def _reply_by(choice) -> str | None:
    if getattr(choice, "reply_by", None):
        return choice.reply_by
    try:
        from education_system.systems.sixth_form.domain.progression.university import (
            offers as _offers,
        )
        details = _offers.get_details_for_choice(choice.choice_id)
        return details.reply_deadline if details else None
    except Exception:
        return None


def _held_back(choice, embargo: dict[str, Any]) -> bool:
    """A Firm / Insurance outcome settled in the results summer, while the
    learner's results are still embargoed."""
    if not embargo["active"] or choice.final_decision not in ("Firm", "Insurance"):
        return False
    if choice.decision_status not in _RESULTS_DAY_DECISIONS:
        return False
    when = str(getattr(choice, "decided_at", None) or choice.updated_at or "")[:10]
    return when >= f"{embargo['year']:04d}-07-01"


def _choice_view(choice, embargo: dict[str, Any]) -> dict[str, Any]:
    held = _held_back(choice, embargo)
    return {
        "order": choice.choice_order, "university": choice.university,
        "course": choice.course_name, "course_code": choice.course_code,
        "decision": _HELD if held else choice.decision_status,
        "offer": None if held else choice.offer_terms,
        "final": choice.final_decision,
        "conditions": [] if held else _offer_conditions(choice),
        "reply_by": _reply_by(choice),
        "decision_date": None if held else (
            str(choice.decided_at)[:10] if getattr(choice, "decided_at", None) else None),
        "placed": bool(getattr(choice, "is_placed", False)) and not held,
        "held": held,
    }


#: The steps of the tracker, in order.
TRACKER_STEPS: tuple[tuple[str, str], ...] = (
    ("applied", "Applied"),
    ("decision", "Decision"),
    ("reply", "Firm / Insurance"),
    ("results", "Results"),
    ("confirmed", "Confirmed"),
    ("handover_sent", "Handover sent"),
    ("received", "Received by university"),
    ("enrolled", "Enrolled"),
)


def _step(key: str, state: str, *, date: str | None = None,
          detail: str | None = None) -> dict[str, Any]:
    label = dict(TRACKER_STEPS)[key]
    return {"key": key, "label": label, "state": state,
            "date": (str(date)[:10] if date else None), "detail": detail or ""}


def _home_transition(student_id: str) -> dict[str, Any] | None:
    """The learner's sixth form → university transition on the platform
    journey (the handover route), newest first; None when there is none."""
    try:
        from education_system.platform.cross_system import identity_service, transitions
        journey = identity_service.find_by_student("sixth_form", student_id)
        if not journey:
            return None
        rows = [t for t in transitions.list_transitions(journey["journey_id"])
                if t.get("source_system") == "sixth_form"
                and t.get("destination_system") == "university"]
    except Exception:
        logger.debug("Transition lookup failed for %s", student_id, exc_info=True)
        return None
    live = [t for t in rows if t.get("status") != "cancelled"]
    return (live or rows or [None])[-1]


def _university_enrolment(student_id: str) -> dict[str, Any] | None:
    """The university's own enrolment report for this learner, if any."""
    try:
        from education_system.systems.sixth_form.domain.progression.destinations import (
            university_confirmations as _uc,
        )
        rows = [r for r in _uc.confirmations_for(student_id) if r["event_type"] == "enrolled"]
    except Exception:
        logger.debug("University confirmations unavailable", exc_info=True)
        return None
    return rows[-1] if rows else None


def ucas_tracker(student_id: str, *, _app=None, _choices=None,
                 _embargo_state: dict[str, Any] | None = None
                 ) -> list[dict[str, Any]] | None:
    """Applied → Decision → Firm/Insurance → Results → Confirmed →
    Handover sent → Received by university → Enrolled.

    Each step is read from a real record: the UCAS application and
    choices, released exam results, the results-day confirmation, the
    platform transition carrying the handover (approved / acknowledged /
    admitted) and the university's enrolment report. States are ``done``,
    ``current`` (the next thing to happen), ``pending``, ``held`` (waiting
    on the results embargo) and ``n/a`` (the handover steps when the Firm
    choice is not the university on this platform). Returns None when the
    learner has no application.
    """
    from education_system.systems.sixth_form.domain.progression.university import (
        ucas as _ucas,
    )
    app = _app or _ucas.get_application_for_student(student_id)
    if app is None:
        return None
    choices = _choices if _choices is not None else _ucas.list_choices(app.application_id)
    embargo = _embargo_state or _embargo(student_id, _results_year(app, choices))
    done: dict[str, dict[str, Any]] = {}

    if app.submitted_at or app.status not in ("Draft",):
        done["applied"] = _step("applied", "done", date=app.submitted_at,
                                detail=f"{len(choices)} choice(s)")

    decided = [c for c in choices if c.decision_status not in ("Awaiting",)
               and not _held_back(c, embargo)]
    if decided:
        dates = sorted(str(getattr(c, "decided_at", None) or "")[:10] for c in decided)
        offers = sum(1 for c in decided if "Offer" in c.decision_status)
        done["decision"] = _step(
            "decision", "done" if len(decided) == len(choices) else "current",
            date=dates[-1] or None,
            detail=f"{len(decided)} of {len(choices)} decided, {offers} offer(s)")

    firm = next((c for c in choices if c.final_decision == "Firm"), None)
    insurance = next((c for c in choices if c.final_decision == "Insurance"), None)
    if firm or insurance:
        bits = []
        if firm:
            bits.append(f"Firm: {firm.university}")
        if insurance:
            bits.append(f"Insurance: {insurance.university}")
        done["reply"] = _step("reply", "done", detail="; ".join(bits))

    if embargo["active"]:
        done["results"] = _step("results", "held", detail="Results day — not yet released")
    elif embargo["any_results"]:
        done["results"] = _step("results", "done", detail=f"{embargo['year']} results released")

    if not embargo["active"]:
        try:
            from education_system.systems.sixth_form.domain.progression.university import (
                post_offer as _po,
            )
            conf = _po.get_confirmation(app.application_id)
        except Exception:
            conf = None
        placed = next((c for c in choices if getattr(c, "is_placed", False)), None)
        if conf and conf.get("outcome") and conf["outcome"] != "Awaiting confirmation":
            done["confirmed"] = _step("confirmed", "done", date=conf.get("confirmed_on"),
                                      detail=conf["outcome"])
        elif placed is not None:
            done["confirmed"] = _step("confirmed", "done",
                                      detail=f"Place at {placed.university}")

    # The handover steps apply only when the Firm choice is this platform's
    # own university; elsewhere the college cannot see the far end.
    home = False
    try:
        from education_system.systems.sixth_form.domain.progression import (
            university_handover as _uh,
        )
        target = firm or next((c for c in choices if getattr(c, "is_placed", False)), None)
        home = bool(target) and _uh.is_home_university(target.university)
    except Exception:
        logger.debug("Home university unknown", exc_info=True)
    if home:
        transition = _home_transition(student_id) or {}
        if transition.get("handover_approved_at"):
            done["handover_sent"] = _step("handover_sent", "done",
                                          date=transition["handover_approved_at"])
        status = transition.get("status")
        if transition.get("acknowledged_at") or status in ("admitted", "completed"):
            done["received"] = _step(
                "received", "done",
                date=transition.get("acknowledged_at") or transition.get("updated_at"))
        enrolment = _university_enrolment(student_id)
        placed = next((c for c in choices if getattr(c, "is_placed", False)), None)
        if enrolment:
            done["enrolled"] = _step(
                "enrolled", "done", date=enrolment.get("event_date"),
                detail=" · ".join(x for x in (enrolment.get("course"),
                                              enrolment.get("start_date") and
                                              f"starts {enrolment['start_date']}") if x))
        elif placed is not None or status in ("admitted", "completed"):
            done["enrolled"] = _step("enrolled", "done",
                                     date=getattr(placed, "placed_at", None)
                                     or transition.get("completed_at"))

    steps: list[dict[str, Any]] = []
    next_marked = False
    for key, _label in TRACKER_STEPS:
        if key in done:
            steps.append(done[key])
            next_marked = next_marked or done[key]["state"] in ("current", "held")
            continue
        if not home and key in ("handover_sent", "received", "enrolled"):
            steps.append(_step(key, "n/a", detail=(
                "Only for a place at the university on this platform" if firm
                else "Once you have a Firm choice")))
            continue
        if embargo["active"] and key == "confirmed":
            steps.append(_step(key, "held", detail="After results are released"))
            next_marked = True
            continue
        steps.append(_step(key, "pending" if next_marked else "current"))
        next_marked = True
    return steps


# ── Bursaries ───────────────────────────────────────────────────────

def bursaries(student_id: str) -> list[dict[str, Any]]:
    """Applications with what has been paid, and the payment schedule."""
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _b,
    )
    out = []
    for v in _b.list_views(student_id=student_id):
        app = v.app
        payments = [{"date": d.paid_on, "amount": d.amount, "method": d.method,
                     "status": d.status}
                    for d in _b.list_disbursements(application_id=app.application_id)]
        schedule = []
        try:
            schedule = [{"due_date": i.due_date, "amount": i.amount, "state": i.state,
                         "period": f"{i.period_from} → {i.period_to}"}
                        for i in _b.list_instalments(application_id=app.application_id)]
        except Exception:
            logger.debug("Instalments unavailable for #%s", app.application_id,
                         exc_info=True)
        out.append({
            "application_id": app.application_id, "type": app.bursary_type,
            "academic_year": app.academic_year, "applied": app.application_date,
            "status": app.status, "requested": app.amount_requested,
            "awarded": app.amount_awarded, "paid": v.paid, "remaining": v.remaining,
            "evidence_received": app.evidence_received,
            "decision_note": app.decision_note if app.status in (
                "Approved", "Partially Paid", "Paid in Full", "Rejected") else None,
            "payments": payments, "schedule": schedule,
        })
    return out


# ── Trips ───────────────────────────────────────────────────────────

def trips(student_id: str) -> list[dict[str, Any]]:
    from education_system.systems.sixth_form.domains.finance.domain.trips import trips as _t
    out = []
    for v in _t.list_booking_views(student_id=student_id):
        b, t = v.booking, v.trip
        out.append({
            "booking_id": b.booking_id, "trip_id": t.trip_id, "trip": t.name,
            "destination": t.destination, "start_date": t.start_date,
            "end_date": t.end_date, "cost": t.cost_per_place,
            "payment_due": t.payment_due, "booking_status": b.status,
            "consent": b.consent_received, "consent_note": b.consent_note,
            "medical_note": b.medical_note, "dietary_note": b.dietary_note,
            "paid": v.paid, "balance": v.balance,
            "payment_state": v.payment_state, "refunded": v.refunded,
            "trip_status": t.status,
        })
    out.sort(key=lambda d: d["start_date"] or "", reverse=True)
    return out


# ── Messages and announcements ──────────────────────────────────────

def messages_to(address: str | None, *, limit: int = 50) -> list[dict[str, Any]]:
    if not address:
        return []
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msgs,
    )
    rows = _msgs.list_messages(to_address=address, sent_only=True)
    return [{"message_id": m.message_id, "subject": m.subject,
             "from_name": m.from_name, "from_address": m.from_address,
             "category": m.category, "sent_at": m.sent_at} for m in rows[:limit]]


def message_for(address: str | None, message_id: int) -> dict[str, Any]:
    """One message, provided it was addressed to ``address``."""
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msgs,
    )
    msg = _msgs.get_message(int(message_id))
    if (not address or msg is None
            or (msg.to_address or "").strip().lower() != address.strip().lower()):
        raise LookupError("That message is not in your mailbox.")
    return {"message_id": msg.message_id, "subject": msg.subject, "body": msg.body,
            "from_name": msg.from_name, "from_address": msg.from_address,
            "sent_at": msg.sent_at}


def announcements(audience: str) -> list[dict[str, Any]]:
    """Live announcements for ``students`` or ``parents``."""
    from education_system.systems.sixth_form.domains.communications.domain.announcements import (
        announcements as _ann,
    )
    rows = [a for a in _ann.list_announcements(audience=audience, published_only=True)
            if a.is_live and audience in a.audience_list]
    rows.sort(key=lambda a: (not a.pinned, -(a.priority or 0), a.published_on or ""),
              reverse=False)
    return [{"announcement_id": a.announcement_id, "title": a.title,
             "summary": a.summary, "body": a.body, "category": a.category,
             "priority": _ann.priority_label(a.priority), "pinned": a.pinned,
             "published_on": a.published_on, "expires_on": a.expires_on}
            for a in rows]


# ── Sign-outs ───────────────────────────────────────────────────────

def signouts(student_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """The learner's own sign-out-of-site history."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_signout as _so,
    )
    return [{"date": s.date, "out": s.out_time, "back": s.in_time,
             "expected_back": s.expected_back, "reason": s.reason,
             "state": s.state, "parent_permission": s.parent_permission}
            for s in _so.list_signouts(student_id=student_id, limit=limit)]


def signout_requests(student_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    """The learner's own requests to leave site, newest first."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_signout_requests as _req,
    )
    return [{"request_id": r.request_id, "date": r.date,
             "leave_time": r.leave_time, "reason": r.reason,
             "detail": r.detail, "expected_back": r.expected_back,
             "state": r.state, "decision_note": r.decision_note,
             "open": r.is_open}
            for r in _req.list_requests(student_id=student_id, limit=limit)]


def request_signout(student_id: str, *, reason: str, date: str,
                    leave_time: str, detail: str | None = None,
                    expected_back: str | None = None,
                    parent_aware: bool = False,
                    requested_by: str | None = None) -> dict[str, Any]:
    """Ask to leave site; staff approve it before the desk signs you out."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_signout_requests as _req,
    )
    r = _req.request_signout(student_id, reason, date=date,
                             leave_time=leave_time, detail=detail,
                             expected_back=expected_back,
                             parent_aware=parent_aware,
                             requested_by=requested_by)
    return {"request_id": r.request_id, "state": r.state}


def cancel_signout_request(student_id: str, request_id: int, *,
                           by: str) -> None:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_signout_requests as _req,
    )
    _req.cancel_request(request_id, by=by, student_id=student_id)


def signout_reasons() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_signout as _so,
    )
    return _so.REASONS
