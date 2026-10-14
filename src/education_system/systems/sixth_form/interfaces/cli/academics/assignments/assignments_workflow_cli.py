"""CLI flows for coursework release, appeals and assessment instruments.

Covers the two workflow modules: :mod:`assignments_feedback` (release,
acknowledgement, appeals, turnaround, anonymity) and
:mod:`assignments_assessment` (objective questions, groups, peer and
self assessment), plus multi-part components from the core module.

Reached from the Assignments menu via "Release, appeals & assessment...".
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
    assignments_assessment as assess,
    assignments_feedback as feedback,
    assignments_marking as marking,
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


def _who(submission: data.Submission,
          assignment: data.Assignment) -> str:
    """Student label, honouring anonymous marking."""
    return feedback.display_student_id(submission, assignment)


# ── Release control (item 22) ──────────────────────────────────────

def pending_release_flow() -> None:
    print("\n═══ Awaiting Release ═══")
    rows = feedback.list_pending_release()
    if not rows:
        print("\n  (nothing marked is being held back)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Sub':>5}  {'Assign':>6}  {'Student':<10}  {'Name':<20}  "
          f"{'Marks':>6}  {'Grade':<5}  Policy")
    print("  " + "-" * 90)
    for s in rows:
        a = data.get_assignment(s.assignment_id)
        policy = a.release_policy if a else "—"
        if a and a.release_policy == "On date":
            policy += f" ({a.release_on or 'no date'})"
        print(f"  {s.submission_id:>5}  {s.assignment_id:>6}  "
              f"{s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:20]:<20}  "
              f"{_fmt(s.marks):>6}  {(s.grade or '—'):<5}  {policy}")
    print(f"\n  {len(rows)} result(s) held back.")
    _pause()


def release_assignment_flow() -> None:
    print("\n═══ Release Results ═══")
    print("  Publishes a whole class at once, so everybody finds out")
    print("  together rather than by looking over a shoulder.")
    try:
        a = _pick_assignment()
        by = _input("Released by", default=a.teacher or "")
        notify = _input("Email the students? (y/n)",
                         default="y").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    held = [s for s in feedback.list_pending_release(
        assignment_id=a.assignment_id)]
    print(f"\n  {len(held)} result(s) would become visible.")
    if not held:
        _pause()
        return
    if _input("Release now? Type 'yes'",
               default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    result = feedback.release_assignment(a.assignment_id,
                                          released_by=by or None,
                                          notify=notify)
    print(f"\n  ✓ {result.message}")
    _pause()


def release_one_flow() -> None:
    print("\n═══ Release One Result ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        by = _input("Released by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = feedback.release_submission(sub.submission_id,
                                           released_by=by or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Released to {out.student_id} "
          f"on {out.feedback_released_on}")
    _pause()


def unrelease_flow() -> None:
    print("\n═══ Withdraw a Released Result ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not sub.feedback_released:
        print("\n  That result is not currently released.")
        _pause()
        return
    if _input("Withdraw it from the student? Type 'yes'",
               default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    feedback.unrelease_submission(sub.submission_id)
    print(f"\n  ✓ Withdrawn from {sub.student_id}")
    _pause()


def release_due_flow() -> None:
    print("\n═══ Run Scheduled Releases ═══")
    print("  Publishes anything whose 'On date' release date has")
    print("  arrived. Safe to run every morning.")
    result = feedback.release_due()
    print(f"\n  ✓ {result.message}")
    _pause()


# ── Acknowledgement (item 23) ──────────────────────────────────────

def acknowledge_flow() -> None:
    print("\n═══ Record Feedback Acknowledgement ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        response = _multiline("Student response (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = feedback.acknowledge(sub.submission_id,
                                    response=response or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {out.student_id} acknowledged on "
          f"{out.acknowledged_on}")
    _pause()


def unacknowledged_flow() -> None:
    print("\n═══ Feedback Not Yet Acknowledged ═══")
    rows = feedback.list_unacknowledged()
    acknowledged, visible = feedback.acknowledgement_rate()
    if not rows:
        print(f"\n  (all {visible} released result(s) acknowledged)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Sub':>5}  {'Assign':>6}  {'Student':<10}  {'Name':<22}  "
          f"Released")
    print("  " + "-" * 80)
    for s in rows:
        print(f"  {s.submission_id:>5}  {s.assignment_id:>6}  "
              f"{s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:22]:<22}  "
              f"{s.feedback_released_on or '—'}")
    rate = (f"{100.0 * acknowledged / visible:.0f}%"
            if visible else "—")
    print(f"\n  {len(rows)} outstanding. "
          f"{acknowledged}/{visible} acknowledged ({rate}).")
    _pause()


def student_responses_flow() -> None:
    print("\n═══ Student Responses to Feedback ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _names()
    found = 0
    for s in data.list_submissions(assignment_id=a.assignment_id):
        if not s.student_response:
            continue
        found += 1
        print(f"\n  {s.student_id} — "
              f"{names.get(s.student_id, '?')}  "
              f"(acknowledged {s.acknowledged_on})")
        for line in s.student_response.splitlines():
            print(f"    {line}")
    if not found:
        print("\n  (no written responses)")
    _pause()


# ── Marking turnaround (item 20) ───────────────────────────────────

def turnaround_flow() -> None:
    print("\n═══ Marking Turnaround ═══")
    try:
        scope = _pick_from("Scope",
                            ["One assignment", "By teacher",
                             "Whole college"],
                            default="One assignment")
        assignment_id = None
        teacher = None
        if scope == "One assignment":
            assignment_id = _pick_assignment().assignment_id
        elif scope == "By teacher":
            teacher = _input("Teacher contains", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    report = feedback.turnaround_report(assignment_id=assignment_id,
                                         teacher=teacher)
    if not report.rows:
        print("\n  (nothing submitted)")
        _pause()
        return
    print()
    print(f"  {'Sub':>5}  {'Student':<10}  {'Name':<20}  "
          f"{'Submitted':<12}  {'Marked':<12}  Status")
    print("  " + "-" * 100)
    for row in report.rows:
        s = row.submission
        print(f"  {s.submission_id:>5}  {s.student_id:<10}  "
              f"{row.student_name[:20]:<20}  "
              f"{(s.submitted_on or '—'):<12}  "
              f"{(s.marked_on or '—'):<12}  {row.message}")
    print(f"\n  {report.message}")
    _pause()


def overdue_marking_flow() -> None:
    print("\n═══ Overdue Marking ═══")
    rows = feedback.overdue_marking()
    if not rows:
        print("\n  (nothing past its marking target)")
        _pause()
        return
    print()
    print(f"  {'Sub':>5}  {'Assign':>6}  {'Student':<10}  "
          f"{'Name':<20}  {'Waiting':>8}  {'Target':>7}")
    print("  " + "-" * 80)
    for row in rows:
        s = row.submission
        print(f"  {s.submission_id:>5}  {s.assignment_id:>6}  "
              f"{s.student_id:<10}  {row.student_name[:20]:<20}  "
              f"{(row.days_waiting or 0):>7}d  "
              f"{row.target_days:>6}d")
    print(f"\n  {len(rows)} piece(s) overdue for marking.")
    _pause()


def teacher_sla_flow() -> None:
    print("\n═══ Turnaround by Teacher ═══")
    summary = feedback.teacher_sla_summary()
    if not summary:
        print("\n  (no submissions)")
        _pause()
        return
    print()
    print(f"  {'Teacher':<26}  {'Marked':>10}  {'Average':>8}  "
          f"{'On target':>10}  {'Overdue':>8}")
    print("  " + "-" * 80)
    for who, report in summary.items():
        on_target = (f"{report.within_target_percent:g}%"
                     if report.within_target_percent is not None
                     else "—")
        print(f"  {who[:26]:<26}  "
              f"{len(report.marked):>4}/{len(report.rows):<5}  "
              f"{_fmt(report.average_days):>7}d  "
              f"{on_target:>10}  "
              f"{len(report.overdue):>8}")
    _pause()


# ── Anonymous marking (item 21) ────────────────────────────────────

def anonymity_flow() -> None:
    print("\n═══ Anonymous Marking ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    state = "on" if a.anonymous_marking else "off"
    print(f"\n  Anonymous marking is {state} for #{a.assignment_id}.")
    print("  Names are hidden until results are released.")
    subs = data.list_submissions(assignment_id=a.assignment_id)
    hidden = sum(1 for s in subs if feedback.is_anonymous(s, a))
    print(f"  {hidden}/{len(subs)} submission(s) currently anonymised.")
    try:
        want = _input(f"Turn anonymous marking "
                       f"{'off' if a.anonymous_marking else 'on'}? (y/n)",
                       default="n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if want.lower() not in ("y", "yes"):
        _pause()
        return
    data.update_assignment(a.assignment_id,
                            {"anonymous_marking":
                                not a.anonymous_marking})
    print(f"\n  ✓ Anonymous marking is now "
          f"{'off' if a.anonymous_marking else 'on'}.")
    _pause()


# ── Appeals (item 24) ──────────────────────────────────────────────

def raise_appeal_flow() -> None:
    print("\n═══ Raise an Appeal ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        kind = _pick_from("Appeal type", list(feedback.APPEAL_TYPES),
                           default=feedback.DEFAULT_APPEAL_TYPE)
        grounds = _multiline("Grounds for the appeal")
        by = _input("Raised by", default=sub.student_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    deadline = feedback.appeal_deadline(sub, a)
    if deadline:
        print(f"\n  Appeal window closes {deadline}.")
    try:
        appeal = feedback.raise_appeal(sub.submission_id,
                                        grounds=grounds,
                                        appeal_type=kind, raised_by=by)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        if "window closed" in str(e):
            if _input("Accept it as a late appeal anyway? (y/n)",
                       default="n").lower() in ("y", "yes"):
                appeal = feedback.raise_appeal(
                    sub.submission_id, grounds=grounds,
                    appeal_type=kind, raised_by=by,
                    allow_out_of_window=True)
                print(f"\n  ✓ Late appeal #{appeal.appeal_id} recorded")
        _pause()
        return
    print(f"\n  ✓ Appeal #{appeal.appeal_id} raised "
          f"(mark at appeal: {_fmt(appeal.marks_at_appeal)})")
    _pause()


def list_appeals_flow() -> None:
    print("\n═══ Appeals ═══")
    try:
        open_only = _input("Open appeals only? (y/n)",
                            default="y").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = feedback.list_appeals(open_only=open_only)
    if not rows:
        print("\n  (no appeals)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'#':>4}  {'Sub':>5}  {'Student':<10}  {'Name':<18}  "
          f"{'Type':<22}  {'Status':<14}  Raised")
    print("  " + "-" * 105)
    for appeal in rows:
        sub = data.get_submission(appeal.submission_id)
        sid = sub.student_id if sub else "?"
        print(f"  {appeal.appeal_id:>4}  {appeal.submission_id:>5}  "
              f"{sid:<10}  {names.get(sid, '?')[:18]:<18}  "
              f"{appeal.appeal_type[:22]:<22}  "
              f"{appeal.status:<14}  {appeal.raised_on}")
    summary = feedback.appeal_summary()
    print(f"\n  {summary['_total']} total, {summary['_open']} open, "
          f"{summary['_upheld']} upheld.")
    _pause()


def view_appeal_flow() -> None:
    print("\n═══ View Appeal ═══")
    try:
        appeal_id = int(_input("Appeal id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    appeal = feedback.get_appeal(appeal_id)
    if appeal is None:
        print(f"\n  ✗ No appeal #{appeal_id}")
        _pause()
        return
    sub = data.get_submission(appeal.submission_id)
    print(f"\n    Appeal #{appeal.appeal_id}  [{appeal.status}]")
    print(f"    Submission    : #{appeal.submission_id}"
          + (f"  ({sub.student_id})" if sub else ""))
    print(f"    Type          : {appeal.appeal_type}")
    print(f"    Raised        : {appeal.raised_on} "
          f"by {appeal.raised_by or '—'}")
    print(f"    Mark at appeal: {_fmt(appeal.marks_at_appeal)} "
          f"({appeal.grade_at_appeal or '—'})")
    print(f"    Reviewer      : {appeal.reviewer or '—'}"
          + (f"  (from {appeal.review_started_on})"
              if appeal.review_started_on else ""))
    print("\n    Grounds:")
    for line in appeal.grounds.splitlines():
        print(f"      {line}")
    if appeal.outcome:
        print(f"\n    Outcome ({appeal.outcome_on}):")
        for line in appeal.outcome.splitlines():
            print(f"      {line}")
        if appeal.mark_changed is not None:
            print(f"      Mark changed by {appeal.mark_changed:+g} "
                  f"to {_fmt(appeal.marks_after)}")
    _pause()


def start_review_flow() -> None:
    print("\n═══ Assign an Appeal for Review ═══")
    try:
        appeal_id = int(_input("Appeal id", allow_empty=False))
        reviewer = _input("Reviewer", allow_empty=False)
        notes = _input("Notes")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        out = feedback.start_review(appeal_id, reviewer=reviewer,
                                     notes=notes or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Appeal #{out.appeal_id} assigned to {out.reviewer}")
    _pause()


def resolve_appeal_flow() -> None:
    print("\n═══ Resolve an Appeal ═══")
    try:
        appeal_id = int(_input("Appeal id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    appeal = feedback.get_appeal(appeal_id)
    if appeal is None:
        print(f"\n  ✗ No appeal #{appeal_id}")
        _pause()
        return
    print(f"\n  Mark at appeal: {_fmt(appeal.marks_at_appeal)}")
    try:
        status = _pick_from("Outcome",
                             list(feedback.CLOSED_APPEAL_STATUSES),
                             default="Rejected")
        outcome = _multiline("Outcome reasoning")
        new_marks = None
        if status in ("Upheld", "Partly upheld"):
            raw = _input("New mark (blank to leave it unchanged)")
            if raw:
                new_marks = float(raw)
        by = _input("Resolved by", allow_empty=False)
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        out = feedback.resolve_appeal(appeal_id, status=status,
                                       outcome=outcome,
                                       new_marks=new_marks,
                                       resolved_by=by)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Appeal #{out.appeal_id} {out.status}")
    if out.mark_changed is not None:
        print(f"    Mark {_fmt(out.marks_at_appeal)} → "
              f"{_fmt(out.marks_after)} ({out.mark_changed:+g})")
    _pause()


# ── Objective questions (item 25) ──────────────────────────────────

def list_questions_flow() -> None:
    print("\n═══ Objective Questions ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = assess.list_questions(a.assignment_id)
    if not rows:
        print("\n  (no objective questions)")
        _pause()
        return
    for q in rows:
        print(f"\n  #{q.question_id}  Q{q.position}  "
              f"[{q.question_type}]  {q.marks:g} mark(s)")
        print(f"      {q.prompt}")
        if q.option_list:
            print(f"      Options: {' / '.join(q.option_list)}")
        print(f"      Key: {' or '.join(q.key_list)}"
              + (f"  (±{q.tolerance:g})" if q.tolerance else ""))
    print(f"\n  {len(rows)} question(s), "
          f"{assess.questions_total(a.assignment_id):g} marks total.")
    _pause()


def add_question_flow() -> None:
    print("\n═══ Add Objective Question ═══")
    print("  Options and answer keys are pipe-separated, so a multiple")
    print("  choice is 'London|Paris|Rome' with key 'Paris', and a short")
    print("  answer accepting synonyms is 'photosynthesis|photo-synthesis'.")
    try:
        a = _pick_assignment()
        kind = _pick_from("Type", list(assess.QUESTION_TYPES),
                           default=assess.DEFAULT_QUESTION_TYPE)
        prompt = _multiline("Prompt")
        options = ""
        if kind in ("Multiple choice", "Multiple response"):
            options = _input("Options (pipe-separated)",
                              allow_empty=False)
        answer_key = _input("Answer key (pipe-separated)",
                             allow_empty=False)
        marks = _input("Marks", default="1")
        tolerance = ""
        if kind == "Numeric":
            tolerance = _input("Tolerance (± )", default="0")
        case_sensitive = _input("Case sensitive? (y/n)",
                                 default="n").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        q = assess.add_question(a.assignment_id, {
            "question_type": kind, "prompt": prompt,
            "options": options, "answer_key": answer_key,
            "marks": marks, "tolerance": tolerance or None,
            "case_sensitive": case_sensitive})
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added question #{q.question_id} "
          f"({assess.questions_total(a.assignment_id):g} marks total)")
    _pause()


def delete_question_flow() -> None:
    print("\n═══ Delete Objective Question ═══")
    try:
        qid = int(_input("Question id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if _input(f"Delete question #{qid} and every answer to it? "
              "Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if assess.delete_question(qid):
        print(f"\n  ✓ Deleted question #{qid}")
    else:
        print(f"\n  ✗ No question #{qid}")
    _pause()


def enter_answers_flow() -> None:
    print("\n═══ Enter Answers ═══")
    try:
        a = _pick_assignment()
        questions = assess.list_questions(a.assignment_id)
        if not questions:
            print("\n  This assignment has no objective questions.")
            _pause()
            return
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = {x.question_id: x
                for x in assess.list_answers(sub.submission_id)}
    try:
        for q in questions:
            prior = existing.get(q.question_id)
            print(f"\n  Q{q.position} [{q.question_type}] "
                  f"{q.marks:g} mark(s)")
            print(f"    {q.prompt}")
            if q.option_list:
                print(f"    Options: {' / '.join(q.option_list)}")
            raw = _input("Answer",
                          default=(prior.response if prior else "") or "")
            if not raw:
                continue
            answer = assess.record_answer(sub.submission_id,
                                           q.question_id, response=raw)
            verdict = ("✓" if answer.is_correct else "✗")
            print(f"    {verdict} {_fmt(answer.marks_awarded)} mark(s)")
    except _UserAbort:
        print("\n  Stopped — answers entered so far are saved.")
        _pause()
        return
    result = assess.auto_mark(sub.submission_id)
    print(f"\n  {result.message}")
    _pause()


def auto_mark_flow() -> None:
    print("\n═══ Auto-Mark ═══")
    try:
        a = _pick_assignment()
        scope = _pick_from("Scope", ["Whole assignment",
                                       "One submission"],
                            default="Whole assignment")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if scope == "One submission":
        try:
            sub = _pick_submission(a.assignment_id)
        except _UserAbort:
            print("\n  Cancelled.")
            return
        print(f"\n  {assess.auto_mark(sub.submission_id).message}")
    else:
        result = assess.auto_mark_assignment(a.assignment_id)
        print(f"\n  ✓ Marked {result['submissions_marked']} "
              f"submission(s), average "
              f"{_fmt(result['average_marks'])} marks")
    _pause()


def override_answer_flow() -> None:
    print("\n═══ Override an Auto-Marked Answer ═══")
    print("  Auto-marking is confidently wrong often enough — an unusual")
    print("  phrasing, a typo in the key — that overriding is a proper")
    print("  action rather than an edit to the answer key.")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        qid = int(_input("Question id", allow_empty=False))
        marks = float(_input("Marks to award", allow_empty=False))
        by = _input("Overridden by", allow_empty=False)
        reason = _input("Reason")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        out = assess.override_answer(sub.submission_id, qid,
                                      marks=marks, overridden_by=by,
                                      reason=reason or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Now {_fmt(out.marks_awarded)} mark(s)")
    print(f"    {assess.auto_mark(sub.submission_id).message}")
    _pause()


def question_analysis_flow() -> None:
    print("\n═══ Question Analysis ═══")
    print("  The question everybody missed is a teaching problem, not a")
    print("  marking one.")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = assess.question_analysis(a.assignment_id)
    if not rows:
        print("\n  (no objective questions)")
        _pause()
        return
    print()
    print(f"  {'Q':>3}  {'Answered':>9}  {'Correct':>8}  "
          f"{'Facility':>9}  Prompt")
    print("  " + "-" * 90)
    for row in sorted(rows, key=lambda r: (r["facility"] is None,
                                             r["facility"] or 0)):
        facility = (f"{row['facility']:g}%"
                    if row["facility"] is not None else "—")
        print(f"  {row['position']:>3}  {row['answered']:>9}  "
              f"{row['correct']:>8}  {facility:>9}  "
              f"{row['prompt'][:45]}")
    _pause()


# ── Group assignments (item 26) ────────────────────────────────────

def list_groups_flow() -> None:
    print("\n═══ Groups ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    groups = assess.list_groups(a.assignment_id)
    if not groups:
        print("\n  (no groups)")
    for group in groups:
        detail = assess.get_group_detail(group.group_id)
        assert detail is not None
        print(f"\n  #{group.group_id}  {group.name}  "
              f"— {detail.message}")
        for m in detail.members:
            effective = m.effective_marks(group.group_marks)
            line = (f"      {m.student_id:<10} "
                    f"{m.student_name[:22]:<22} {m.role:<10}")
            if m.adjustment:
                line += f" {m.adjustment:+g}"
                if m.adjustment_reason:
                    line += f" ({m.adjustment_reason})"
            if effective is not None:
                line += f"  →  {effective:g}"
            print(line)
    ungrouped = assess.ungrouped_submissions(a.assignment_id)
    if ungrouped:
        print(f"\n  Not in a group ({len(ungrouped)}): "
              + ", ".join(s.student_id for s in ungrouped))
    _pause()


def create_group_flow() -> None:
    print("\n═══ Create Group ═══")
    try:
        a = _pick_assignment()
        name = _input("Group name", allow_empty=False)
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        group = assess.create_group(a.assignment_id, name,
                                     notes=notes or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created group #{group.group_id} {group.name!r}")
    _pause()


def add_group_member_flow() -> None:
    print("\n═══ Add Group Member ═══")
    try:
        a = _pick_assignment()
        groups = assess.list_groups(a.assignment_id)
        if not groups:
            print("\n  Create a group first.")
            _pause()
            return
        label = _pick_from("Group",
                            [f"#{g.group_id} {g.name}" for g in groups])
        group = groups[[f"#{g.group_id} {g.name}"
                         for g in groups].index(label)]
        sub = _pick_submission(a.assignment_id)
        role = _pick_from("Role", list(assess.GROUP_ROLES),
                           default=assess.DEFAULT_GROUP_ROLE)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        member = assess.add_group_member(group.group_id,
                                          sub.submission_id, role=role)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {member.student_id} added to {group.name!r} "
          f"as {member.role}")
    _pause()


def group_adjustment_flow() -> None:
    print("\n═══ Per-Member Adjustment ═══")
    print("  Three students who did the work and one who didn't cannot")
    print("  all take the same mark.")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        adjustment = float(_input("Adjustment (e.g. -5 or +3)",
                                    allow_empty=False))
        reason = _input("Reason", allow_empty=False)
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        member = assess.set_member_adjustment(
            sub.submission_id, adjustment=adjustment, reason=reason)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    group = assess.get_group(member.group_id)
    effective = (member.effective_marks(group.group_marks)
                 if group else None)
    print(f"\n  ✓ {member.student_id}: {member.adjustment:+g}"
          + (f"  →  {effective:g}" if effective is not None else ""))
    _pause()


def mark_group_flow() -> None:
    print("\n═══ Mark a Group ═══")
    try:
        a = _pick_assignment()
        groups = assess.list_groups(a.assignment_id)
        if not groups:
            print("\n  No groups on this assignment.")
            _pause()
            return
        label = _pick_from("Group",
                            [f"#{g.group_id} {g.name}" for g in groups])
        group = groups[[f"#{g.group_id} {g.name}"
                         for g in groups].index(label)]
        marks = float(_input(f"Group mark (0-{a.max_marks or '?'})",
                               allow_empty=False))
        by = _input("Marked by", default=a.teacher or "")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        assess.set_group_marks(group.group_id, marks,
                                marked_by=by or None)
        applied = assess.apply_group_marks(group.group_id,
                                            marked_by=by or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Applied to {len(applied)} member(s):")
    for s in applied:
        print(f"      {s.student_id:<10}  {_fmt(s.marks)}"
              + (f"  ({s.group_adjustment:+g})"
                  if s.group_adjustment else ""))
    _pause()


# ── Peer assessment (item 27) ──────────────────────────────────────

def record_peer_flow() -> None:
    print("\n═══ Record a Peer Review ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        reviewer = _pick_student()
        criteria = marking.list_criteria(a.assignment_id)
        criterion_id = None
        if criteria:
            choice = _pick_from(
                "Score against",
                ["Overall"] + [f"#{c.criterion_id} {c.label}"
                                for c in criteria],
                default="Overall")
            if choice != "Overall":
                criterion_id = int(choice.split()[0].lstrip("#"))
        marks = float(_input("Marks", allow_empty=False))
        comment = _multiline("Comment")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        assess.record_peer_review(sub.submission_id,
                                   reviewer_student=reviewer,
                                   marks=marks,
                                   criterion_id=criterion_id,
                                   comment=comment or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    summary = assess.peer_summary(sub.submission_id)
    print(f"\n  ✓ Recorded. {summary.message}")
    _pause()


def peer_summary_flow() -> None:
    print("\n═══ Peer Assessment ═══")
    try:
        a = _pick_assignment()
        mode = _pick_from("Combine by", list(assess.PEER_SCORE_MODES),
                           default=assess.DEFAULT_PEER_SCORE_MODE)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _names()
    weight_label = (f"{a.peer_assessment_weight:g}%"
                    if a.peer_assessment_weight else "not set")
    print(f"\n  Peer weight: {weight_label}")
    print()
    print(f"  {'Sub':>5}  {'Student':<10}  {'Name':<20}  "
          f"{'Reviewers':>9}  {'Peer':>6}  {'Spread':>7}  {'Mark':>6}")
    print("  " + "-" * 85)
    for s in data.list_submissions(assignment_id=a.assignment_id):
        summary = assess.peer_summary(s.submission_id, mode=mode,
                                       store=False)
        if not summary.reviewer_count:
            continue
        print(f"  {s.submission_id:>5}  {s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:20]:<20}  "
              f"{summary.reviewer_count:>9}  "
              f"{_fmt(summary.score):>6}  "
              f"{_fmt(summary.spread):>7}  {_fmt(s.marks):>6}")
    print(f"\n  {assess.peer_review_coverage(a.assignment_id)}")
    _pause()


def blend_peer_flow() -> None:
    print("\n═══ Blend Teacher and Peer Marks ═══")
    try:
        a = _pick_assignment()
        if not a.peer_assessment_weight:
            print("\n  This assignment has no peer weighting set.")
            print("  Set one on the assignment first (Edit assignment).")
            _pause()
            return
        sub = _pick_submission(a.assignment_id)
        teacher_marks = float(_input("Teacher's mark",
                                       allow_empty=False))
        mode = _pick_from("Combine peers by",
                           list(assess.PEER_SCORE_MODES),
                           default=assess.DEFAULT_PEER_SCORE_MODE)
        by = _input("Marked by", default=a.teacher or "")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    blended = assess.blended_marks(sub.submission_id,
                                    teacher_marks=teacher_marks,
                                    mode=mode)
    if blended is None:
        print("\n  No peer reviews — the teacher's mark stands.")
    else:
        print(f"\n  Teacher {teacher_marks:g}  →  blended {blended:g} "
              f"at {a.peer_assessment_weight:g}% peer weight")
    if _input("Apply? (y/n)", default="y").lower() not in ("y", "yes"):
        _pause()
        return
    out = assess.apply_peer_blend(sub.submission_id,
                                   teacher_marks=teacher_marks,
                                   marked_by=by or None, mode=mode)
    print(f"\n  ✓ {out.student_id} marked {_fmt(out.marks)} "
          f"(grade {out.grade or '—'})")
    _pause()


# ── Self-assessment (item 28) ──────────────────────────────────────

def record_self_flow() -> None:
    print("\n═══ Record a Self-Assessment ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        predicted = float(_input(
            f"Student's predicted mark (0-{a.max_marks or '?'})",
            allow_empty=False))
        note = _multiline("Student's note")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        assess.record_self_assessment(sub.submission_id,
                                       predicted_marks=predicted,
                                       note=note or None)
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Recorded for {sub.student_id}")
    _pause()


def self_assessment_flow() -> None:
    print("\n═══ Self-Assessment vs Actual ═══")
    print("  A class that consistently overestimates has not understood")
    print("  the mark scheme — a more useful finding than any one gap.")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = assess.self_assessment_report(a.assignment_id)
    if not rows:
        print("\n  (no self-assessments)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Sub':>5}  {'Student':<10}  {'Name':<20}  "
          f"{'Predicted':>9}  {'Actual':>7}  {'Gap':>6}  Judgement")
    print("  " + "-" * 90)
    for row in rows:
        sub = data.get_submission(row.submission_id)
        sid = sub.student_id if sub else "?"
        print(f"  {row.submission_id:>5}  {sid:<10}  "
              f"{names.get(sid, '?')[:20]:<20}  "
              f"{_fmt(row.predicted):>9}  {_fmt(row.actual):>7}  "
              f"{(f'{row.gap:+g}' if row.gap is not None else '—'):>6}  "
              f"{row.accuracy or '—'}")
    summary = assess.calibration_summary(a.assignment_id)
    print(f"\n  {summary['assessed']} assessed; average gap "
          f"{_fmt(summary['average_gap'])}; "
          f"{summary['over']} over, {summary['under']} under, "
          f"{summary['accurate']} accurate.")
    missing = assess.missing_self_assessments(a.assignment_id)
    if missing:
        print(f"  {len(missing)} student(s) still owe one: "
              + ", ".join(s.student_id for s in missing))
    _pause()


# ── Multi-part assignments (item 29) ───────────────────────────────

def components_flow() -> None:
    print("\n═══ Components ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    components = data.list_components(a.assignment_id)
    if not components:
        if a.parent_assignment_id:
            parent = data.get_assignment(a.parent_assignment_id)
            print(f"\n  This is a component of "
                  f"#{a.parent_assignment_id} "
                  f"{parent.title if parent else ''} "
                  f"({_fmt(a.component_weight)}% weight).")
        else:
            print("\n  (no components — this is a standalone assignment)")
        _pause()
        return
    weights = data.component_weights(a.assignment_id)
    print(f"\n  #{a.assignment_id} {a.title} — "
          f"{len(components)} component(s)")
    print()
    print(f"  {'#':>4}  {'Due':<12}  {'Max':>6}  {'Weight':>7}  Title")
    print("  " + "-" * 70)
    for c in components:
        print(f"  {c.assignment_id:>4}  {(c.due_date or '—'):<12}  "
              f"{_fmt(c.max_marks):>6}  "
              f"{weights.get(c.assignment_id, 0):>6g}%  {c.title}")
    total = sum(weights.values())
    if abs(total - 100.0) > 0.001:
        print(f"\n  ⚠ Weights total {total:g}%, not 100%.")
    _pause()


def link_component_flow() -> None:
    print("\n═══ Link a Component to a Parent ═══")
    print("  Composition is one level deep: an NEA has components, but")
    print("  a component cannot itself have components.")
    try:
        print("\n  First pick the COMPONENT:")
        child = _pick_assignment()
        print("\n  Now pick the PARENT:")
        parent = _pick_assignment()
        weight = _input("Weight % (blank for an even split)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_assignment(child.assignment_id, {
            "parent_assignment_id": parent.assignment_id,
            "component_weight": weight or None})
    except data.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{child.assignment_id} is now a component of "
          f"#{parent.assignment_id}")
    _pause()


def unlink_component_flow() -> None:
    print("\n═══ Unlink a Component ═══")
    try:
        child = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not child.parent_assignment_id:
        print("\n  That assignment is not a component.")
        _pause()
        return
    data.update_assignment(child.assignment_id,
                            {"parent_assignment_id": None,
                             "component_weight": None})
    print(f"\n  ✓ #{child.assignment_id} is standalone again")
    _pause()


def rollup_flow() -> None:
    print("\n═══ Component Rollup ═══")
    print("  Combines component percentages by weight, so components")
    print("  with different maximums count correctly against each other.")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not data.list_components(a.assignment_id):
        print("\n  That assignment has no components.")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Student':<10}  {'Name':<20}  {'Weighted':>9}  "
          f"{'Overall':>8}  {'Grade':<5}  Detail")
    print("  " + "-" * 100)
    for sub in data.list_submissions(assignment_id=a.assignment_id):
        roll = data.component_rollup(a.assignment_id, sub.student_id)
        detail = ", ".join(
            f"{c.assignment.title[:12]} {_fmt(c.percent)}%"
            for c in roll.components)
        weighted = (f"{roll.weighted_percent:g}%"
                    if roll.weighted_percent is not None else "—")
        print(f"  {sub.student_id:<10}  "
              f"{names.get(sub.student_id, '?')[:20]:<20}  "
              f"{weighted:>9}  "
              f"{_fmt(roll.overall_marks):>8}  "
              f"{(roll.grade or '—'):<5}  {detail[:40]}")
    try:
        if _input("Write these onto the parent assignment? (y/n)",
                   default="n").lower() not in ("y", "yes"):
            _pause()
            return
        by = _input("Marked by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    result = data.rollup_all(a.assignment_id, marked_by=by or None)
    print(f"\n  ✓ Applied to {result['applied']} student(s), "
          f"{result['skipped']} incomplete.")
    _pause()


# ── Submenu ────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Awaiting release",          pending_release_flow),
    ("Release results",           release_assignment_flow),
    ("Release one result",        release_one_flow),
    ("Withdraw a result",         unrelease_flow),
    ("Run scheduled releases",    release_due_flow),
    ("─" * 6,                     lambda: None),
    ("Record acknowledgement",    acknowledge_flow),
    ("Not yet acknowledged",      unacknowledged_flow),
    ("Student responses",         student_responses_flow),
    ("─" * 6,                     lambda: None),
    ("Marking turnaround",        turnaround_flow),
    ("Overdue marking",           overdue_marking_flow),
    ("Turnaround by teacher",     teacher_sla_flow),
    ("Anonymous marking",         anonymity_flow),
    ("─" * 6,                     lambda: None),
    ("Raise an appeal",           raise_appeal_flow),
    ("List appeals",              list_appeals_flow),
    ("View appeal",               view_appeal_flow),
    ("Assign for review",         start_review_flow),
    ("Resolve appeal",            resolve_appeal_flow),
    ("─" * 6,                     lambda: None),
    ("Objective questions",       list_questions_flow),
    ("Add question",              add_question_flow),
    ("Delete question",           delete_question_flow),
    ("Enter answers",             enter_answers_flow),
    ("Auto-mark",                 auto_mark_flow),
    ("Override an answer",        override_answer_flow),
    ("Question analysis",         question_analysis_flow),
    ("─" * 6,                     lambda: None),
    ("Groups",                    list_groups_flow),
    ("Create group",              create_group_flow),
    ("Add group member",          add_group_member_flow),
    ("Per-member adjustment",     group_adjustment_flow),
    ("Mark a group",              mark_group_flow),
    ("─" * 6,                     lambda: None),
    ("Record peer review",        record_peer_flow),
    ("Peer assessment summary",   peer_summary_flow),
    ("Blend teacher and peer",    blend_peer_flow),
    ("─" * 6,                     lambda: None),
    ("Record self-assessment",    record_self_flow),
    ("Self-assessment vs actual", self_assessment_flow),
    ("─" * 6,                     lambda: None),
    ("Components",                components_flow),
    ("Link a component",          link_component_flow),
    ("Unlink a component",        unlink_component_flow),
    ("Component rollup",          rollup_flow),
]


def run() -> None:
    feedback.init_db()
    assess.init_db()
    while True:
        print("\n── Release, Appeals & Assessment ──")
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
            logger.exception("Workflow CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Workflow":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Workflow CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
