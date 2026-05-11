"""CLI flows for the Sixth Form Gradebook.

Submenu: class summary / per-student detail / boundaries (set / clear /
view) / letter-grade lookup. No grade entry happens here — that's the
homework module's job.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.class_groups import class_groups
from education_system.sixthform_system.modules.domain.courses import courses
from education_system.sixthform_system.modules.domain.gradebook import gradebook
from education_system.sixthform_system.modules.domain.homework import homework
from education_system.sixthform_system.modules.domain.students import students as cg_data
from education_system.sixthform_system.modules.domain.courses import courses as course_data
from education_system.sixthform_system.modules.domain.gradebook import gradebook as data
from education_system.sixthform_system.modules.domain.homework import homework as hw_data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.gradebook.gradebook import (
    DEFAULT_BOUNDARIES_PCT,
    GradedSubmission,
    LETTER_GRADES,
    StudentGradebookSummary,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.homework.homework import ASSIGNMENT_TYPES

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_group() -> int:
    groups = cg_data.list_groups()
    if not groups:
        print("    No class groups exist. Create one first.")
        raise _UserAbort
    courses = {c.course_id: c for c in course_data.list_courses()}
    print("\n  Class groups:")
    for i, g in enumerate(groups, 1):
        c = courses.get(g.course_id)
        code = c.course_code if c else f"#{g.course_id}"
        print(f"    {i:>3}) #{g.group_id:<3}  {code:<14}  {g.group_name}")
    while True:
        raw = _input(f"  Pick #1..{len(groups)} (or group ID)", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(groups):
                return groups[n - 1].group_id
            target = next((g for g in groups if g.group_id == n), None)
            if target:
                return target.group_id
            print(f"    Out of range (1..{len(groups)}).")


def _pick_assignment() -> int:
    assns = hw_data.list_assignments()
    if not assns:
        print("    No assignments exist.")
        raise _UserAbort
    print("\n  Assignments:")
    for i, a in enumerate(assns, 1):
        print(f"    {i:>3}) #{a.assignment_id:<3}  {a.title[:32]:<32}  "
              f"({a.type}, max {a.max_marks if a.max_marks is not None else '—'})")
    while True:
        raw = _input(f"  Pick #1..{len(assns)} (or assignment ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(assns):
                return assns[n - 1].assignment_id
            target = next((a for a in assns if a.assignment_id == n), None)
            if target:
                return target.assignment_id
            print(f"    Out of range (1..{len(assns)}).")


# ── Class summary ──────────────────────────────────────────────────

def class_summary() -> None:
    print("\n═══ Class Gradebook Summary ═══")
    try:
        gid = _pick_group()
        a_type = _input(f"Type (optional: {'/'.join(ASSIGNMENT_TYPES)})") or None
        if a_type and a_type not in ASSIGNMENT_TYPES:
            print("  ✗ Unknown type.")
            _pause()
            return
        due_from = _input("Due from (YYYY-MM-DD, optional)") or None
        due_to   = _input("Due to (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        _assns, sts, _cells = data.group_matrix(
            gid, type=a_type, due_from=due_from, due_to=due_to)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("group_matrix failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return

    print()
    print(f"  {'Student':<10}  {'Name':<24}  {'Total':>5}  {'Marked':>6}  "
          f"{'Avg %':>6}  {'Best':>4}  {'Worst':>5}")
    print("  " + "-" * 74)
    for student in sts:
        summ = data.student_summary(student.student_id, group_id=gid)
        avg = f"{summ.avg_pct}%" if summ.avg_pct is not None else "—"
        print(f"  {student.student_id:<10}  {student.full_name[:24]:<24}  "
              f"{summ.total_assignments:>5}  {summ.marked:>6}  "
              f"{avg:>6}  {(summ.best_letter or '—'):>4}  "
              f"{(summ.worst_letter or '—'):>5}")
    _pause()


# ── Per-student detail ────────────────────────────────────────────

def student_detail() -> None:
    print("\n═══ Per-Student Gradebook ═══")
    try:
        sid = _input("Student ID", allow_empty=False)
        scope = _input("Scope to one group? (y/n)", default="n").lower()
        gid = None
        if scope in ("y", "yes"):
            gid = _pick_group()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    if student is None:
        print(f"  ✗ No student with id {sid}")
        _pause()
        return

    try:
        rows = data.graded_submissions_for_student(sid)
        if gid is not None:
            ids = {a.assignment_id for a in hw_data.list_assignments(group_id=gid)}
            rows = [r for r in rows if r.assignment_id in ids]
        summ = data.student_summary(sid, group_id=gid)
    except Exception as e:
        logger.exception("student detail failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return

    print()
    print(f"  {student.student_id}  {student.full_name}")
    avg = f"{summ.avg_pct}%" if summ.avg_pct is not None else "—"
    extras = (f"  ·  Best: {summ.best_letter}  ·  Worst: {summ.worst_letter}"
              if summ.best_letter else "")
    print(f"  Marked: {summ.marked}/{summ.total_assignments}  ·  "
          f"Avg: {avg}{extras}\n")
    if not rows:
        print("  (no graded submissions)")
        _pause()
        return

    print(f"  {'#':>4}  {'Title':<28}  {'Type':<10}  {'Due':<10}  "
          f"{'Marks':<10}  {'%':>5}  {'Letter':<6}")
    print("  " + "-" * 80)
    for r in rows:
        marks = (f"{r.marks}/{r.max_marks}"
                 if r.marks is not None and r.max_marks else
                 (str(r.marks) if r.marks is not None else "—"))
        pct = f"{r.percentage}%" if r.percentage is not None else "—"
        print(f"  {r.assignment_id:>4}  {r.title[:28]:<28}  {r.type[:10]:<10}  "
              f"{r.due_date:<10}  {marks:<10}  {pct:>5}  "
              f"{(r.letter or '—'):<6}")
    _pause()


# ── Boundaries ────────────────────────────────────────────────────

def view_boundaries() -> None:
    print("\n═══ View Boundaries ═══")
    try:
        aid = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    a = hw_data.get_assignment(aid)
    print(f"\n  Assignment #{a.assignment_id}  {a.title}")
    print(f"  Max marks: {a.max_marks if a.max_marks is not None else '—'}")
    b = data.get_boundaries(aid)
    if b is None:
        print("  Using percentage defaults:")
        for letter, pct in DEFAULT_BOUNDARIES_PCT:
            print(f"    {letter:<2}  ≥  {pct}%")
        print("    U   <  40.0%")
    else:
        print("  Per-assignment overrides (raw marks):")
        for letter, value in b.as_dict().items():
            print(f"    {letter:<2}  ≥  "
                  f"{value if value is not None else '(default)'}")
    _pause()


def set_boundaries_flow() -> None:
    print("\n═══ Set Boundaries ═══")
    print("  (blank = use default; type 'cancel' to abort)")
    try:
        aid = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    a = hw_data.get_assignment(aid)
    print(f"\n  Assignment #{a.assignment_id}  {a.title}")
    print(f"  Max marks: {a.max_marks if a.max_marks is not None else '—'}")
    existing = data.get_boundaries(aid)
    payload: dict[str, Any] = {}
    try:
        for letter in ("A*", "A", "B", "C", "D", "E"):
            cur = (str(existing.as_dict().get(letter))
                   if existing and existing.as_dict().get(letter) is not None
                   else "")
            payload[letter] = _input(f"{letter} threshold (raw marks)",
                                     default=cur)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        gb = data.set_boundaries(aid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("set_boundaries crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print("\n  ✓ Saved boundaries:")
    for letter, value in gb.as_dict().items():
        print(f"    {letter}: {value if value is not None else '(default)'}")
    _pause()


def clear_boundaries_flow() -> None:
    print("\n═══ Clear Boundaries ═══")
    try:
        aid = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    confirm = _input("Revert to percentage defaults? Type 'yes'",
                     default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.clear_boundaries(aid):
        print(f"\n  ✓ Cleared overrides for assignment #{aid}")
    else:
        print(f"\n  (no overrides existed for assignment #{aid})")
    _pause()


# ── Letter grade lookup ───────────────────────────────────────────

def letter_lookup() -> None:
    print("\n═══ Letter Grade Lookup ═══")
    try:
        raw = _input("Percentage (0-100)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        pct = float(raw)
    except ValueError:
        print("  ✗ Must be a number.")
        _pause()
        return
    if pct < 0 or pct > 100:
        print("  ✗ Percentage must be between 0 and 100.")
        _pause()
        return
    print(f"\n  {pct}% → {data.pct_to_letter(pct)}")
    _pause()


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Class Summary",        class_summary),
    ("Per-Student Detail",   student_detail),
    ("View Boundaries",      view_boundaries),
    ("Set Boundaries",       set_boundaries_flow),
    ("Clear Boundaries",     clear_boundaries_flow),
    ("Letter Grade Lookup",  letter_lookup),
]


def run() -> None:
    while True:
        print("\n── Gradebook ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Gradebook CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Gradebook":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Gradebook CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
