"""The pupil and parent portals in the terminal (same sections as the GUI).
Reads go through :mod:`modules.portals.domain.portal`, which checks the link on every call."""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.secondary import SYSTEM_NAME
from education_system.systems.secondary.modules.portals.cli.portal_linked_cli import (
    _messages,
    _money,
    _wellbeing,
    home_lines,
)
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.progression.domain import sixth_form_choices as SC
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

logger = logging.getLogger(__name__)
_ERRORS = (PT.ValidationError, PT.PermissionDenied, PT.NotFound)


_problem = prompts.problem


def _d(iso: str | None) -> str:
    try:
        return _dt.date.fromisoformat(str(iso)[:10]).strftime("%a %d %b") if iso else ""
    except ValueError:
        return str(iso)


def menu(auth, principal: Principal) -> str:
    """Run the portal. Returns "logout", "quit" or "gui"."""
    who = "Pupil" if principal.is_student else "Parent"
    children = PT.pupils(principal)
    if not children:
        print(f"\n  {SYSTEM_NAME} · {who} portal")
        print("  " + ("Your login isn't linked to a pupil record yet." if principal.is_student
                      else "No children are linked to your login yet."))
        print("  Please contact the school office - they can link it for you.")
        return "logout"
    current = children[0]
    sections = list(PT.sections_for(principal))
    while True:
        print(f"\n=== {SYSTEM_NAME} · {who} portal ===")
        print(f"Signed in: {principal.username}"
              + ("" if principal.is_student else f" · viewing {current.display_name} "
                 f"(Year {current.year_group})"))
        for i, s in enumerate(sections, 1):
            print(f"  {i:2d}) {s}")
        if len(children) > 1:
            print("   C) Choose another child")
        print("   P) Change password\n   G) Switch to GUI\n   L) Logout\n   Q) Quit")
        choice = _prompt("Select: ").lower()
        if choice == "l":
            return "logout"
        if choice == "q":
            return "quit"
        if choice == "g":
            return "gui"
        if choice == "p":
            from education_system.platform.delivery.cli import change_password_cli
            change_password_cli.run(auth)
            continue
        if choice == "c" and len(children) > 1:
            for i, p in enumerate(children, 1):
                print(f"  {i}) {p.display_name} (Year {p.year_group})")
            n = _prompt("  Child: ")
            if n.isdigit() and 1 <= int(n) <= len(children):
                current = children[int(n) - 1]
            continue
        if not choice.isdigit() or not 1 <= int(choice) <= len(sections):
            print("Invalid selection.")
            continue
        section = sections[int(choice) - 1]
        try:
            globals()["_" + section.lower().replace(" ", "_")](principal, current.pupil_id)
        except _ERRORS as e:
            _problem(e)
        except Exception as e:  # noqa: BLE001 - keep the portal alive
            logger.exception("Portal section %s failed", section)
            activity_log.record("error", target=section, outcome="error",
                                error=type(e).__name__)
            print(f"\n  {section} could not be opened: {e}")
        _pause()


def _home(principal, pid) -> None:
    h = PT.home(principal, pid)
    print(f"\n  {h['day']:%A %d %B %Y}" + (f" · {h['day_label']}" if h["day_label"] else ""))
    att = h["attendance"]
    if att and att.attendance_pct is not None:
        print(f"  Attendance this year: {att.attendance_pct}%")
    print("\n  Today's lessons:")
    _lessons(h["lessons"])
    print("\n  Homework due this week:")
    for t, _w in h["homework_due"] or []:
        print(f"    {_d(t.due_date):<11} {t.subject_code:<6} {t.title}"
              + ("  (overdue)" if t.due_date < h["day"].isoformat() else ""))
    if not h["homework_due"]:
        print("    nothing due")
    if h["books_due"]:
        print("\n  Library books due back: " + ", ".join(
            f"{b.book_title} ({_d(b.due_date)})" for b in h["books_due"]))
    if h["events"]:
        print("\n  Coming up:")
        for e in h["events"]:
            print(f"    {_d(e.start_date):<11} {e.title}")
    home_lines(h)


def _lessons(lessons) -> None:
    from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
    times = {p.period: p for p in TT.periods()}
    if not lessons:
        print("    no lessons")
    for x in lessons:
        p = times.get(x.period)
        print(f"    {(p.label if p else 'P' + str(x.period)):<7} {(p.times if p else ''):<12} "
              f"{x.subject_name} ({x.group_code}) {x.teacher or ''}"
              + (f" room {x.room}" if x.room else ""))


def _timetable(principal, pid) -> None:
    from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
    t = PT.timetable(principal, pid)
    if not t["lessons"]:
        print("  No timetable yet.")
        return
    for week in range(1, t["weeks"] + 1):
        if t["weeks"] == 2:
            print(f"\n  {TT.WEEK_LABELS[week]}" + (" (this week)" if week == t["this_week"]
                                                  else ""))
        print("  " + f"{'':<8}" + "".join(f"{d:<10}" for d in TT.DAYS))
        for p in t["periods"]:
            cells = ["/".join(x.subject_code for x in t["grid"].get((week, d, p.period), []))
                     or "-" for d in range(1, 6)]
            print(f"  {p.label:<8}" + "".join(f"{c[:9]:<10}" for c in cells))


def _homework(principal, pid) -> None:
    h = PT.homework(principal, pid)
    print("\n  To do:")
    for i, (t, w) in enumerate(h["due"], 1):
        print(f"  {i:2d}) {_d(t.due_date):<11} {t.subject_code:<6} {t.title[:40]:<40} {w.status}")
    if not h["due"]:
        print("     nothing to do")
    print("\n  Handed in and marked:")
    for t, w in h["done"][:15]:
        mark = "" if w.mark is None else f"{w.mark:g}" + (f"/{t.points}" if t.points else "%")
        print(f"      {_d(t.due_date):<11} {t.subject_code:<6} {t.title[:30]:<30} "
              f"{w.status:<9} {mark:<7} {w.grade or ''} {w.feedback or ''}"[:150])
    if not h["due"]:
        return
    n = _prompt("\n  Number to see" + (" / hand in" if principal.is_student else "")
                + " (blank = back): ")
    if not (n.isdigit() and 1 <= int(n) <= len(h["due"])):
        return
    t, _w = h["due"][int(n) - 1]
    print(f"\n  {t.title} ({t.subject_name}) - due {t.due_date}\n\n  {t.instructions or ''}")
    if t.resources:
        print(f"\n  Resources: {t.resources}")
    if principal.is_student and _yes("\n  Hand it in now?"):
        from education_system.systems.secondary.modules.curriculum.domain import homework as HW
        note = _prompt("  Note for your teacher (optional): ")
        w = HW.hand_in(t.task_id, actor=principal, pupil_id=pid, note=note)
        print(f"  ✓ Handed in{' (late)' if w.status == 'Late' else ''}")


def _attendance(principal, pid) -> None:
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    a = PT.attendance(principal, pid)
    s = a["summary"]
    if s is None or not s.possible:
        print("  No attendance recorded yet this year.")
        return
    print(f"\n  {s.attendance_pct}% since {a['since']:%d %B %Y}: {s.attended}/{s.possible} "
          f"sessions, {s.authorised} authorised, {s.unauthorised} unauthorised, {s.late} late")
    rows = [m for m in a["recent"] if AT.category_of(m.code) != AT.PRESENT or m.code == "L"]
    print("\n  Absences and lates (last 60 days):" if rows else "\n  No absences or lates.")
    for m in rows:
        print(f"    {_d(m.date):<11} {m.session}  {m.code}  {m.label}")


def _grades(principal, pid) -> None:
    g = PT.grades(principal, pid)
    print(f"\n  Subjects ({g['year']}):")
    for r in g["overview"]:
        print(f"    {r['subject_code']:<8} {r['count']:>3} piece(s)  average "
              f"{'-' if r['avg_pct'] is None else str(r['avg_pct']) + '%':<7} latest "
              f"{r['latest_grade'] or '-'}")
    if not g["overview"]:
        print("    no marked work yet")
    print("\n  Marked work:")
    for e in g["entries"][:25]:
        marks = "" if e.marks_awarded is None else f"{e.marks_awarded:g}" + (
            f"/{e.max_marks:g}" if e.max_marks else "")
        print(f"    {_d(e.assessment_date):<11} {e.subject_code:<6} {e.assessment_name[:30]:<30} "
              f"{marks:<9} {e.grade or ''}")


def _reports(principal, pid) -> None:
    from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
    r = PT.reports(principal, pid)
    issued = r.get("issued") or []
    print("\n  School reports:")
    for i, (cy, rep) in enumerate(issued, 1):
        print(f"    {i}) {cy.title} - issued {(rep.issued_at or '')[:10]}"
              + (" (acknowledged)" if rep.acknowledged_at else ""))
    if not issued:
        print("    none issued yet")
    else:
        pick = _prompt("  Read which report (number, Enter to skip)? ")
        if pick.isdigit() and 1 <= int(pick) <= len(issued):
            rep = issued[int(pick) - 1][1]
            got = PT.school_report(principal, pid, rep.report_id)
            print("\n" + "\n".join("  " + line for line in got["text"].splitlines()))
            if principal.is_parent and not got["report"].acknowledged_at and _yes(
                    "\n  Confirm you have read this report?"):
                PT.acknowledge_report(principal, pid, rep.report_id)
                print("  Thank you - the school can see you have read it.")
    if r["point"]:
        pt, rows = r["point"]
        print(f"\n  {pt.name}:")
        for x in rows:
            print(f"    {x.subject_code:<8} working at {x.working_at or '-':<9} predicted "
                  f"{x.predicted or '-':<6} {x.comment or ''}")
    else:
        print("\n  No report published yet.")
    print("\n  Targets:")
    for x in r["targets"]:
        print(f"    {x['target'].subject_code:<8} target {x['target'].target_grade:<9} now "
              f"{x['current'] or '-':<9} {x['status']}")
    if not r["targets"]:
        print("    none set yet")
    m = r["mocks"]
    if m:
        print(f"\n  Mock exams - {m['series'].name}:")
        for x in m["subjects"]:
            marks = f"{MX._num(x['marks'])}/{MX._num(x['max'])}" if x["marks"] is not None else ""
            print(f"    {x['subject_name'][:22]:<22} {marks:<9} grade {x['grade'] or '-':<5} "
                  f"{x['note'] or x['vs_target']}")


def _exams(principal, pid) -> None:
    d = PT.exams(principal, pid)
    c = d["candidate"]
    print(f"\n  Candidate number: {c.candidate_number if c else 'not given yet'}")
    from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
    for sl in d.get("results", []):
        print("\n" + "\n".join("  " + line for line in ER.slip_text(sl).splitlines()))
    if not d["statements"]:
        print("  No exam entries have been confirmed yet.")
    for st in d["statements"]:
        s = st["series"]
        print(f"\n  Statement of entry - {s.name}"
              + (f" (results day {_d(s.results_day)})" if s.results_day else ""))
        for e in st["entries"]:
            print(f"    {e.subject_name[:28]:<28} {e.qualification:<10} {e.exam_board:<14} "
                  f"{e.entry_code:<8} {'' if e.tier == 'N/A' else e.tier}")
        if st["access"]:
            print(f"    Access arrangements: {st['access']}")
    print("\n  If anything is wrong, tell the exams officer straight away.")


def _behaviour(principal, pid) -> None:
    b = PT.behaviour(principal, pid)
    nxt = b["next"]
    print(f"\n  {b['positive_points']} positive point(s) this year"
          + (f" · house {b['house'].name}" if b["house"] else ""))
    if b["milestones"]:
        print("  Rewards: " + ", ".join(m["level"] for m in reversed(b["milestones"])))
    if nxt["next"]:
        print(f"  {nxt['needed']} more to {nxt['next']}")
    dts = b.get("detentions") or {"upcoming": [], "past": []}
    for d in dts["upcoming"]:
        print(f"  Detention: {_d(d.detention_date)}" + (f" {d.start_time}" if d.start_time else "")
              + f" {d.detention_type}, {d.duration_min} min - {d.reason[:50]}")
    if dts["past"]:
        print(f"  Detentions this year: {len(dts['past'])} past")
    for x in b.get("exclusions") or []:
        print(f"  {x['type']}: {x['period']}"
              + (f", back {_d(x['return_date'])}" if x["return_date"] else "")
              + f" - {x['reason'][:50]}")
    print("\n  Shared by school:")
    for e in b["entries"]:
        print(f"    {_d(e.entry_date)}  {e.incident_type[:18]:<18} {e.points:+3d}  "
              f"{e.description[:60]}")
    if not b["entries"]:
        print("    nothing yet")


def _library(principal, pid) -> None:
    lib = PT.library(principal, pid)
    print("\n  Books out:")
    for x in lib["out"]:
        print(f"    {x.book_title[:40]:<40} due {_d(x.due_date)}"
              + (f"  OVERDUE {x.days_overdue} day(s)" if x.days_overdue else ""))
    if not lib["out"]:
        print("    none")
    for h in lib["holds"]:
        print(f"  Reserved: {h.book_title} - {h.status}")


def _clubs(principal, pid) -> None:
    rows = PT.clubs(principal, pid)
    if not rows:
        print("  Not in any clubs.")
    for m, c in rows:
        print(f"    {(m.club_name or (c.name if c else ''))[:30]:<30} "
              f"{(c.when if c else ''):<20} {m.status}")


def _sixth_form(principal, pid) -> None:
    st = PT.sixth_form(principal, pid)
    if st["locked"] and not st["choices"]:
        print(f"  {st['locked']}")
        return
    if st["options"] is None:
        print("  The sixth form's course list isn't available just now.")
    known = st["results_known"]

    def line(c):
        need = "; ".join(c.get("requirements") or []) or "no entry requirements"
        if not known and c.get("requirements"):
            out = "awaited"
        else:
            out = (c["outcome"] if c.get("requirements") else "Met").lower()
        bad = "; ".join(x["detail"] for x in c.get("checks") or [] if x["outcome"] != "Met")
        block = "/".join(c.get("blocks") or [])
        block = (f"  [block {block}{', full' if c.get('full') else ''}]" if block else "")
        return (f"    {c['course']:<24} {out:<10} {need}" + (f"  ({bad})" if bad and known
                                                             else "") + block)
    if st["choices"]:
        print("\n  Your A-level choices:" if principal.is_student else "\n  A-level choices:")
        for c in st["chosen"]:
            print(line(c))
        if not known:
            print("  Results awaited.")
        elif st["all_met"]:
            print("  ✓ The results meet the entry requirements for all three courses.")
        else:
            bad = [c["course"] for c in st["chosen"] if c["outcome"] != "Met"]
            print(f"  ✗ The results don't meet the entry requirements for {', '.join(bad)}.")
            print("  Courses that can be chosen instead: "
                  + (", ".join(st["can_choose_from"]) or "none - talk to the sixth form"))
            if st["near_miss"]:
                print("  One grade short (ask the sixth form): " + ", ".join(st["near_miss"]))
    else:
        print("\n  No A-level choices yet - choose three.")
    for clash in (st.get("blocks") or {}).get("clashes") or []:
        print(f"  ✗ {clash}. Choose one course from each block.")
    lines = SC.block_lines(st.get("blocks"))
    if lines:
        print(f"\n  Option blocks ({st['blocks']['academic_year']}) - one course from each "
              "block:")
        for b in lines:
            print(f"    {b}")
    if st["locked"]:
        print(f"  {st['locked']}")
    if st["options"] and _yes("  See every course and what it needs?"):
        for c in st["options"]:
            print(line(c))
    if not (st["can_choose"] and st["options"]) or not _yes(
            "  Change choices now?" if st["choices"] else "  Choose now?"):
        return
    mine = {c.lower() for c in st["choices"]}
    names = st["eligible"] if known else [o["course"] for o in st["options"]
                                          if not o.get("full") or o["course"].lower() in mine]
    for i, n in enumerate(names, 1):
        print(f"     {i:2d}) {n}")
    raw = _prompt("    Three numbers, comma separated: ")
    nums = [int(n) for n in raw.replace(" ", "").split(",") if n.isdigit()]
    if len(nums) != 3 or not all(1 <= n <= len(names) for n in nums):
        print("    Give three numbers from the list.")
        return
    try:
        out = PT.choose_sixth_form(principal, pid, [names[n - 1] for n in nums])
        print("    ✓ Choices saved" + (" and the sixth form told" if out["sixth_form"]
                                       == "updated" else ""))
    except _ERRORS as e:
        _problem(e)


def _options(principal, pid) -> None:
    rounds = PT.options(principal, pid)
    if not rounds:
        print("  No options choices for this year group.")
        return
    for x in rounds:
        r = x["round"]
        print(f"\n  {r.name} ({r.status}) - choose {r.choices_required}"
              + (f" + {r.reserves_required} reserve(s)" if r.reserves_required else "")
              + (f" by {_d(r.closes_on)}" if r.closes_on else ""))
        for u in x["rules"]:
            print(f"    Rule: {u.label}")
        if x["allocations"]:
            print("    Your subjects: " + ", ".join(a.name for a in x["allocations"]))
        elif x["choices"]:
            print("    Choices: " + ", ".join(f"{c.rank}. {c.name}" + (" (reserve)" if
                                               c.is_reserve else "")
                                               for c in x["choices"].choices))
        else:
            print("    No choices made yet.")
        if x["can_choose"] and _yes("    Make / change choices now?"):
            subs = x["subjects"]
            for i, s in enumerate(subs, 1):
                g = x["guidance"].get(s.subject_id)
                print(f"     {i:2d}) {s.name}" + (f" - {g}" if g else ""))
            need = r.choices_required + r.reserves_required
            raw = _prompt(f"    Numbers in order, choices then reserves ({need}, comma "
                          "separated): ")
            nums = [int(n) for n in raw.replace(" ", "").split(",") if n.isdigit()]
            if len(nums) != need or not all(1 <= n <= len(subs) for n in nums):
                print(f"    Give exactly {need} numbers from the list.")
                continue
            ids = [subs[n - 1].subject_id for n in nums]
            try:
                PT.submit_options(principal, pid, r.round_id, ids[:r.choices_required],
                                  ids[r.choices_required:])
                print("    ✓ Choices sent to the school")
            except _ERRORS as e:
                _problem(e)


def _calendar(principal, pid) -> None:
    terms = PT.term_dates(principal, pid)
    print("\n  Term dates and holidays:")
    for name, start, end in terms:
        print(f"    {name[:28]:<28} {_d(start)} - {_d(end)}")
    if not terms:
        print("    not published yet")
    print("\n  Events (next 60 days):")
    rows = PT.calendar(principal, pid)
    for e in rows:
        print(f"    {_d(e.start_date):<11} {e.title}" + (f" - {e.location}" if e.location else "")
              + (" (cancelled)" if e.status == "Cancelled" else ""))
    if not rows:
        print("    none")


def _my_details(principal, pid) -> None:
    d = PT.details(principal, pid)
    p, f = d["pupil"], d["form"]
    print(f"\n  Name:          {p.full_name}"
          + (f" (known as {p.preferred_name})" if p.preferred_name else ""))
    print(f"  Admission no:  {p.admission_no}\n  Year:          {p.year_group}")
    print(f"  Form:          {f.get('form_group') or 'not set yet'}"
          + (f" - tutor {f['form_tutor']}" if f.get("form_tutor") else ""))
    print(f"  Date of birth: {p.date_of_birth}")
    if d.get("school_email"):
        print(f"  School e-mail: {d['school_email']}")
    if "contacts" in d:
        print("\n  Contacts the school holds:")
        for c in d["contacts"]:
            print(f"    {c.full_name} ({c.relationship}) {c.email or ''} {c.phone or ''}")
    print("\n  If anything is wrong, please tell the school office.")
