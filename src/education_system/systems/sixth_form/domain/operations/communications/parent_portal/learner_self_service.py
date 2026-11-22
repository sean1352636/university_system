"""Learner-only reads and actions for the student portal.

The companion of :mod:`.learner_view` for the sections only the learner
themselves sees: their plan (ILP + targets), exams, projects and
placements, library, surveys, wellbeing and help, and study planner.

Same rule as :mod:`.learner_view`: every function takes the bare
``student_id`` (or, for safeguarding, the signed-in principal) and the
caller passes only ``principal.student_id`` — the portals never take an
id from the screen. The actions here re-check ownership in the owning
domain module (an ILP review, a study session, the EPQ project are all
found *from* the learner, never by an id the learner could swap).

What is left out on purpose: staff notes on every record, Draft ILPs,
EPQ marks/grades (results come only through released exam results),
exam results under embargo, staff-raised support referrals, and all
safeguarding data — the learner can file a concern, and see only the
reference and date of what they filed.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    learner_view as _lv,
)

logger = logging.getLogger(__name__)


def _sid(student_id: str) -> str:
    """The learner's id, never blank.

    Several domain ``list_*(student_id=...)`` readers treat a blank id as
    "no filter", so a blank id must stop here rather than list everyone.
    """
    sid = (student_id or "").strip() if isinstance(student_id, str) else ""
    if not sid:
        raise ValueError("A signed-in learner's student id is required")
    return sid


def _subjects(student_id: str) -> list[str]:
    try:
        return sorted({a["subject"] for a in _lv.learning_aims(student_id)
                       if a.get("subject")})
    except Exception:
        logger.exception("Could not read learning aims for %s", student_id)
        return []


# ── My Plan: ILP + targets ──────────────────────────────────────────

def my_plan(student_id: str) -> dict[str, Any]:
    """The learner's shared ILPs (goals, reviews) and academic targets."""
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.assessment.ilp import ilp as _ilp
    from education_system.systems.sixth_form.domain.assessment.target_setting import (
        target_setting as _ts,
    )
    plans = []
    for d in _ilp.plans_for_learner(student_id):
        p = d.plan
        plans.append({
            "plan_id": p.plan_id, "title": p.title, "type": p.plan_type,
            "status": p.status, "lead": p.lead_staff, "start": p.start_date,
            "end": p.end_date, "next_review": p.next_review_due,
            "strengths": p.strengths, "strategies": p.strategies,
            "support": p.support_provided, "success_criteria": p.success_criteria,
            "goals": [{"title": g.title, "description": g.description,
                       "category": g.category, "target_date": g.target_date,
                       "status": g.status, "success_criteria": g.success_criteria,
                       "completed_on": g.completed_on} for g in d.goals],
            "reviews": [{"review_id": r.review_id, "date": r.review_date,
                         "reviewer": r.reviewer, "progress": r.progress,
                         "comments": r.comments, "next_steps": r.next_steps,
                         "next_review": r.next_review_due,
                         "student_comment": r.student_comment,
                         "student_comment_at": r.student_comment_at}
                        for r in d.reviews],
        })
    targets = _ts.student_academic_targets(student_id)
    megs: dict[str, str | None] = {}
    try:
        from education_system.systems.sixth_form.domain.assessment.target_setting import (
            meg as _meg,
        )
        megs = {m.subject: m.meg_grade for m in _meg.megs_for_student(student_id)}
    except Exception:
        logger.debug("MEG derivation unavailable for %s", student_id, exc_info=True)
    rows: dict[str, dict[str, Any]] = {}
    for t in targets.grade_targets:
        rows[t.subject_name] = {
            "subject": t.subject_name, "meg": megs.get(t.subject_name),
            "target": t.mte_grade, "aspirational": t.aspirational_grade,
            "current": t.current_grade, "status": t.status,
            "next_review": t.next_review_due}
    for subject, grade in megs.items():
        rows.setdefault(subject, {"subject": subject, "meg": grade, "target": None,
                                  "aspirational": None, "current": None,
                                  "status": None, "next_review": None})
    return {
        "plans": plans,
        "targets": sorted(rows.values(), key=lambda r: r["subject"]),
        "actions": [{"subject": a.subject_name, "description": a.description,
                     "measure": a.measure, "due": a.due_date, "status": a.status,
                     "overdue": a.is_overdue, "progress": a.progress_note}
                    for a in targets.actions],
    }


def set_review_comment(student_id: str, review_id: int, comment: str | None) -> None:
    """The learner's own voice on one of their ILP reviews."""
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.assessment.ilp import ilp as _ilp
    _ilp.set_student_comment(student_id, review_id, comment)


# ── Exams: statement of entry, timetable, released results ──────────

def _arrangements_text(student_id: str) -> str | None:
    """Usable access arrangements in plain words (no internal flags)."""
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        access_arrangements as _aa,
    )
    a = _aa.for_student(student_id)
    parts: list[str] = []
    if a.extra_time_pct:
        parts.append(f"{a.extra_time_pct}% extra time")
    for on, label in ((a.reader, "Reader"), (a.scribe, "Scribe"),
                      (a.word_processor, "Word processor"),
                      (a.separate_room, "Separate room"),
                      (a.rest_breaks, "Rest breaks")):
        if on:
            parts.append(label)
    parts.extend(a.other)
    return ", ".join(parts) or None


def exams(student_id: str) -> dict[str, Any]:
    """Statement of entry with the timetable, room/seat, clashes and
    released results. Results under embargo never appear."""
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _sittings,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        candidates as _cand,
        results_day as _rd,
        timetable as _tt,
    )
    entries = _entries.entries_for_student(student_id)
    series = sorted({(e.season, e.year) for e in entries}, key=lambda s: (s[1], s[0]))
    papers: dict[tuple[str, str, int], Any] = {}
    for season, year in series:
        try:
            for p in _tt.candidate_timetable(student_id, season, year):
                papers[(p.component_code, season, year)] = p
        except Exception:
            logger.exception("Exam timetable unavailable for %s %s %s",
                             student_id, season, year)
    seats: dict[tuple[str, str], tuple[Any, Any]] = {}
    try:
        for sitting, cand in _sittings.student_record(student_id):
            seats[(sitting.paper_code, sitting.date)] = (sitting, cand)
    except Exception:
        logger.exception("Exam sittings unavailable for %s", student_id)

    rows = []
    slot_count: dict[tuple[str, str], int] = {}
    for e in entries:
        p = papers.get((e.paper_code, e.season, e.year))
        if p and e.status != "Withdrawn":
            slot_count[(p.exam_date, p.session)] = slot_count.get(
                (p.exam_date, p.session), 0) + 1
    for e in entries:
        p = papers.get((e.paper_code, e.season, e.year))
        sitting, cand = seats.get((e.paper_code, p.exam_date if p else ""), (None, None))
        clash = None
        if p and e.status != "Withdrawn" and slot_count.get((p.exam_date, p.session), 0) > 1:
            res = _tt.get_resolution(student_id, e.season, e.year, p.exam_date, p.session)
            if res is None:
                clash = "Clash with another paper — the exams office will tell you the plan"
            else:
                clash = res.method
                if res.moved_to_date:
                    moved = " ".join(x for x in (res.moved_to_date, res.moved_to_session,
                                                 res.moved_to_time) if x)
                    clash += f" (moved to {moved})"
        rows.append({
            "series": f"{e.season} {e.year}", "subject": e.subject,
            "board": e.exam_board, "paper_code": e.paper_code,
            "paper": e.paper_title or (p.title if p else None),
            "entry_status": e.status, "tier": e.tier,
            "date": p.exam_date if p else None, "session": p.session if p else None,
            "start": p.start_time if p else None, "end": p.end_time if p else None,
            "duration": p.duration_minutes if p else None,
            "room": sitting.room if sitting else None,
            "seat": cand.seat if cand else None,
            "finish": cand.finish_time if cand else None,
            "clash": clash,
        })
    rows.sort(key=lambda r: (r["date"] or "9999", r["start"] or "", r["subject"]))

    contingency = []
    for season, year in series:
        try:
            contingency += [{"series": f"{season} {year}", "date": c.exam_date,
                             "session": c.session or "All day"}
                            for c in _tt.list_contingency(season=season, year=year)]
        except Exception:
            logger.debug("Contingency days unavailable", exc_info=True)

    candidate_no = None
    try:
        candidate_no = _cand.candidate_number(student_id)
    except Exception:
        logger.debug("Candidate number unavailable", exc_info=True)
    arrangements = None
    try:
        arrangements = _arrangements_text(student_id)
    except Exception:
        logger.exception("Access arrangements unavailable for %s", student_id)

    qualification = [{"series": f"{q.season} {q.year}", "subject": q.subject or q.entry_code,
                      "board": q.exam_board, "type": q.qualification_type,
                      "grade": q.grade, "ums": q.ums}
                     for q in _rd.list_qualification_results(student_id=student_id,
                                                             released_only=True)]
    return {"candidate_no": candidate_no, "arrangements": arrangements,
            "entries": rows, "contingency": contingency,
            "results": _lv.released_results(student_id),
            "qualification_results": qualification}


# ── Projects & placements: EPQ, work experience, careers ────────────

def projects(student_id: str) -> dict[str, Any]:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.academics.epq import epq as _epq
    from education_system.systems.sixth_form.domain.progression.careers import (
        careers as _careers,
    )
    from education_system.systems.sixth_form.domain.progression.work_experience import (
        work_experience as _we,
    )
    epq = None
    proj = _epq.get_project_for_student(student_id)
    if proj is not None:
        chk = _epq.hours_check(proj.project_id)
        epq = {
            "title": proj.working_title, "question": proj.research_question,
            "artefact": proj.artefact_type, "supervisor": proj.supervisor,
            "stage": proj.stage, "hours": chk.label,
            "authenticated": proj.is_authenticated,
            "log_open": (proj.stage not in _epq.LEARNER_LOG_CLOSED_STAGES
                         and not proj.is_authenticated),
            "log": [{"date": e.entry_date, "hours": e.hours, "activity": e.activity,
                     "reflection": e.reflection}
                    for e in _epq.list_log_entries(proj.project_id)],
            "milestones": [{"milestone": _epq.MILESTONE_LABELS.get(m.milestone_type,
                                                                   m.milestone_type),
                            "due": m.due_date, "done": m.completed_date,
                            "status": m.status}
                           for m in _epq.list_milestones(proj.project_id)],
        }
    employers: dict[int, str] = {}
    placements = []
    for p in _we.list_placements(student_id=student_id):
        if p.employer_id not in employers:
            emp = _we.get_employer(p.employer_id)
            employers[p.employer_id] = emp.name if emp else "—"
        placements.append({
            "employer": employers[p.employer_id], "role": p.role,
            "start": p.start_date, "end": p.end_date, "status": p.status,
            "hours_done": p.hours_completed, "hours_required": p.hours_required,
            "progress": p.progress_percent, "supervisor": p.supervisor_name,
            "consent": p.parental_consent})
    sessions = [{"date": s.session_date, "adviser": s.advisor, "type": s.session_type,
                 "topics": s.topics, "action_plan": s.action_plan,
                 "follow_up": s.follow_up_date, "status": s.status}
                for s in _careers.sessions_for_student(student_id)]
    asp = _careers.get_aspiration_for_student(student_id)
    aspiration = None if asp is None else {
        "pathway": asp.primary_pathway, "career": asp.target_career,
        "sector": asp.target_sector, "employer": asp.target_employer,
        "course": asp.target_course}
    return {"epq": epq, "placements": placements, "careers": sessions,
            "aspiration": aspiration}


def add_epq_log(student_id: str, *, entry_date: str, hours: Any, activity: str,
                reflection: str | None = None) -> None:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.academics.epq import epq as _epq
    _epq.add_own_log_entry(student_id, entry_date=entry_date, hours=hours,
                           activity=activity, reflection=reflection)


# ── Library ─────────────────────────────────────────────────────────

def library(student_id: str) -> dict[str, Any]:
    """Current loans, holds, fines and reading lists for their subjects."""
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.academics.library import (
        library_kiosk as _kiosk,
        library_reading_lists as _rl,
    )
    summary = _kiosk.student_summary(student_id)
    lists = []
    for rl in _rl.reading_lists_for_subjects(_subjects(student_id)):
        lists.append({"title": rl.title, "subject": rl.subject,
                      "year": rl.academic_year,
                      "items": [{"title": i.book_title, "requirement": i.requirement,
                                 "note": i.note} for i in _rl.list_items(rl.list_id)]})
    return {"loans": summary["loans"], "reservations": summary["reservations"],
            "fines": summary["fines"], "balance": summary["balance"],
            "reading_lists": lists}


# ── Surveys ─────────────────────────────────────────────────────────

def surveys(student_id: str) -> list[dict[str, Any]]:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.pastoral.surveys import surveys as _sv
    return [{"survey_id": s.survey_id, "name": s.name, "description": s.description,
             "anonymous": s.anonymous, "close_on": s.close_on, "completed": done,
             "questions": [q.to_dict() for q in s.questions]}
            for s, done in _sv.open_surveys_for_learner(student_id)]


def submit_survey(student_id: str, survey_id: int, answers: dict[int, Any],
                  *, name: str | None = None) -> None:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.pastoral.surveys import surveys as _sv
    _sv.submit_learner_response(survey_id, student_id, answers=answers,
                                respondent_name=name)


def survey_types() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.pastoral.surveys import surveys as _sv
    return _sv.QUESTION_TYPES


# ── Wellbeing & help ────────────────────────────────────────────────

def support_types() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.pastoral.student_support import (
        student_support as _ss,
    )
    return _ss.SELF_REFERRAL_TYPES


def my_support_requests(student_id: str) -> list[dict[str, Any]]:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.pastoral.student_support import (
        student_support as _ss,
    )
    return [{"referral_id": r.referral_id, "date": r.referred_on, "type": r.support_type,
             "issue": r.presenting_issue, "status": r.status,
             "assigned_to": r.assigned_to}
            for r in _ss.self_referrals_for(student_id)]


def request_support(student_id: str, *, support_type: str, issue: str,
                    referrer: str, urgent: bool = False) -> int:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.pastoral.student_support import (
        student_support as _ss,
    )
    return _ss.self_refer(student_id, support_type=support_type, issue=issue,
                          referrer=referrer, urgent=urgent).referral_id


def concern_topics() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.safeguarding import safeguarding as _sg
    return tuple(_sg.LEARNER_TOPICS)


def concern_subjects() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.safeguarding import safeguarding as _sg
    return _sg.LEARNER_SUBJECTS


def report_concern(principal, description: str, *, topic: str, about: str,
                   unsafe_now: bool = False) -> str:
    """File a learner concern with the DSL; returns the message to show."""
    from education_system.systems.sixth_form.domain.safeguarding import safeguarding as _sg
    receipt = _sg.report_concern_as_learner(principal, description, topic=topic,
                                            about=about, unsafe_now=unsafe_now)
    return f"Reference #{receipt.concern_id}. {receipt.message}"


def my_concern_receipts(principal) -> list[dict[str, Any]]:
    """Reference and date only of what this learner filed — no content."""
    from education_system.systems.sixth_form.domain.safeguarding import safeguarding as _sg
    if principal is None or not principal.is_student:
        return []
    return [{"reference": r.concern_id, "filed": r.reported_at}
            for r in _sg.my_reports(principal)]


def urgent_help() -> list[str]:
    """Static urgent-help lines. Only what the codebase already states
    (the safeguarding module's "call 999" advice) — no phone numbers are
    invented here."""
    return [
        "If you or anyone else is in immediate danger, call 999.",
        "Tell any member of staff in person — your tutor, a teacher or reception "
        "— and ask for the Designated Safeguarding Lead (DSL).",
        "Using 'Report a concern' here sends your worry straight to the DSL.",
    ]


def saved_help_resources(student_id: str) -> list[dict[str, Any]]:
    """Help resources the learner saved for themselves in Student Wellbeing."""
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.pastoral.student_wellbeing import (
        student_wellbeing as _sw,
    )
    return [{"title": r.title, "category": r.category, "url": r.url,
             "contact": r.contact, "notes": r.notes}
            for r in _sw.list_resources(student_id=student_id)]


# ── Study planner ───────────────────────────────────────────────────

def study_plan(student_id: str) -> dict[str, Any]:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.academics.study_planner import (
        study_planner as _sp,
    )
    s = _sp.student_summary(student_id)
    return {
        "summary": {"total": s.total, "completed": s.completed, "open": s.open_count,
                    "overdue": s.overdue, "planned_minutes": s.minutes_planned,
                    "actual_minutes": s.minutes_actual},
        "tasks": [{"task_id": t.task_id, "date": t.planned_date, "start": t.time_label,
                   "subject": t.subject_name, "title": t.title, "type": t.task_type,
                   "priority": t.priority, "planned": t.planned_duration,
                   "actual": t.actual_duration, "status": t.status,
                   "open": t.is_open, "overdue": t.is_overdue,
                   "reflection": t.reflection}
                  for t in _sp.list_tasks(student_id=student_id)],
    }


def start_study_session(student_id: str, task_id: int) -> None:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.academics.study_planner import (
        study_planner as _sp,
    )
    _sp.start_own_task(student_id, task_id)


def finish_study_session(student_id: str, task_id: int, *,
                         actual_minutes: int | None = None,
                         reflection: str | None = None) -> None:
    student_id = _sid(student_id)
    from education_system.systems.sixth_form.domain.academics.study_planner import (
        study_planner as _sp,
    )
    _sp.complete_own_task(student_id, task_id, actual_duration=actual_minutes,
                          reflection=reflection)
