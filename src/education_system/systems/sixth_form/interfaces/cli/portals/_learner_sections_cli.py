"""Student portal CLI screens added after the first twelve options.

Terminal counterpart of :mod:`...gui.portals._learner_sections`: My
Plan, Exams, Projects & Placements, Library, Surveys, Wellbeing & Help,
Study Planner, Class Resources, My Devices and Pay. Each screen is
``handler(sid, principal)`` like the rest of :mod:`.student_portal_cli`, and ``sid`` is always
``principal.student_id``. A learner picks their own records by list
number; the domain re-checks every one against ``sid``.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable

from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    learner_self_service as ls,
)

logger = logging.getLogger(__name__)

_RULE = "─" * 76


def _io() -> tuple[Callable[..., str], Callable[[], None]]:
    """The portal's idle-timed prompt and pause (imported lazily: the
    portal module imports this one)."""
    from education_system.systems.sixth_form.interfaces.cli.portals import (
        student_portal_cli as _sp,
    )
    return _sp._input, _sp._pause


def _ask(prompt: str, default: str = "") -> str:
    return _io()[0](prompt, default)


def _d(v: Any) -> str:
    return "—" if v in (None, "") else str(v)


def _head(title: str) -> None:
    print(f"\n  {_RULE}\n  {title}\n  {_RULE}")


def _pick(rows: list, prompt: str) -> int | None:
    """A 0-based index chosen by list number, or None."""
    n = _ask(prompt)
    if n.isdigit() and 1 <= int(n) <= len(rows):
        return int(n) - 1
    if n:
        print("  Not a valid option.")
    return None


def _choose(label: str, options: list[str], default: int = 1) -> str | None:
    for i, o in enumerate(options, 1):
        print(f"    {i:>2}. {o}")
    n = _ask(f"{label} (number)", str(default))
    if n.isdigit() and 1 <= int(n) <= len(options):
        return options[int(n) - 1]
    print("  ✗ Pick a number from the list.")
    return None


# ── My Plan ──────────────────────────────────────────────────────────

def my_plan(sid: str, _p) -> None:
    while True:
        data = ls.my_plan(sid)
        _head("My targets")
        if not data["targets"]:
            print("  No targets set yet.")
        else:
            print(f"  {'Subject':<26}{'MEG':<6}{'Target':<8}{'Aspire':<8}"
                  f"{'Working':<9}{'On track?':<14}Next review")
        for t in data["targets"]:
            print(f"  {t['subject'][:24]:<26}{_d(t['meg']):<6}{_d(t['target']):<8}"
                  f"{_d(t['aspirational']):<8}{_d(t['current']):<9}"
                  f"{_d(t['status'])[:12]:<14}{_d(t['next_review'])}")
        if data["actions"]:
            print("\n  Action steps")
        for a in data["actions"]:
            flag = " OVERDUE" if a["overdue"] else ""
            print(f"    • {_d(a['subject'])}: {a['description']} "
                  f"(due {_d(a['due'])}, {a['status']}{flag})")
        _head("My individual learning plan")
        reviews: list[dict[str, Any]] = []
        if not data["plans"]:
            print("  You have no learning plan shared with you yet.")
        for p in data["plans"]:
            print(f"\n  {p['title']} — {p['type']} · {p['status']} · lead {_d(p['lead'])}"
                  f" · next review {_d(p['next_review'])}")
            for label, key in (("Strengths", "strengths"), ("Strategies", "strategies"),
                               ("Support", "support"),
                               ("Success looks like", "success_criteria")):
                if p.get(key):
                    print(f"    {label}: {p[key]}")
            for g in p["goals"]:
                print(f"    Goal: {g['title']} [{g['category']}] by "
                      f"{_d(g['target_date'])} — {g['status']}")
            for r in p["reviews"]:
                reviews.append(r)
                print(f"    {len(reviews):>2}) Review {r['date']} by {_d(r['reviewer'])}"
                      f" — {_d(r['progress'])}")
                if r["comments"]:
                    print(f"        Comments: {r['comments']}")
                if r["next_steps"]:
                    print(f"        Next steps: {r['next_steps']}")
                print(f"        My comment: {_d(r['student_comment'])}")
        if not reviews:
            return
        i = _pick(reviews, "Add/change your comment on which review (number), "
                           "or Enter to go back")
        if i is None:
            return
        text = _ask("Your comment (blank to clear)")
        try:
            ls.set_review_comment(sid, reviews[i]["review_id"], text or None)
            print("  ✓ Saved.")
        except Exception as e:      # ValidationError
            print(f"  ✗ {e}")


# ── Exams ────────────────────────────────────────────────────────────

def exams(sid: str, _p) -> None:
    data = ls.exams(sid)
    _head("My exams — statement of entry")
    print(f"  Candidate number: {_d(data['candidate_no'])}")
    print(f"  Access arrangements: {data['arrangements'] or 'none recorded'}")
    if not data["entries"]:
        print("\n  You have not been entered for any exams yet.")
    else:
        print(f"\n  {'Date':<11}{'Sess':<5}{'Time':<13}{'Subject':<20}{'Code':<10}"
              f"{'Room':<9}{'Seat':<6}Entry")
        for e in data["entries"]:
            time = f"{e['start']}-{e['end']}" if e["start"] else "—"
            print(f"  {_d(e['date']):<11}{_d(e['session']):<5}{time:<13}"
                  f"{e['subject'][:18]:<20}{e['paper_code'][:9]:<10}"
                  f"{_d(e['room'])[:8]:<9}{_d(e['seat']):<6}{e['entry_status']}")
            if e["paper"]:
                print(f"      {e['paper']} ({e['board']})")
            if e["finish"] and e["finish"] != e["end"]:
                print(f"      With your extra time you finish at {e['finish']}.")
            if e["clash"]:
                print(f"      ! Clash: {e['clash']}")
    if data["contingency"]:
        print("\n  Keep these free (contingency days):")
        for c in data["contingency"]:
            print(f"    {c['date']} {c['session']} ({c['series']})")
    _head("Released results")
    if not (data["results"] or data["qualification_results"]):
        print("  No results have been released to you yet.")
    for q in data["qualification_results"]:
        print(f"  {q['series']:<14}{q['subject'][:26]:<28}{'qualification':<16}{q['grade']}")
    for r in data["results"]:
        print(f"  {r['season']} {r['year']:<8}{r['subject'][:26]:<28}"
              f"{_d(r['paper'])[:14]:<16}{r['grade']}")


# ── Projects & placements ────────────────────────────────────────────

def projects(sid: str, _p) -> None:
    while True:
        data = ls.projects(sid)
        _head("Extended Project (EPQ)")
        epq = data["epq"]
        if epq is None:
            print("  You are not doing an EPQ.")
        else:
            print(f"  {epq['title']} — {epq['artefact']} · stage {epq['stage']} · "
                  f"supervisor {_d(epq['supervisor'])}")
            if epq["question"]:
                print(f"  Question: {epq['question']}")
            print(f"  Production log: {epq['hours']}")
            for m in epq["milestones"]:
                print(f"    {m['milestone']:<28}due {_d(m['due']):<12}{m['status']}")
            print("  Recent log entries:")
            for e in epq["log"][:10]:
                print(f"    {e['date']}  {e['hours']:>4g}h  {e['activity'][:56]}")
            if not epq["log"]:
                print("    (none yet)")
        _head("Work experience")
        if not data["placements"]:
            print("  No placements recorded.")
        for pl in data["placements"]:
            req = f"/{pl['hours_required']:g}" if pl["hours_required"] else ""
            print(f"  {pl['employer'][:26]:<28}{_d(pl['role'])[:18]:<20}"
                  f"{pl['start']} → {pl['end']}  {pl['status']:<11}"
                  f"{pl['hours_done']:g}{req} h")
        _head("Careers guidance")
        a = data["aspiration"]
        if a:
            print(f"  My plans: {a['pathway']}"
                  + "".join(f" · {k} {a[k]}" for k in ("career", "sector", "employer",
                                                       "course") if a[k]))
        if not data["careers"]:
            print("  No careers meetings recorded yet.")
        for s in data["careers"]:
            print(f"  {s['date']}  {s['type']:<20}{_d(s['adviser'])}")
            if s["action_plan"]:
                print(f"      Action plan: {s['action_plan']}")
        if not (epq and epq["log_open"]):
            return
        if not _ask("A)dd an EPQ log entry, or Enter to go back").lower().startswith("a"):
            return
        try:
            ls.add_epq_log(sid, entry_date=_ask("Date (YYYY-MM-DD)",
                                                _dt.date.today().isoformat()),
                           hours=_ask("Hours"), activity=_ask("What you did"),
                           reflection=_ask("Reflection (optional)") or None)
            print("  ✓ Added.")
        except Exception as e:      # ValidationError
            print(f"  ✗ {e}")


# ── Library ──────────────────────────────────────────────────────────

def library(sid: str, _p) -> None:
    data = ls.library(sid)
    _head("Library — on loan to me")
    if not data["loans"]:
        print("  Nothing on loan.")
    for x in data["loans"]:
        print(f"  {x['title'][:44]:<46}due {x['due_on']}"
              + ("  OVERDUE" if x["overdue"] else ""))
    print("\n  My reservations")
    if not data["reservations"]:
        print("    None.")
    for x in data["reservations"]:
        where = (f"queue #{x['queue_position']}" if x["queue_position"]
                 else f"collect by {_d(x['collect_by'])}")
        print(f"    {x['title'][:44]:<46}{x['status']:<9}{where}")
    if data["balance"]:
        print(f"\n  Library charges outstanding: £{data['balance']:,.2f} — see the desk.")
    _head("Reading lists for my subjects")
    if not data["reading_lists"]:
        print("  No reading lists for your subjects yet.")
    for rl in data["reading_lists"]:
        print(f"\n  {rl['title']} ({_d(rl['subject'])})")
        for i in rl["items"]:
            print(f"    [{i['requirement'][:8]:<8}] {i['title']}"
                  + (f" — {i['note']}" if i["note"] else ""))


# ── Surveys ──────────────────────────────────────────────────────────

def surveys(sid: str, p) -> None:
    while True:
        rows = ls.surveys(sid)
        _head("Surveys")
        if not rows:
            print("  There are no surveys open for you at the moment.")
            return
        print("  Anonymous surveys never record your name with your answers.")
        for i, s in enumerate(rows, 1):
            print(f"  {i:>2}) {s['name'][:40]:<42}closes {_d(s['close_on']):<12}"
                  f"{'anonymous' if s['anonymous'] else 'named':<11}"
                  f"{'COMPLETED' if s['completed'] else 'to do'}")
        i = _pick(rows, "Take which survey (number), or Enter to go back")
        if i is None:
            return
        s = rows[i]
        if s["completed"]:
            print("  You have already completed this survey.")
            continue
        _take_survey(sid, p, s)


def _take_survey(sid: str, p, s: dict[str, Any]) -> None:
    print(f"\n  {s['name']}")
    if s["description"]:
        print(f"  {s['description']}")
    print("  Anonymous — your name is not stored." if s["anonymous"]
          else "  Named — your name is recorded with your answers.")
    answers: dict[int, Any] = {}
    for idx, q in enumerate(s["questions"]):
        hint = {"Likert": " (1-5)", "Yes/No": " (y/n)",
                "Multi Choice": " (numbers, comma-separated)",
                "Single Choice": " (number)"}.get(q["type"], "")
        print(f"\n  Q{idx + 1}. {q['prompt']}{' *' if q['required'] else ''}")
        if q["type"] in ("Single Choice", "Multi Choice"):
            for n, c in enumerate(q["choices"], 1):
                print(f"      {n}. {c}")
        raw = _ask(f"Answer{hint}")
        if not raw:
            continue
        if q["type"] == "Single Choice" and raw.isdigit() \
                and 1 <= int(raw) <= len(q["choices"]):
            raw = q["choices"][int(raw) - 1]
        elif q["type"] == "Multi Choice":
            raw = [q["choices"][int(x) - 1] for x in raw.replace(" ", "").split(",")
                   if x.isdigit() and 1 <= int(x) <= len(q["choices"])]
        answers[idx] = raw
    try:
        from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
            learner_view as _lv,
        )
        name = _lv.student_identity(sid).get("full_name")
    except Exception:
        name = None
    try:
        ls.submit_survey(sid, s["survey_id"], answers, name=name)
        print("\n  ✓ Thank you — your response has been recorded.")
    except Exception as e:          # ValidationError
        print(f"\n  ✗ {e}")


# ── Wellbeing & help ─────────────────────────────────────────────────

def wellbeing(sid: str, p) -> None:
    while True:
        _head("Wellbeing & help")
        for line in ls.urgent_help():
            print(f"  • {line}")
        print("\n  My requests for support")
        reqs = ls.my_support_requests(sid)
        if not reqs:
            print("    None made through the portal.")
        for r in reqs:
            print(f"    {r['date']}  {r['type'][:24]:<26}{r['status']:<12}"
                  f"{_d(r['assigned_to'])}")
        receipts = ls.my_concern_receipts(p)
        if receipts:
            print("\n  Concerns you have reported (passed to the DSL): " + ", ".join(
                f"#{r['reference']} ({(r['filed'] or '')[:10]})" for r in receipts))
        res = ls.saved_help_resources(sid)
        if res:
            print("\n  Help resources I have saved")
            for r in res:
                print(f"    {r['title'][:30]:<32}{_d(r['url'] or r['contact'])}")
        pick = _ask("A)sk for support, R)eport a concern, Enter to go back").lower()
        if not pick:
            return
        if pick.startswith("a"):
            _ask_support(sid, p)
        elif pick.startswith("r"):
            _report_concern(p)


def _ask_support(sid: str, p) -> None:
    kind = _choose("What kind of help", list(ls.support_types()))
    if kind is None:
        return
    issue = _ask("Tell us a little more")
    urgent = _ask("Is it urgent? y/N", "n").lower().startswith("y")
    try:
        rid = ls.request_support(sid, support_type=kind, issue=issue,
                                 referrer=p.username, urgent=urgent)
        print(f"  ✓ Request #{rid} sent to the student support team.")
    except Exception as e:          # ValidationError
        print(f"  ✗ {e}")


def _report_concern(p) -> None:
    print("\n  This goes straight to the college's Designated Safeguarding Lead.")
    print("  If anyone is in immediate danger, call 999 now.")
    topics = list(ls.concern_topics())
    topic = _choose("What is it about", topics, default=len(topics))
    if topic is None:
        return
    about = _choose("Who is it about", list(ls.concern_subjects()))
    if about is None:
        return
    desc = _ask("What has happened")
    unsafe = _ask("Do you feel unsafe right now? y/N", "n").lower().startswith("y")
    try:
        print(f"\n  ✓ {ls.report_concern(p, desc, topic=topic, about=about, unsafe_now=unsafe)}")
    except Exception as e:          # ValidationError
        print(f"  ✗ {e}")


# ── Study planner ────────────────────────────────────────────────────

def study(sid: str, _p) -> None:
    while True:
        data = ls.study_plan(sid)
        s = data["summary"]
        _head("My study plan")
        print(f"  {s['total']} sessions · {s['completed']} done · {s['open']} to do · "
              f"{s['overdue']} overdue")
        tasks = data["tasks"]
        if not tasks:
            print("  No study sessions planned yet. Ask your tutor to help you set one up.")
            return
        for i, t in enumerate(tasks, 1):
            state = "OVERDUE" if t["overdue"] else t["status"]
            print(f"  {i:>3}) {_d(t['date']):<11}{t['start']:<6}{_d(t['subject'])[:16]:<18}"
                  f"{t['title'][:28]:<30}{state}")
        pick = _ask("S)tart a session, D)one with a session, Enter to go back").lower()
        if not pick or pick[0] not in "sd":
            return
        i = _pick(tasks, "Which session (number)")
        if i is None:
            continue
        t = tasks[i]
        try:
            if pick.startswith("s"):
                ls.start_study_session(sid, t["task_id"])
            else:
                raw = _ask("Minutes spent (optional)")
                ls.finish_study_session(
                    sid, t["task_id"], actual_minutes=int(raw) if raw.isdigit() else None,
                    reflection=_ask("How did it go? (optional)") or None)
            print("  ✓ Updated.")
        except Exception as e:      # ValidationError
            print(f"  ✗ {e}")


# ── Class resources, devices, pay ────────────────────────────────────

def class_resources(sid: str, _p) -> None:
    from education_system.systems.sixth_form.domain.academics.class_resources import (
        class_resources as cr,
    )
    rows = cr.resources_for_student(sid)
    _head("Class resources")
    if not rows:
        print("  Nothing has been shared with your classes yet.")
        return
    for i, s in enumerate(rows, 1):
        r = s.resource
        title = s.task.title if s.task else r.title
        due = f"  due {s.task.due_date}" if s.task and s.task.due_date else ""
        print(f"  {i:>3}. [{_d(r.group_name or r.course_code)[:12]:<12}] "
              f"wk {_d(r.week):<3} {title[:44]}{due}{'  (opened)' if s.seen else ''}")
    idx = _pick(rows, "Open which (number), or Enter to go back")
    if idx is None:
        return
    try:
        kind, target = cr.open_resource(rows[idx].resource.resource_id, student_id=sid)
    except ValueError as e:
        print(f"  ✗ {e}")
        return
    print(f"\n  {'File' if kind == 'file' else 'Link'}: {target}")


def devices(sid: str, _p) -> None:
    from education_system.systems.sixth_form.domains.operations.domain.assets import assets
    from education_system.systems.sixth_form.domains.operations.domain.device_loans import (
        acceptable_use as aup,
        device_loans as dl,
    )
    _head("IT acceptable-use policy")
    cur = aup.current_aup()
    if cur is None:
        print("  No acceptable-use policy has been published yet.")
    else:
        print(f"  {cur.title} — version {cur.version}")
        if cur.summary:
            print(f"  {cur.summary}")
        if aup.current_acceptance(aup.STUDENT, sid) is not None:
            print("  You have accepted this version.")
        elif _ask("You need to accept this before borrowing a device. "
                  "Accept now? (y/N)").lower().startswith("y"):
            try:
                aup.accept_current()
                print("  ✓ Accepted.")
            except ValueError as e:
                print(f"  ✗ {e}")
    _head("Devices on loan to me")
    loans = dl.loans_for_student(sid)
    if not loans:
        print("  You have no device loans.")
    for ln in loans:
        a = assets.get_asset(ln.asset_id)
        name = a.name if a else f"Asset {ln.asset_id}"
        back = f"returned {ln.returned_on}" if ln.returned_on else f"due {ln.due_on}"
        charge = (f"  charge £{ln.charge_amount:,.2f} ({ln.charge_status})"
                  if ln.charge_amount else "")
        print(f"  {name[:36]:<38}{ln.status:<10}{back}{charge}")


def pay(sid: str, _p) -> None:
    from education_system.systems.sixth_form.domains.finance.interfaces.cli.online_payments import (
        online_payments_cli,
    )
    online_payments_cli.pay_menu("student", sid)


MENU: list[tuple[str, Callable[[str, Any], None]]] = [
    ("My plan (ILP & targets)", my_plan),
    ("My exams (entries, timetable, results)", exams),
    ("Projects & placements (EPQ, work experience, careers)", projects),
    ("Library", library),
    ("Surveys", surveys),
    ("Wellbeing & help (support, report a concern)", wellbeing),
    ("Study planner", study),
    ("Class resources", class_resources),
    ("My devices & acceptable use", devices),
    ("Pay fees, trips or meals online", pay),
]
