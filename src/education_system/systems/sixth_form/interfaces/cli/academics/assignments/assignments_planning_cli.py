"""CLI flows for authoring, reusing and scheduling coursework.

Covers :mod:`assignments_catalogue` (specifications, templates, the
department library, variants, workload) and
:mod:`assignments_scheduling` (publishing, reminders, chasers, parent
visibility, calendar).

Reached from the Assignments menu via "Planning, reuse & scheduling...".
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
    assignments_catalogue as cat,
    assignments_scheduling as sched,
)
from education_system.systems.sixth_form.interfaces.cli.academics.assignments.assignments_cli import (
    _input,
    _multiline,
    _pause,
    _pick_assignment,
    _pick_from,
    _pick_student,
    _pick_submission,
    _UserAbort,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)


def _names() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


def _fmt(value: float | None, dash: str = "—") -> str:
    return f"{value:g}" if value is not None else dash


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower() in ("y", "yes")


# ── Specification metadata (item 30) ───────────────────────────────

def set_specification_flow() -> None:
    print("\n═══ Specification Details ═══")
    try:
        a = _pick_assignment()
        qualification = _pick_from(
            "Qualification", [""] + list(cat.QUALIFICATIONS),
            default=a.qualification or "")
        board = _pick_from("Exam board", [""] + list(cat.EXAM_BOARDS),
                            default=a.exam_board or "")
        spec = _input("Specification code", default=a.spec_code or "")
        unit = _input("Unit code", default=a.unit_code or "")
        component = _input("Component code",
                            default=a.component_code or "")
        objectives = _input(
            f"Assessment objectives, comma separated "
            f"({'/'.join(cat.COMMON_OBJECTIVES)})",
            default=a.assessment_objectives or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = cat.set_specification(
            a.assignment_id, qualification=qualification or None,
            exam_board=board or None, spec_code=spec or None,
            unit_code=unit or None, component_code=component or None,
            objectives=objectives or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {out.spec_reference or '(no reference set)'}")
    print(f"    Objectives: {', '.join(out.objective_list) or '—'}")
    _pause()


def objective_coverage_flow() -> None:
    print("\n═══ Assessment Objective Coverage ═══")
    print("  The gap is the point: an AO with no coursework behind it")
    print("  is one the cohort has never been assessed on.")
    try:
        subject = _input("Subject (blank for all)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    coverage = cat.objective_coverage(subject_name=subject or None)
    if not coverage:
        print("\n  (no assignments carry assessment objectives)")
        _pause()
        return
    print()
    for objective, count in coverage.items():
        bar = "█" * min(count, 40)
        print(f"    {objective:<8} {count:>3}  {bar}")
    if subject:
        gaps = cat.specification_gaps(subject)
        print(f"\n  Not evidenced in {subject}: "
              + (", ".join(gaps) if gaps else "none"))
    _pause()


def by_specification_flow() -> None:
    print("\n═══ Find by Specification ═══")
    try:
        board = _input("Exam board (blank for any)")
        spec = _input("Spec code (blank for any)")
        unit = _input("Unit code (blank for any)")
        objective = _input("Assessment objective (blank for any)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = cat.list_by_specification(
        exam_board=board or None, spec_code=spec or None,
        unit_code=unit or None, objective=objective or None)
    if not rows:
        print("\n  (nothing matches)")
        _pause()
        return
    print()
    print(f"  {'#':>4}  {'Subject':<16}  {'Due':<12}  "
          f"{'Reference':<30}  Title")
    print("  " + "-" * 100)
    for a in rows:
        print(f"  {a.assignment_id:>4}  {a.subject_name[:16]:<16}  "
              f"{(a.due_date or '—'):<12}  "
              f"{a.spec_reference[:30]:<30}  {a.title[:30]}")
    print(f"\n  {len(rows)} assignment(s).")
    _pause()


# ── Templates and library (items 31 and 32) ────────────────────────

def library_flow() -> None:
    print("\n═══ Department Library ═══")
    try:
        subject = _input("Subject (blank for all)")
        query = _input("Text contains (blank for all)")
        templates_only = _yes("Templates only? (y/n)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = cat.list_library(subject_name=subject or None,
                             query=query or None,
                             templates_only=templates_only)
    if not rows:
        print("\n  (nothing shared yet — use 'Save as template' or")
        print("   'Share with department' on an assignment)")
        _pause()
        return
    print()
    for entry in rows:
        print(f"  #{entry.assignment.assignment_id:<4} {entry.label}")
        print(f"        {entry.message}")
    print(f"\n  {len(rows)} entry/entries, most-reused first.")
    _pause()


def save_template_flow() -> None:
    print("\n═══ Save as Template ═══")
    try:
        a = _pick_assignment()
        name = _input("Template name", default=a.title)
        share = _yes("Share with the department? (y/n)", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    out = cat.save_as_template(a.assignment_id, template_name=name,
                                share=share)
    print(f"\n  ✓ #{out.assignment_id} saved as "
          f"{out.template_name!r}"
          + ("  (shared)" if out.shared_with_department else ""))
    _pause()


def share_flow() -> None:
    print("\n═══ Share / Unshare with Department ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    now = a.shared_with_department
    print(f"\n  #{a.assignment_id} is currently "
          f"{'shared' if now else 'not shared'}.")
    if not _yes(f"Turn sharing {'off' if now else 'on'}? (y/n)"):
        print("\n  Cancelled.")
        return
    cat.share_with_department(a.assignment_id, shared=not now)
    print(f"\n  ✓ Sharing is now {'off' if now else 'on'}.")
    _pause()


def clone_flow() -> None:
    print("\n═══ Clone an Assignment ═══")
    print("  Copies the design — brief, rubric, questions, variants,")
    print("  teaching material. Never copies students, submissions or")
    print("  marks: a new run starts empty.")
    try:
        source = _pick_assignment()
        title = _input("New title", default=f"{source.title} (copy)")
        set_date = _input("Set date (YYYY-MM-DD)",
                           default=data._dt.date.today().isoformat())
        due_date = _input("Due date (YYYY-MM-DD)")
        teacher = _input("Teacher", default=source.teacher or "")
        copy_rubric = _yes("Copy the rubric? (y/n)", default="y")
        copy_questions = _yes("Copy objective questions? (y/n)",
                               default="y")
        copy_variants = _yes("Copy variants? (y/n)", default="y")
        copy_files = _yes("Copy teaching material? (y/n)", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        result = cat.clone_assignment(
            source.assignment_id, title=title, set_date=set_date,
            due_date=due_date or None, teacher=teacher or None,
            copy_rubric=copy_rubric, copy_questions=copy_questions,
            copy_variants=copy_variants,
            copy_attachments=copy_files)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Cloned {result.message}")
    _pause()


def lineage_flow() -> None:
    print("\n═══ Where Did This Come From? ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    chain = cat.clone_lineage(a.assignment_id)
    if not chain:
        print(f"\n  #{a.assignment_id} was written from scratch.")
        _pause()
        return
    print(f"\n  #{a.assignment_id} {a.title}")
    for i, parent in enumerate(chain, 1):
        print(f"  {'  ' * i}↳ cloned from #{parent.assignment_id} "
              f"{parent.title}"
              + (f"  ({parent.set_date})" if parent.set_date else ""))
    _pause()


# ── Variants (item 33) ─────────────────────────────────────────────

def list_variants_flow() -> None:
    print("\n═══ Differentiated Variants ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = cat.list_variants(a.assignment_id)
    if not rows:
        print("\n  (no variants — everyone gets the base brief)")
        _pause()
        return
    print()
    for v in rows:
        star = " *default" if v.is_default else ""
        print(f"  #{v.variant_id:<4} {v.label}{star}")
        print(f"        max {_fmt(v.max_marks)}  ·  "
              f"{_fmt(v.estimated_hours)}h")
        if v.brief:
            print(f"        {v.brief.splitlines()[0][:60]}")
    print(f"\n  Spread: {cat.variant_spread(a.assignment_id)}")
    _pause()


def add_variant_flow() -> None:
    print("\n═══ Add a Variant ═══")
    try:
        a = _pick_assignment()
        name = _input("Name", allow_empty=False)
        tier = _pick_from("Tier", list(cat.VARIANT_TIERS),
                           default=cat.DEFAULT_VARIANT_TIER)
        brief = _multiline("Brief for this variant")
        hours = _input("Estimated hours")
        max_marks = _input("Max marks (blank to use the assignment's)")
        is_default = _yes("Make this the default variant? (y/n)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = cat.add_variant(a.assignment_id, {
            "name": name, "tier": tier, "brief": brief,
            "estimated_hours": hours or None,
            "max_marks": max_marks or None, "is_default": is_default})
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added variant #{v.variant_id} {v.label}")
    _pause()


def assign_variant_flow() -> None:
    print("\n═══ Issue a Variant ═══")
    try:
        a = _pick_assignment()
        variants = cat.list_variants(a.assignment_id)
        if not variants:
            print("\n  This assignment has no variants.")
            _pause()
            return
        sub = _pick_submission(a.assignment_id)
        labels = ["(base brief)"] + [f"#{v.variant_id} {v.label}"
                                       for v in variants]
        choice = _pick_from("Variant", labels, default=labels[0])
    except _UserAbort:
        print("\n  Cancelled.")
        return
    variant_id = (None if choice == "(base brief)"
                  else int(choice.split()[0].lstrip("#")))
    try:
        out = cat.assign_variant(sub.submission_id, variant_id)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {out.student_id} → "
          f"{choice if variant_id else 'base brief'}")
    _pause()


def default_variants_flow() -> None:
    print("\n═══ Apply Default Variant ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    n = cat.assign_default_variants(a.assignment_id)
    if not n:
        print("\n  Nothing to do — no default variant, or everyone "
              "already has one.")
    else:
        print(f"\n  ✓ {n} student(s) put on the default variant.")
    _pause()


# ── Workload (item 34) ─────────────────────────────────────────────

def student_workload_flow() -> None:
    print("\n═══ Student Workload ═══")
    print("  Hours land in the week the work is due, which is where")
    print("  students actually feel them.")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    report = cat.student_workload(sid)
    if not report.weeks:
        print(f"\n  {report.message}")
        _pause()
        return
    print()
    for week in report.weeks:
        flag = "  ⚠" if week.is_heavy else ""
        print(f"  {week.week_start}  {week.hours:>6g}h{flag}")
        for _aid, title, hours in week.assignments:
            print(f"        {hours:>5g}h  {title[:45]}")
    print(f"\n  {report.message}")
    _pause()


def heavy_weeks_flow() -> None:
    print("\n═══ Overloaded Weeks ═══")
    print("  No single department can see that its 6-hour essay landed")
    print("  in the same week as two others.")
    try:
        year = _input("Year group (blank for all)")
        threshold = _input("Hours threshold",
                            default=f"{cat.WEEKLY_HOURS_WARNING:g}")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = cat.heavy_weeks(year_group=year or None,
                                threshold=float(threshold))
    except (ValueError, data.ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (nobody is over the threshold)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Student':<10}  {'Name':<22}  {'Week':<12}  "
          f"{'Hours':>6}  Assignments")
    print("  " + "-" * 95)
    for student_id, week in rows:
        titles = ", ".join(t for _a, t, _h in week.assignments)
        print(f"  {student_id:<10}  {names.get(student_id, '?')[:22]:<22}  "
              f"{week.week_start:<12}  {week.hours:>6g}  {titles[:35]}")
    print(f"\n  {len(rows)} overloaded student-week(s).")
    _pause()


def assignment_hours_flow() -> None:
    print("\n═══ Assignment Workload ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    summary = cat.assignment_hours_summary(a.assignment_id)
    print(f"\n  Base estimate    : "
          f"{_fmt(summary['base_hours'])}h")
    print(f"  Students         : {summary['students']}")
    print(f"  With an estimate : {summary['with_estimate']}")
    print(f"  Total cohort time: {summary['total_hours']:g}h")
    print(f"  Average per head : {_fmt(summary['average_hours'])}h")
    _pause()


# ── Publishing (item 35) ───────────────────────────────────────────

def publish_flow() -> None:
    print("\n═══ Publish an Assignment ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if a.published_on:
        print(f"\n  Already published on {a.published_on}.")
        _pause()
        return
    if not _yes(f"Publish #{a.assignment_id} and email the students? "
                 "(y/n)", default="y"):
        print("\n  Cancelled.")
        return
    out = sched.publish_assignment(a.assignment_id)
    print(f"\n  ✓ Published on {out.published_on} "
          f"(status {out.status})")
    _pause()


def scheduled_flow() -> None:
    print("\n═══ Scheduled to Publish ═══")
    rows = sched.list_scheduled()
    if not rows:
        print("\n  (nothing waiting for its set date)")
        _pause()
        return
    print()
    print(f"  {'#':>4}  {'Set date':<12}  {'Due':<12}  "
          f"{'Subject':<16}  Title")
    print("  " + "-" * 80)
    for a in rows:
        print(f"  {a.assignment_id:>4}  {(a.set_date or '—'):<12}  "
              f"{(a.due_date or '—'):<12}  "
              f"{a.subject_name[:16]:<16}  {a.title[:30]}")
    print(f"\n  {len(rows)} waiting.")
    _pause()


def publish_due_flow() -> None:
    print("\n═══ Run Scheduled Publishing ═══")
    preview = sched.publish_due(notify=False)
    print(f"\n  {preview.message}")
    for line in preview.detail[:10]:
        print(f"    {line}")
    _pause()


# ── Reminders and chasers (items 36 and 37) ────────────────────────

def reminders_flow() -> None:
    print("\n═══ Send Due-Date Reminders ═══")
    print("  Each offset fires once per student, so a catch-up run")
    print("  nudges rather than nags.")
    try:
        scope = _pick_from("Scope", ["Whole college", "One assignment"],
                            default="Whole college")
        assignment_id = None
        if scope == "One assignment":
            assignment_id = _pick_assignment().assignment_id
    except _UserAbort:
        print("\n  Cancelled.")
        return
    preview = sched.sweep_reminders(assignment_id=assignment_id,
                                     dry_run=True)
    print(f"\n  {preview.scanned} reminder(s) would go out:")
    for line in preview.detail[:15]:
        print(f"    {line}")
    if not preview.scanned:
        _pause()
        return
    if not _yes("Send them? (y/n)", default="y"):
        print("\n  Cancelled.")
        return
    result = sched.sweep_reminders(assignment_id=assignment_id)
    print(f"\n  ✓ {result.message}")
    _pause()


def reminder_settings_flow() -> None:
    print("\n═══ Reminder Schedule ═══")
    try:
        a = _pick_assignment()
        college_default = ",".join(
            str(d) for d in sched.DEFAULT_REMINDER_DAYS)
        current = (a.reminder_days
                   or f"college default ({college_default})")
        print(f"\n  Current: {current}")
        days = _input("Days before due, comma separated "
                       "(blank for the default)",
                       default=a.reminder_days or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.update_assignment(a.assignment_id,
                                      {"reminder_days": days or None})
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Reminders at "
          f"{out.reminder_days or 'the college default'}")
    _pause()


def chasers_flow() -> None:
    print("\n═══ Chase Missing Work ═══")
    print("  Escalates one step at a time: student, then tutor, then")
    print(f"  home. At least {sched.CHASE_INTERVAL_DAYS} days between "
          f"steps.")
    try:
        scope = _pick_from("Scope", ["Whole college", "One assignment"],
                            default="Whole college")
        assignment_id = None
        if scope == "One assignment":
            assignment_id = _pick_assignment().assignment_id
    except _UserAbort:
        print("\n  Cancelled.")
        return
    preview = sched.sweep_chasers(assignment_id=assignment_id,
                                   dry_run=True)
    print(f"\n  {preview.scanned} scanned; would escalate "
          f"{len(preview.detail)}:")
    for line in preview.detail[:15]:
        print(f"    {line}")
    if not preview.detail:
        _pause()
        return
    if not _yes("Send them? (y/n)", default="y"):
        print("\n  Cancelled.")
        return
    result = sched.sweep_chasers(assignment_id=assignment_id)
    print(f"\n  ✓ {result.message}")
    _pause()


def escalation_flow() -> None:
    print("\n═══ Escalation Report ═══")
    rows = sched.escalation_report()
    if not rows:
        print("\n  (nobody is being chased)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Sub':>5}  {'Assign':>6}  {'Student':<10}  "
          f"{'Name':<22}  {'Level':<10}  Last chased")
    print("  " + "-" * 85)
    for sub, level in rows:
        print(f"  {sub.submission_id:>5}  {sub.assignment_id:>6}  "
              f"{sub.student_id:<10}  "
              f"{names.get(sub.student_id, '?')[:22]:<22}  "
              f"{level:<10}  {sub.last_chased_on or '—'}")
    print(f"\n  {len(rows)} student(s) mid-escalation.")
    _pause()


def notice_log_flow() -> None:
    print("\n═══ Notice Log ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = sched.list_notices(assignment_id=a.assignment_id)
    if not rows:
        print("\n  (nothing sent for this assignment)")
        _pause()
        return
    print()
    print(f"  {'Sent':<12}  {'Sub':>5}  {'Kind':<8}  "
          f"{'What':<32}  {'To':<12}  Delivered")
    print("  " + "-" * 90)
    for n in rows:
        print(f"  {n.sent_on:<12}  {n.submission_id:>5}  "
              f"{n.kind:<8}  {n.label[:32]:<32}  "
              f"{(n.recipient or '—')[:12]:<12}  "
              f"{'yes' if n.delivered else 'NO'}")
    print(f"\n  {len(rows)} notice(s).")
    _pause()


# ── Parent visibility (item 38) ────────────────────────────────────

def parent_view_flow() -> None:
    print("\n═══ Parent View ═══")
    print("  Exactly what a guardian sees. Marks appear only once")
    print("  released — a parent must not see a result before the")
    print("  student does.")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = sched.parent_view(sid)
    if not rows:
        print("\n  (nothing visible to a guardian)")
        _pause()
        return
    print()
    print(f"  {'Due':<12}  {'Subject':<16}  {'State':<14}  "
          f"{'Marks':>10}  {'Grade':<6}  Title")
    print("  " + "-" * 100)
    for v in rows:
        marks = ("—" if v.marks is None
                 else f"{v.marks:g}/{_fmt(v.max_marks)}")
        print(f"  {(v.due_date or '—'):<12}  "
              f"{v.subject_name[:16]:<16}  {v.state:<14}  "
              f"{marks:>10}  {(v.grade or '—'):<6}  {v.title[:28]}")
    print(f"\n  {sched.parent_summary(sid)}")
    _pause()


def parent_visibility_flow() -> None:
    print("\n═══ Parent Visibility ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    now = a.parent_visible
    print(f"\n  #{a.assignment_id} is currently "
          f"{'visible' if now else 'hidden'} to guardians.")
    if not _yes(f"{'Hide' if now else 'Show'} it? (y/n)"):
        print("\n  Cancelled.")
        return
    sched.set_parent_visibility(a.assignment_id, visible=not now)
    print(f"\n  ✓ Now {'hidden' if now else 'visible'}.")
    _pause()


# ── Calendar (item 39) ─────────────────────────────────────────────

def calendar_sync_flow() -> None:
    print("\n═══ Sync Deadlines to the Calendar ═══")
    result = sched.sync_calendar()
    print(f"\n  {result.message}")
    for line in result.detail[:15]:
        print(f"    {line}")
    _pause()


def calendar_remove_flow() -> None:
    print("\n═══ Remove a Deadline from the Calendar ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not a.calendar_event_id:
        print("\n  That assignment is not on the calendar.")
        _pause()
        return
    if sched.remove_from_calendar(a.assignment_id):
        print(f"\n  ✓ Removed #{a.assignment_id} from the calendar.")
    _pause()


def clashes_flow() -> None:
    print("\n═══ Deadline Clashes ═══")
    print("  Sometimes a busy week is unavoidable — but a head of year")
    print("  should see it before the students do.")
    try:
        year = _input("Year group (blank for all)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = sched.deadline_clashes(year_group=year or None)
    if not rows:
        print("\n  (no week has more than one deadline)")
        _pause()
        return
    print()
    for clash in rows:
        print(f"  Week of {clash['week_start']}: "
              f"{clash['count']} deadline(s) across "
              f"{', '.join(clash['subjects'])}")
        for aid, title, due in clash["assignments"]:
            print(f"        {due}  #{aid}  {title[:40]}")
    print(f"\n  {len(rows)} busy week(s).")
    _pause()


# ── The daily job ──────────────────────────────────────────────────

def daily_job_flow() -> None:
    print("\n═══ Run the Daily Coursework Job ═══")
    print("  Publishes what is due, marks missing work, sends reminders")
    print("  and chasers, and syncs the calendar. Safe to run twice.")
    if not _yes("Run it now? (y/n)", default="y"):
        print("\n  Cancelled.")
        return
    results = sched.run_daily()
    print()
    for name, result in results.items():
        print(f"    {name:<16} {result.message}")
    _pause()


# ── Submenu ────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Specification details",     set_specification_flow),
    ("Objective coverage",        objective_coverage_flow),
    ("Find by specification",     by_specification_flow),
    ("─" * 6,                     lambda: None),
    ("Department library",        library_flow),
    ("Save as template",          save_template_flow),
    ("Share / unshare",           share_flow),
    ("Clone an assignment",       clone_flow),
    ("Clone lineage",             lineage_flow),
    ("─" * 6,                     lambda: None),
    ("Variants",                  list_variants_flow),
    ("Add a variant",             add_variant_flow),
    ("Issue a variant",           assign_variant_flow),
    ("Apply default variant",     default_variants_flow),
    ("─" * 6,                     lambda: None),
    ("Student workload",          student_workload_flow),
    ("Overloaded weeks",          heavy_weeks_flow),
    ("Assignment workload",       assignment_hours_flow),
    ("─" * 6,                     lambda: None),
    ("Publish an assignment",     publish_flow),
    ("Scheduled to publish",      scheduled_flow),
    ("Run scheduled publishing",  publish_due_flow),
    ("─" * 6,                     lambda: None),
    ("Send reminders",            reminders_flow),
    ("Reminder schedule",         reminder_settings_flow),
    ("Chase missing work",        chasers_flow),
    ("Escalation report",         escalation_flow),
    ("Notice log",                notice_log_flow),
    ("─" * 6,                     lambda: None),
    ("Parent view",               parent_view_flow),
    ("Parent visibility",         parent_visibility_flow),
    ("─" * 6,                     lambda: None),
    ("Sync calendar",             calendar_sync_flow),
    ("Remove from calendar",      calendar_remove_flow),
    ("Deadline clashes",          clashes_flow),
    ("─" * 6,                     lambda: None),
    ("Run the daily job",         daily_job_flow),
]


def run() -> None:
    cat.init_db()
    sched.init_db()
    while True:
        print("\n── Planning, Reuse & Scheduling ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Planning CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Planning":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Planning CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
