"""CLI flows for coursework marking, moderation and rubrics.

Sibling to :mod:`assignments_cli`, which handles the assignments and
submissions themselves. Reached from the Assignments menu via
"Marking...".
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
    assignments_marking as marking,
)
from education_system.systems.sixth_form.domain.academics.assignments.assignments_cli import (
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
from education_system.systems.sixth_form.domain.academics.assignments.assignments_marking import (
    COMMENT_CATEGORIES,
    Criterion,
    MARKER_ROLES,
    SAMPLE_BANDS,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ── Shared helpers ─────────────────────────────────────────────────

def _names() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


def _pick_criterion(assignment_id: int) -> Criterion:
    rows = marking.list_criteria(assignment_id)
    if not rows:
        print("    This assignment has no rubric criteria yet.")
        raise _UserAbort
    print("\n  Criteria:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>3}) #{c.criterion_id}  {c.label[:44]:<44}  "
              f"max {c.max_marks:g}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((c for c in rows if c.criterion_id == n), None)
            if match:
                return match
        print("    No matching criterion.")


def _pick_role(default: str = marking.DEFAULT_MARKER_ROLE) -> str:
    return _pick_from("Marker role", list(MARKER_ROLES), default=default)


def _float_or_none(raw: str, label: str) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        print(f"  ✗ {label} must be a number.")
        raise _UserAbort from None


# ── Rubric criteria (item 12) ──────────────────────────────────────

def list_criteria_flow() -> None:
    print("\n═══ Rubric ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = marking.list_criteria(a.assignment_id)
    if not rows:
        print("\n  (no criteria — the mark scheme is still a text blob)")
        _pause()
        return
    print()
    print(f"  {'#':>4}  {'Pos':>3}  {'Code':<8}  {'Title':<30}  "
          f"{'Max':>6}  {'Weight':>7}  AO")
    print("  " + "-" * 90)
    for c in rows:
        print(f"  {c.criterion_id:>4}  {c.position:>3}  "
              f"{(c.code or '—'):<8}  {c.title[:30]:<30}  "
              f"{c.max_marks:>6g}  "
              f"{(f'{c.weight_percent:g}%' if c.weight_percent else '—'):>7}  "
              f"{c.assessment_objective or '—'}")
    print(f"\n  {marking.rubric_total(a.assignment_id).message}")
    _pause()


def add_criterion_flow() -> None:
    print("\n═══ Add Rubric Criterion ═══")
    try:
        a = _pick_assignment()
        code = _input("Code (e.g. AO1)")
        title = _input("Title", allow_empty=False)
        max_marks = _input("Max marks", allow_empty=False)
        weight = _input("Weight % (optional)")
        ao = _input("Assessment objective (optional)")
        descriptor = _multiline("Descriptor")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = marking.add_criterion(a.assignment_id, {
            "code": code, "title": title, "max_marks": max_marks,
            "weight_percent": weight or None,
            "assessment_objective": ao, "descriptor": descriptor,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added criterion #{c.criterion_id} {c.label}")
    print(f"    {marking.rubric_total(a.assignment_id).message}")
    _pause()


def edit_criterion_flow() -> None:
    print("\n═══ Edit Rubric Criterion ═══")
    try:
        a = _pick_assignment()
        c = _pick_criterion(a.assignment_id)
        code = _input("Code", default=c.code or "")
        title = _input("Title", default=c.title, allow_empty=False)
        max_marks = _input("Max marks", default=f"{c.max_marks:g}")
        weight = _input("Weight %",
                         default=(f"{c.weight_percent:g}"
                                   if c.weight_percent else ""))
        ao = _input("Assessment objective",
                     default=c.assessment_objective or "")
        descriptor = _multiline("Descriptor", default=c.descriptor or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        marking.update_criterion(c.criterion_id, {
            "code": code, "title": title, "max_marks": max_marks,
            "weight_percent": weight or None,
            "assessment_objective": ao, "descriptor": descriptor,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated criterion #{c.criterion_id}")
    print(f"    {marking.rubric_total(a.assignment_id).message}")
    _pause()


def delete_criterion_flow() -> None:
    print("\n═══ Delete Rubric Criterion ═══")
    try:
        a = _pick_assignment()
        c = _pick_criterion(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete {c.label!r}? Every mark against it goes too. "
              "Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if marking.delete_criterion(c.criterion_id):
        print(f"\n  ✓ Deleted criterion #{c.criterion_id}")
    _pause()


def reorder_criteria_flow() -> None:
    print("\n═══ Reorder Rubric ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = marking.list_criteria(a.assignment_id)
    if len(rows) < 2:
        print("\n  Nothing to reorder.")
        _pause()
        return
    print("\n  Current order:")
    for c in rows:
        print(f"    #{c.criterion_id}  {c.label}")
    try:
        raw = _input("New order (criterion ids, comma separated)",
                      allow_empty=False)
        ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        for c in marking.reorder_criteria(a.assignment_id, ids):
            print(f"    {c.position}. {c.label}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


# ── Per-criterion marking (item 13) ────────────────────────────────

def mark_by_criterion_flow() -> None:
    print("\n═══ Mark by Criterion ═══")
    try:
        a = _pick_assignment()
        criteria = marking.list_criteria(a.assignment_id)
        if not criteria:
            print("\n  This assignment has no rubric to mark against.")
            _pause()
            return
        sub = _pick_submission(a.assignment_id)
        role = _pick_role()
        marked_by = _input("Marked by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return

    existing = {m.criterion_id: m for m in
                marking.list_criterion_marks(sub.submission_id,
                                              role=role)}
    print(f"\n  Marking {sub.student_id} — blank keeps the current score.")
    try:
        for c in criteria:
            prior = existing.get(c.criterion_id)
            current = (f"{prior.marks:g}"
                       if prior and prior.marks is not None else "")
            print(f"\n  {c.label}  (max {c.max_marks:g})")
            if c.descriptor:
                for line in c.descriptor.splitlines()[:4]:
                    print(f"    | {line}")
            raw = _input("Marks", default=current)
            if not raw:
                continue
            comment = _input("Comment",
                              default=(prior.comment if prior else "") or "")
            marking.set_criterion_mark(
                sub.submission_id, c.criterion_id, marks=float(raw),
                role=role, comment=comment or None,
                marked_by=marked_by or None)
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Stopped — scores entered so far are saved.")
        _pause()
        return

    scored, total = marking.criterion_coverage(sub.submission_id,
                                                role=role)
    subtotal = marking.criterion_total(sub.submission_id, role=role)
    print(f"\n  {scored}/{total} criteria scored, total "
          f"{subtotal if subtotal is not None else '—'}")
    if scored < total:
        print("  Finish the rubric before totalling it onto the mark.")
        _pause()
        return
    if _input("Apply this total as the mark? (y/n)",
               default="y").lower() not in ("y", "yes"):
        _pause()
        return
    try:
        out = marking.apply_criterion_total(sub.submission_id, role=role,
                                             marked_by=marked_by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_mark_outcome(out, a)
    _pause()


def _print_mark_outcome(sub: data.Submission,
                         assignment: data.Assignment) -> None:
    print(f"\n  ✓ Raw mark   : "
          f"{sub.raw_marks if sub.raw_marks is not None else '—'}")
    if sub.penalty_percent:
        print(f"    Penalty    : {sub.penalty_percent:g}% "
              f"({sub.penalty_days} day(s) late)")
    print(f"    Final mark : "
          f"{sub.marks if sub.marks is not None else '—'}"
          f" / {assignment.max_marks or '?'}")
    print(f"    Grade      : {sub.grade or '—'}")


def view_criterion_marks_flow() -> None:
    print("\n═══ Criterion Marks ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    criteria = {c.criterion_id: c
                for c in marking.list_criteria(a.assignment_id)}
    for role in MARKER_ROLES:
        rows = marking.list_criterion_marks(sub.submission_id, role=role)
        if not rows:
            continue
        print(f"\n  {role} marker:")
        for m in rows:
            c = criteria.get(m.criterion_id)
            label = c.label if c else f"#{m.criterion_id}"
            cap = f"/{c.max_marks:g}" if c else ""
            print(f"    {label[:40]:<40}  "
                  f"{(f'{m.marks:g}' if m.marks is not None else '—'):>6}"
                  f"{cap}")
            if m.comment:
                print(f"      {m.comment}")
        total = marking.criterion_total(sub.submission_id, role=role)
        print(f"    {'TOTAL':<40}  "
              f"{(f'{total:g}' if total is not None else '—'):>6}")
    _pause()


# ── Grade boundaries (item 14) ─────────────────────────────────────

def boundaries_flow() -> None:
    print("\n═══ Grade Boundaries ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    current = marking.get_grade_boundaries(a.assignment_id)
    print(f"\n  Assignment max marks: {a.max_marks or '—'}")
    if current and current.is_set:
        print("  Current raw-mark thresholds:")
        for letter, value in current.as_pairs():
            print(f"    {letter:<3} : "
                  f"{value if value is not None else '(percentage default)'}")
    else:
        print("  No overrides — the college percentage defaults apply:")
        for letter, pct in marking.DEFAULT_BOUNDARIES_PCT:
            print(f"    {letter:<3} : {pct:g}%")
    print("\n  Enter raw marks, blank to use the percentage default.")
    payload: dict[str, Any] = {}
    try:
        for letter in ("A*", "A", "B", "C", "D", "E"):
            prior = ""
            if current:
                col = {"A*": "a_star"}.get(letter, letter.lower())
                value = getattr(current, col)
                prior = f"{value:g}" if value is not None else ""
            payload[letter] = _input(f"{letter} boundary", default=prior)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = marking.set_grade_boundaries(a.assignment_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print("\n  ✓ Saved:")
    for letter, value in out.as_pairs():
        print(f"    {letter:<3} : "
              f"{value if value is not None else '(percentage default)'}")
    if _input("Re-grade every marked submission now? (y/n)",
               default="y").lower() in ("y", "yes"):
        n = _regrade_assignment(a)
        print(f"  ✓ Re-graded {n} submission(s).")
    _pause()


def _regrade_assignment(assignment: data.Assignment) -> int:
    """Re-derive letters after a boundary change."""
    n = 0
    for sub in data.list_submissions(assignment_id=assignment.assignment_id):
        if sub.raw_marks is None:
            continue
        marking.apply_marks(sub.submission_id, raw_marks=sub.raw_marks,
                             marked_by=sub.marked_by, source="manual",
                             reason="Grade boundaries changed")
        n += 1
    return n


def clear_boundaries_flow() -> None:
    print("\n═══ Clear Grade Boundaries ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input("Clear the overrides and fall back to percentages? "
              "Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if marking.clear_grade_boundaries(a.assignment_id):
        print(f"\n  ✓ Cleared. Re-graded "
              f"{_regrade_assignment(a)} submission(s).")
    else:
        print("\n  Nothing to clear.")
    _pause()


# ── Second marking and moderation (item 15) ────────────────────────

def record_mark_flow() -> None:
    print("\n═══ Record a Mark ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        role = _pick_role()
        marks = _input(f"Marks (0-{a.max_marks or '?'})",
                        allow_empty=False)
        feedback = _multiline("Feedback")
        marked_by = _input("Marked by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = marking.record_mark(sub.submission_id, role=role,
                                 marks=float(marks),
                                 feedback=feedback or None,
                                 marked_by=marked_by or None)
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {m.role} mark {m.marks:g} recorded "
          f"(grade {m.grade or '—'})")
    state = marking.moderation_state(sub.submission_id)
    print(f"    {state.message}")
    if role == "First" and not state.is_double_marked:
        if _input("Apply as the submission's mark now? (y/n)",
                   default="y").lower() in ("y", "yes"):
            out = marking.apply_marks(sub.submission_id,
                                       raw_marks=float(marks),
                                       feedback=feedback or None,
                                       marked_by=marked_by or None,
                                       source="manual")
            _print_mark_outcome(out, a)
    elif state.needs_moderation:
        print("    ⚠ This submission now needs moderation.")
    _pause()


def view_marks_flow() -> None:
    print("\n═══ Marks on a Submission ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = marking.list_marks(sub.submission_id)
    if not rows:
        print("\n  (no marks recorded)")
    else:
        print()
        print(f"  {'Role':<10}  {'Marks':>7}  {'Grade':<6}  "
              f"{'By':<16}  On")
        print("  " + "-" * 70)
        for m in rows:
            print(f"  {m.role:<10}  "
                  f"{(f'{m.marks:g}' if m.marks is not None else '—'):>7}  "
                  f"{(m.grade or '—'):<6}  "
                  f"{(m.marked_by or '—')[:16]:<16}  "
                  f"{m.marked_on or '—'}")
    current = data.get_submission(sub.submission_id)
    print(f"\n  {marking.moderation_state(sub.submission_id).message}")
    if current:
        _print_mark_outcome(current, a)
    _pause()


def moderation_queue_flow() -> None:
    print("\n═══ Moderation Queue ═══")
    rows = marking.list_for_moderation()
    if not rows:
        print("\n  (nothing outside tolerance)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Sub':>5}  {'Student':<10}  {'Name':<20}  "
          f"{'First':>6}  {'Second':>7}  {'Gap':>5}  Tolerance")
    print("  " + "-" * 80)
    for m in rows:
        sub = data.get_submission(m.submission_id)
        sid = sub.student_id if sub else "?"
        print(f"  {m.submission_id:>5}  {sid:<10}  "
              f"{names.get(sid, '?')[:20]:<20}  "
              f"{m.first:>6g}  {m.second:>7g}  "
              f"{(m.discrepancy or 0):>5g}  "
              f"{m.tolerance if m.tolerance is not None else '—'}")
    print(f"\n  {len(rows)} submission(s) need a moderator.")
    _pause()


def resolve_moderation_flow() -> None:
    print("\n═══ Resolve Moderation ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    state = marking.moderation_state(sub.submission_id)
    print(f"\n  {state.message}")
    if not state.is_double_marked:
        print("  Nothing to resolve — this needs a first and second mark.")
        _pause()
        return
    try:
        marks = _input(f"Agreed mark (first {state.first:g}, "
                        f"second {state.second:g})", allow_empty=False)
        note = _input("Note")
        by = _input("Resolved by", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = marking.resolve_moderation(sub.submission_id,
                                          marks=float(marks),
                                          resolved_by=by,
                                          note=note or None)
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_mark_outcome(out, a)
    _pause()


# ── Standardisation samples (item 16) ──────────────────────────────

def flag_sample_flow() -> None:
    print("\n═══ Flag Standardisation Sample ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        band = _pick_from("Band", list(SAMPLE_BANDS), default="Middle")
        note = _input("Note")
        by = _input("Flagged by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = marking.flag_sample(sub.submission_id, band=band,
                                   note=note or None,
                                   flagged_by=by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{out.submission_id} flagged as {out.sample_band}")
    _pause()


def unflag_sample_flow() -> None:
    print("\n═══ Remove From Sample ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    marking.unflag_sample(sub.submission_id)
    print(f"\n  ✓ #{sub.submission_id} removed from the sample")
    _pause()


def auto_sample_flow() -> None:
    print("\n═══ Auto-Select Standardisation Sample ═══")
    print("  Takes the highest, lowest and middle marks so the moderator")
    print("  sees the range rather than the department's favourites.")
    try:
        a = _pick_assignment()
        per_band = _input("Scripts per band", default="2")
        by = _input("Selected by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = marking.auto_select_sample(a.assignment_id,
                                           per_band=int(per_band),
                                           flagged_by=by or None)
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    names = _names()
    print()
    for s in rows:
        print(f"    {s.sample_band:<10}  {s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:22]:<22}  "
              f"{s.marks:g}")
    print(f"\n  ✓ {len(rows)} script(s) sampled.")
    _pause()


def list_samples_flow() -> None:
    print("\n═══ Standardisation Sample ═══")
    rows = marking.list_samples()
    if not rows:
        print("\n  (nothing sampled)")
        _pause()
        return
    names = _names()
    print()
    print(f"  {'Sub':>5}  {'Assign':>6}  {'Band':<10}  {'Student':<10}  "
          f"{'Name':<20}  {'Marks':>6}  Note")
    print("  " + "-" * 100)
    for s in rows:
        print(f"  {s.submission_id:>5}  {s.assignment_id:>6}  "
              f"{(s.sample_band or '—'):<10}  {s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:20]:<20}  "
              f"{(f'{s.marks:g}' if s.marks is not None else '—'):>6}  "
              f"{(s.sample_note or '—')[:30]}")
    print(f"\n  {len(rows)} sampled.")
    _pause()


# ── Late penalties (item 10) ───────────────────────────────────────

def penalties_flow() -> None:
    print("\n═══ Late Penalties ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not a.late_penalty_percent_per_day:
        print("\n  This assignment has no late penalty policy set.")
        print("  Set one on the assignment (Edit assignment).")
    else:
        print(f"\n  Policy: {a.late_penalty_percent_per_day:g}% per day"
              + (f", capped at {a.late_penalty_cap_percent:g}%"
                  if a.late_penalty_cap_percent else "")
              + (f", after {a.late_penalty_grace_days} grace day(s)"
                  if a.late_penalty_grace_days else ""))
    names = _names()
    rows = data.list_submissions(assignment_id=a.assignment_id)
    print()
    print(f"  {'Sub':>5}  {'Student':<10}  {'Name':<18}  "
          f"{'Raw':>6}  {'Pen':>6}  {'Final':>6}  Status")
    print("  " + "-" * 90)
    for s in rows:
        penalty = marking.compute_late_penalty(a, s)
        print(f"  {s.submission_id:>5}  {s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:18]:<18}  "
              f"{(f'{s.raw_marks:g}' if s.raw_marks is not None else '—'):>6}  "
              f"{(f'{s.penalty_percent:g}%' if s.penalty_percent else '—'):>6}  "
              f"{(f'{s.marks:g}' if s.marks is not None else '—'):>6}  "
              f"{penalty.message}")
    _pause()


def waive_penalty_flow() -> None:
    print("\n═══ Waive Late Penalty ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        reason = _input("Reason", allow_empty=False)
        by = _input("Waived by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = marking.waive_penalty(sub.submission_id, reason=reason,
                                     waived_by=by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print("\n  ✓ Penalty waived.")
    _print_mark_outcome(out, a)
    _pause()


def restore_penalty_flow() -> None:
    print("\n═══ Restore Late Penalty ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        by = _input("Restored by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    out = marking.restore_penalty(sub.submission_id,
                                   restored_by=by or None)
    print("\n  ✓ Waiver withdrawn — the policy applies again.")
    _print_mark_outcome(out, a)
    _pause()


# ── Access arrangements (item 11) ──────────────────────────────────

def student_arrangements_flow() -> None:
    print("\n═══ Access Arrangements ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = marking.access_arrangements_for(sid)
    if not names:
        print(f"\n  {sid} has no current exam-access arrangements.")
    else:
        print(f"\n  {sid}:")
        for n in names:
            print(f"    - {n}")
        percent = marking.extra_time_percent(sid)
        if percent:
            print(f"\n  Extra time: {percent:g}%")
        else:
            print("\n  No extra-time entitlement "
                  "(these arrangements don't change deadlines).")
    _pause()


def apply_arrangements_flow() -> None:
    print("\n═══ Apply Access Arrangements ═══")
    print("  Converts extra time into extra days on the deadline and")
    print("  records it as an ordinary extension, so the late sweep")
    print("  honours it automatically.")
    try:
        a = _pick_assignment()
        overwrite = _input(
            "Overwrite extensions granted by hand? (y/n)",
            default="n").lower() in ("y", "yes")
        by = _input("Applied by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not a.honour_access_arrangements:
        print("\n  This assignment has access arrangements switched off.")
        _pause()
        return
    result = marking.apply_access_arrangements(
        a.assignment_id, applied_by=by or None, overwrite=overwrite)
    print(f"\n  Eligible          : {result['eligible']}")
    print(f"  Extensions granted: {result['granted']}")
    print(f"  Already extended  : {result['skipped']}")
    _pause()


# ── Mark audit trail (item 17) ─────────────────────────────────────

def audit_flow() -> None:
    print("\n═══ Mark Audit Trail ═══")
    try:
        a = _pick_assignment()
        scope = _pick_from("Scope",
                            ["Whole assignment", "One submission"],
                            default="Whole assignment")
        submission_id = None
        if scope == "One submission":
            submission_id = _pick_submission(
                a.assignment_id).submission_id
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = marking.list_mark_audit(
        assignment_id=(a.assignment_id if submission_id is None else None),
        submission_id=submission_id, limit=200)
    if not rows:
        print("\n  (no mark changes recorded)")
        _pause()
        return
    print()
    print(f"  {'When':<20}  {'Sub':>5}  {'Field':<10}  "
          f"{'From':>8}  {'To':>8}  {'Source':<10}  By / reason")
    print("  " + "-" * 110)
    for r in rows:
        who = r.changed_by or "—"
        detail = f"{who}" + (f" — {r.reason}" if r.reason else "")
        print(f"  {r.changed_at:<20}  {r.submission_id:>5}  "
              f"{r.field:<10}  {(r.old_value or '—'):>8}  "
              f"{(r.new_value or '—'):>8}  {r.source:<10}  "
              f"{detail[:40]}")
    print(f"\n  {len(rows)} change(s), newest first.")
    _pause()


# ── Comment bank (item 18) ─────────────────────────────────────────

def list_comments_flow() -> None:
    print("\n═══ Comment Bank ═══")
    try:
        subject = _input("Subject (blank for all)")
        category = _input(f"Category ({'/'.join(COMMENT_CATEGORIES)})")
        query = _input("Text contains")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = marking.list_comments(subject_name=subject or None,
                                      category=category or None,
                                      query=query or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  (no comments)")
        _pause()
        return
    print()
    for c in rows:
        scope = c.subject_name or "all subjects"
        print(f"  #{c.comment_id:<4} [{c.category:<12}] "
              f"({scope}, used {c.use_count}×)")
        for line in c.body.splitlines():
            print(f"      {line}")
    print(f"\n  {len(rows)} comment(s).")
    _pause()


def add_comment_flow() -> None:
    print("\n═══ Add Bank Comment ═══")
    print("  Placeholders: {first_name} {full_name} {grade} {marks}")
    print("                {max_marks} {title} {subject_name}")
    try:
        subject = _input("Subject (blank = all subjects)")
        category = _pick_from("Category", list(COMMENT_CATEGORIES),
                               default=marking.DEFAULT_COMMENT_CATEGORY)
        code = _input("Short code (optional)")
        body = _multiline("Comment body")
        by = _input("Created by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = marking.add_comment({"subject_name": subject or None,
                                  "category": category, "code": code,
                                  "body": body, "created_by": by})
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added comment #{c.comment_id}")
    _pause()


def edit_comment_flow() -> None:
    print("\n═══ Edit Bank Comment ═══")
    try:
        cid = int(_input("Comment id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = marking.get_comment(cid)
    if existing is None:
        print(f"\n  ✗ No comment #{cid}")
        _pause()
        return
    try:
        subject = _input("Subject", default=existing.subject_name or "")
        category = _pick_from("Category", list(COMMENT_CATEGORIES),
                               default=existing.category)
        code = _input("Short code", default=existing.code or "")
        body = _multiline("Comment body", default=existing.body)
        active = _input("Active? (y/n)",
                         default="y" if existing.is_active else "n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        marking.update_comment(cid, {
            "subject_name": subject or None, "category": category,
            "code": code, "body": body,
            "is_active": active.lower() in ("y", "yes")})
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated comment #{cid}")
    _pause()


def delete_comment_flow() -> None:
    print("\n═══ Delete Bank Comment ═══")
    try:
        cid = int(_input("Comment id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if _input(f"Delete comment #{cid}? Type 'yes'",
               default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if marking.delete_comment(cid):
        print(f"\n  ✓ Deleted comment #{cid}")
    else:
        print(f"\n  ✗ No comment #{cid}")
    _pause()


def apply_comment_flow() -> None:
    print("\n═══ Add Bank Comment to Feedback ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = marking.list_comments(subject_name=a.subject_name)
    if not rows:
        print("\n  The bank has no comments for this subject.")
        _pause()
        return
    print("\n  Bank:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>3}) #{c.comment_id}  {c.label}")
    try:
        raw = _input(f"Pick #1..{len(rows)}", allow_empty=False)
        chosen = rows[int(raw) - 1]
    except (ValueError, IndexError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    text = marking.use_comment(chosen.comment_id,
                                submission_id=sub.submission_id)
    print(f"\n  {text}")
    if _input("Append to this submission's feedback? (y/n)",
               default="y").lower() not in ("y", "yes"):
        _pause()
        return
    current = data.get_submission(sub.submission_id)
    existing = (current.feedback or "") if current else ""
    data.update_submission(sub.submission_id, {
        "feedback": (existing + "\n\n" + text).strip()})
    print("  ✓ Appended.")
    _pause()


# ── Bulk marking (item 19) ─────────────────────────────────────────

def bulk_mark_flow() -> None:
    print("\n═══ Bulk Marking ═══")
    try:
        a = _pick_assignment()
        marked_by = _input("Marked by", default=a.teacher or "")
        role = _pick_role()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    grid = marking.marking_grid(a.assignment_id, role=role)
    if not grid:
        print("\n  No students on this assignment.")
        _pause()
        return
    print(f"\n  {len(grid)} student(s). Blank keeps the current mark; "
          f"'cancel' aborts.")
    rows: list[dict[str, Any]] = []
    try:
        for g in grid:
            s = g.submission
            current = (f"{s.raw_marks:g}"
                       if s.raw_marks is not None else "")
            flags = []
            if g.penalty.days_late:
                flags.append(g.penalty.message)
            if g.access_arrangements:
                flags.append("; ".join(g.access_arrangements))
            suffix = f"   [{' | '.join(flags)}]" if flags else ""
            raw = _input(f"{s.student_id} {g.student_name[:22]:<22}"
                          f"{suffix}\n    Marks (0-{a.max_marks or '?'})",
                          default=current)
            if not raw:
                continue
            rows.append({"submission_id": s.submission_id,
                          "marks": raw})
    except _UserAbort:
        print("\n  Cancelled — nothing has been written.")
        return

    if not rows:
        print("\n  Nothing entered.")
        _pause()
        return
    result = marking.bulk_mark(a.assignment_id, rows,
                               marked_by=marked_by or None, role=role)
    print(f"\n  Applied {result.applied}, failed {result.failed}.")
    for o in result.outcomes:
        flag = "✓" if o.ok else "✗"
        print(f"    {flag} {o.student_id:<10}  {o.message}")
    _pause()


def marking_grid_flow() -> None:
    print("\n═══ Marking Grid ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    grid = marking.marking_grid(a.assignment_id)
    if not grid:
        print("\n  No students on this assignment.")
        _pause()
        return
    criteria = marking.list_criteria(a.assignment_id)
    header = (f"  {'Sub':>5}  {'Student':<10}  {'Name':<18}  "
              f"{'Status':<11}  {'Raw':>5}  {'Pen':>5}  "
              f"{'Final':>5}  {'Gr':<3}")
    for c in criteria:
        header += f"  {(c.code or c.title)[:6]:>6}"
    print()
    print(header)
    print("  " + "-" * (len(header) + 10))
    for g in grid:
        s = g.submission
        line = (f"  {s.submission_id:>5}  {s.student_id:<10}  "
                f"{g.student_name[:18]:<18}  {s.status:<11}  "
                f"{(f'{s.raw_marks:g}' if s.raw_marks is not None else '—'):>5}  "
                f"{(f'{s.penalty_percent:g}' if s.penalty_percent else '—'):>5}  "
                f"{(f'{s.marks:g}' if s.marks is not None else '—'):>5}  "
                f"{(s.grade or '—'):<3}")
        for c in criteria:
            value = g.criterion_marks.get(c.criterion_id)
            line += f"  {(f'{value:g}' if value is not None else '—'):>6}"
        print(line)
        if g.moderation and g.moderation.needs_moderation:
            print(f"        ⚠ {g.moderation.message}")
        if g.access_arrangements:
            print(f"        ◆ {'; '.join(g.access_arrangements)}")
    print(f"\n  {len(grid)} student(s). "
          f"{marking.rubric_total(a.assignment_id).message}")
    _pause()


# ── Submenu ────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Marking grid",             marking_grid_flow),
    ("Bulk marking",             bulk_mark_flow),
    ("─" * 6,                    lambda: None),
    ("View rubric",              list_criteria_flow),
    ("Add criterion",            add_criterion_flow),
    ("Edit criterion",           edit_criterion_flow),
    ("Delete criterion",         delete_criterion_flow),
    ("Reorder rubric",           reorder_criteria_flow),
    ("─" * 6,                    lambda: None),
    ("Mark by criterion",        mark_by_criterion_flow),
    ("View criterion marks",     view_criterion_marks_flow),
    ("─" * 6,                    lambda: None),
    ("Record a mark",            record_mark_flow),
    ("View marks",               view_marks_flow),
    ("Moderation queue",         moderation_queue_flow),
    ("Resolve moderation",       resolve_moderation_flow),
    ("─" * 6,                    lambda: None),
    ("Grade boundaries",         boundaries_flow),
    ("Clear grade boundaries",   clear_boundaries_flow),
    ("─" * 6,                    lambda: None),
    ("Late penalties",           penalties_flow),
    ("Waive late penalty",       waive_penalty_flow),
    ("Restore late penalty",     restore_penalty_flow),
    ("─" * 6,                    lambda: None),
    ("Student access arrangements", student_arrangements_flow),
    ("Apply access arrangements",   apply_arrangements_flow),
    ("─" * 6,                    lambda: None),
    ("Auto-select sample",       auto_sample_flow),
    ("Flag sample",              flag_sample_flow),
    ("Remove from sample",       unflag_sample_flow),
    ("View sample",              list_samples_flow),
    ("─" * 6,                    lambda: None),
    ("Comment bank",             list_comments_flow),
    ("Add bank comment",         add_comment_flow),
    ("Edit bank comment",        edit_comment_flow),
    ("Delete bank comment",      delete_comment_flow),
    ("Apply bank comment",       apply_comment_flow),
    ("─" * 6,                    lambda: None),
    ("Mark audit trail",         audit_flow),
]


def run() -> None:
    marking.init_db()
    while True:
        print("\n── Marking ──")
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
            logger.exception("Marking CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Marking":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Marking CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
