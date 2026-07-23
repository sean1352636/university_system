"""CLI flows for Sixth Form Homework & Coursework.

Submenu: list / filter / new / view / edit / delete + mark sheet bulk
flow + per-student summary.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups
from education_system.post_16.sixthform_system.modules.domain.academics.homework import homework
from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups as cg_data
from education_system.post_16.sixthform_system.modules.domain.academics.courses import courses as course_data
from education_system.post_16.sixthform_system.modules.domain.academics.homework import homework as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.academics.homework.homework import (
    ASSIGNMENT_TYPES,
    Assignment,
    DEFAULT_ASSIGNMENT_TYPE,
    DEFAULT_SUBMISSION_STATUS,
    SUBMISSION_STATUSES,
    StudentSummary,
    ValidationError,
)

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


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _pick_group() -> int:
    groups = cg_data.list_groups()
    if not groups:
        print("    No class groups exist. Create one first.")
        raise _UserAbort
    courses = {c.course_id: c for c in course_data.list_courses()}
    print("\n  Class groups:")
    for i, g in enumerate(groups, 1):
        course = courses.get(g.course_id)
        code = course.course_code if course else f"#{g.course_id}"
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
    rows = data.list_assignments()
    if not rows:
        print("    No assignments exist. Create one first.")
        raise _UserAbort
    print("\n  Assignments:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.assignment_id:<3}  {a.title[:32]:<32}  "
              f"({a.type}, due {a.due_date}, group #{a.group_id})")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or assignment ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].assignment_id
            target = next((a for a in rows if a.assignment_id == n), None)
            if target:
                return target.assignment_id
            print(f"    Out of range (1..{len(rows)}).")


# ── Assignment form ────────────────────────────────────────────────

def _today() -> str:
    return _date.today().isoformat()


def _collect_assignment(existing: Assignment | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}
    if is_edit:
        print(f"\n  Editing assignment #{existing.assignment_id} "
              f"(group #{existing.group_id})")
        payload["group_id"] = existing.group_id
    else:
        print("\n  ── Class group ──")
        payload["group_id"] = _pick_group()

    print("\n  ── Assignment details ──")
    payload["title"] = _input(
        "Title", default=(existing.title if is_edit else ""), allow_empty=False)
    payload["type"] = _pick_from(
        "Type", list(ASSIGNMENT_TYPES),
        default=(existing.type if is_edit else DEFAULT_ASSIGNMENT_TYPE))
    payload["set_date"] = _input(
        "Set date (YYYY-MM-DD)",
        default=(existing.set_date if is_edit else _today()),
        allow_empty=False)
    payload["due_date"] = _input(
        "Due date (YYYY-MM-DD)",
        default=(existing.due_date if is_edit else _today()),
        allow_empty=False)
    payload["max_marks"] = _input(
        "Max marks (blank = no cap)",
        default=(str(existing.max_marks)
                 if (is_edit and existing.max_marks is not None) else "100"))
    payload["description"] = _input(
        "Description (optional)",
        default=(existing.description or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return payload


# ── CRUD entry points ──────────────────────────────────────────────

def _print_assignments(rows: list[Assignment]) -> None:
    if not rows:
        print("\n  (no assignments)")
        return
    print()
    print(f"  {'#':>4}  {'Title':<32}  {'Type':<12}  "
          f"{'Group':>5}  {'Set':<10}  {'Due':<10}  Max")
    print("  " + "-" * 86)
    for a in rows:
        print(
            f"  {a.assignment_id:>4}  {a.title[:32]:<32}  {a.type:<12}  "
            f"{a.group_id:>5}  {a.set_date:<10}  {a.due_date:<10}  "
            f"{a.max_marks if a.max_marks is not None else '—'}"
        )
    print(f"\n  {len(rows)} assignment(s).")


def list_all() -> None:
    print("\n═══ Assignments ═══")
    try:
        rows = data.list_assignments()
    except Exception as e:
        logger.exception("CLI list_assignments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_assignments(rows)
    _row_action_loop(rows)


def filter_assignments() -> None:
    print("\n═══ Filter Assignments ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        gid_raw = _input("Group ID")
        a_type = _input(f"Type ({'/'.join(ASSIGNMENT_TYPES)})") or None
        if a_type and a_type not in ASSIGNMENT_TYPES:
            print("  ✗ Unknown type.")
            _pause()
            return
        due_from = _input("Due from (YYYY-MM-DD)") or None
        due_to   = _input("Due to (YYYY-MM-DD)")   or None
        search   = _input("Search (title / description)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    kwargs: dict[str, Any] = {
        "type": a_type, "due_from": due_from, "due_to": due_to,
        "search": search,
    }
    if gid_raw:
        try:
            kwargs["group_id"] = int(gid_raw)
        except ValueError:
            print("  ✗ Group ID must be a number.")
            _pause()
            return

    try:
        rows = data.list_assignments(**kwargs)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI filter_assignments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_assignments(rows)
    _row_action_loop(rows)


def new_assignment() -> None:
    print("\n═══ New Assignment ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_assignment(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_assignment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_assignment failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print()
    print(f"  ✓ Created assignment #{a.assignment_id}")
    print(f"      Title    : {a.title}")
    print(f"      Type     : {a.type}")
    print(f"      Group    : #{a.group_id}")
    print(f"      Set/Due  : {a.set_date} → {a.due_date}")
    print(f"      Max      : {a.max_marks if a.max_marks is not None else '—'}")
    _pause()


def view_assignment(assignment_id: int | None = None) -> None:
    print("\n═══ View Assignment ═══")
    try:
        aid = assignment_id if assignment_id is not None else int(
            _input("Assignment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Assignment ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    a = data.get_assignment(aid)
    if a is None:
        print(f"  ✗ No assignment #{aid}")
        _pause()
        return
    g = cg_data.get_group(a.group_id)
    course = course_data.get_course(g.course_id) if g else None
    print()
    print(f"    Assignment ID : #{a.assignment_id}")
    print(f"    Title         : {a.title}")
    print(f"    Type          : {a.type}")
    print(f"    Class group   : "
          f"#{a.group_id} {(g.group_name if g else '(deleted)')} "
          f"({course.course_code if course else '—'})")
    print(f"    Set date      : {a.set_date}")
    print(f"    Due date      : {a.due_date}")
    print(f"    Max marks     : {a.max_marks if a.max_marks is not None else '—'}")
    if a.description:
        print(f"    Description   : {a.description}")
    if a.notes:
        print(f"    Notes         : {a.notes}")

    # Quick submission summary
    subs = data.list_submissions(assignment_id=aid)
    print()
    print(f"    Submissions: {len(subs)} record(s)")
    by_status: dict[str, int] = {}
    for s in subs:
        by_status[s.status] = by_status.get(s.status, 0) + 1
    for st in SUBMISSION_STATUSES:
        print(f"      {st:<14}: {by_status.get(st, 0)}")
    _pause()


def edit_assignment(assignment_id: int | None = None) -> None:
    print("\n═══ Edit Assignment ═══")
    try:
        aid = assignment_id if assignment_id is not None else int(
            _input("Assignment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Assignment ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_assignment(aid)
    if existing is None:
        print(f"  ✗ No assignment #{aid}")
        _pause()
        return
    try:
        payload = _collect_assignment(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.update_assignment(aid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_assignment(%d) failed", aid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated assignment #{a.assignment_id}")
    _pause()


def delete_assignment_flow(assignment_id: int | None = None) -> None:
    print("\n═══ Delete Assignment ═══")
    try:
        aid = assignment_id if assignment_id is not None else int(
            _input("Assignment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Assignment ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_assignment(aid)
    if existing is None:
        print(f"  ✗ No assignment #{aid}")
        _pause()
        return
    n = len(data.list_submissions(assignment_id=aid))
    extra = f" ({n} submission row(s) will be removed)" if n else ""
    confirm = _input(
        f"Delete '{existing.title}'?{extra} Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_assignment(aid):
            print(f"\n  ✓ Deleted assignment #{aid}")
    except Exception as e:
        logger.exception("CLI delete_assignment crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Mark sheet ─────────────────────────────────────────────────────

def mark_sheet() -> None:
    print("\n═══ Mark Sheet ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        aid = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    a = data.get_assignment(aid)
    try:
        view = data.submission_view(aid)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("submission_view failed")
        print(f"  ✗ Unexpected error: {e}")
        _pause()
        return
    if not view:
        print("  ✗ This assignment's class group has no members.")
        _pause()
        return

    print(f"\n  {a.title}  (max: {a.max_marks if a.max_marks is not None else '—'})")
    print("  Statuses: 1=Not Submitted  2=Submitted  3=Late  4=Excused  S=Skip")

    payload: dict[str, dict[str, Any]] = {}
    for v in view:
        existing = ""
        if v.submission:
            existing = (f"  [current: {v.submission.status}"
                        + (f", marks={v.submission.marks}"
                           if v.submission.marks is not None else "")
                        + "]")
        print(f"\n  {v.student_id}  {v.full_name}{existing}")
        default_status = (v.submission.status if v.submission
                          else DEFAULT_SUBMISSION_STATUS)
        try:
            raw = _input("  Status (1-4 / S)", default=default_status)
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if raw.lower() == "s":
            continue
        mapping = {"1": "Not Submitted", "2": "Submitted",
                   "3": "Late", "4": "Excused"}
        status = mapping.get(raw, raw)

        submitted_at = ""
        marks = ""
        feedback = ""
        if status in ("Submitted", "Late"):
            try:
                submitted_at = _input(
                    "    Submitted at (YYYY-MM-DD [HH:MM])",
                    default=(v.submission.submitted_at
                             if v.submission and v.submission.submitted_at
                             else _today()),
                )
            except _UserAbort:
                print("\n  Cancelled.")
                return
        if status != "Not Submitted":
            try:
                marks = _input(
                    "    Marks (optional)",
                    default=(str(v.submission.marks)
                             if v.submission and v.submission.marks is not None
                             else ""),
                )
                feedback = _input(
                    "    Feedback (optional)",
                    default=(v.submission.feedback if v.submission and v.submission.feedback
                             else ""),
                )
            except _UserAbort:
                print("\n  Cancelled.")
                return
        payload[v.student_id] = {
            "status": status, "submitted_at": submitted_at,
            "marks": marks, "feedback": feedback,
        }

    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = data.save_submissions(aid, payload)
        print(f"\n  ✓ Saved {n} submission(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_submissions crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Per-student summary ────────────────────────────────────────────

def student_summary() -> None:
    print("\n═══ Per-Student Summary ═══")
    try:
        gid = _pick_group()
        a_type = _input(f"Type (optional: {'/'.join(ASSIGNMENT_TYPES)})") or None
        if a_type and a_type not in ASSIGNMENT_TYPES:
            print("  ✗ Unknown type.")
            _pause()
            return
        due_from = _input("Due from (YYYY-MM-DD, optional)") or None
        due_to = _input("Due to (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        per = data.per_student_summary_for_group(
            gid, type=a_type, due_from=due_from, due_to=due_to)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return

    students_index = {s.student_id: s for s in student_data.list_students()}
    print()
    print(f"  {'Student':<10}  {'Name':<24}  {'Total':>5}  {'Subm.':>5}  "
          f"{'Late':>4}  {'Miss':>4}  {'Exc.':>4}  {'Rate':>6}  {'Avg':>6}")
    print("  " + "-" * 80)
    for sid, s in sorted(per.items()):
        student = students_index.get(sid)
        name = (student.full_name if student else "(deleted)")[:24]
        rate = f"{s.submission_rate}%" if s.submission_rate is not None else "—"
        avg  = f"{s.avg_pct}%" if s.avg_pct is not None else "—"
        print(f"  {sid:<10}  {name:<24}  {s.total:>5}  {s.submitted:>5}  "
              f"{s.late:>4}  {s.not_submitted:>4}  {s.excused:>4}  "
              f"{rate:>6}  {avg:>6}")
    _pause()


# ── Row-action loop ────────────────────────────────────────────────

def _row_action_loop(rows: list[Assignment]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   M) Mark sheet   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "m", "d"):
            print("    Pick V, E, M, D, or Enter.")
            continue
        try:
            raw = _input("Assignment ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            aid = int(raw)
        except ValueError:
            print("    Assignment ID must be a whole number.")
            continue
        if choice == "v":
            view_assignment(aid)
        elif choice == "e":
            edit_assignment(aid)
        elif choice == "m":
            _mark_sheet_for(aid)
        elif choice == "d":
            delete_assignment_flow(aid)
        return


def _mark_sheet_for(aid: int) -> None:
    """Variant of mark_sheet that skips the assignment picker."""
    a = data.get_assignment(aid)
    if a is None:
        print(f"  ✗ No assignment #{aid}")
        _pause()
        return
    try:
        view = data.submission_view(aid)
    except Exception as e:
        logger.exception("submission_view failed")
        print(f"  ✗ {e}")
        _pause()
        return
    if not view:
        print("  ✗ This assignment's class group has no members.")
        _pause()
        return

    print(f"\n  {a.title}  (max: {a.max_marks if a.max_marks is not None else '—'})")
    print("  Statuses: 1=Not Submitted  2=Submitted  3=Late  4=Excused  S=Skip")
    payload: dict[str, dict[str, Any]] = {}
    for v in view:
        existing = (f"  [current: {v.submission.status}]"
                    if v.submission else "")
        print(f"\n  {v.student_id}  {v.full_name}{existing}")
        default_status = (v.submission.status if v.submission
                          else DEFAULT_SUBMISSION_STATUS)
        try:
            raw = _input("  Status (1-4 / S)", default=default_status)
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if raw.lower() == "s":
            continue
        mapping = {"1": "Not Submitted", "2": "Submitted",
                   "3": "Late", "4": "Excused"}
        status = mapping.get(raw, raw)
        submitted_at = ""
        marks = ""
        feedback = ""
        if status in ("Submitted", "Late"):
            try:
                submitted_at = _input(
                    "    Submitted at",
                    default=(v.submission.submitted_at
                             if v.submission and v.submission.submitted_at
                             else _today()),
                )
            except _UserAbort:
                return
        if status != "Not Submitted":
            try:
                marks = _input(
                    "    Marks",
                    default=(str(v.submission.marks)
                             if v.submission and v.submission.marks is not None
                             else ""))
                feedback = _input(
                    "    Feedback",
                    default=(v.submission.feedback if v.submission and v.submission.feedback
                             else ""))
            except _UserAbort:
                return
        payload[v.student_id] = {
            "status": status, "submitted_at": submitted_at,
            "marks": marks, "feedback": feedback,
        }
    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = data.save_submissions(aid, payload)
        print(f"\n  ✓ Saved {n} submission(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_submissions crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Submenu dispatcher ─────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Assignments",       list_all),
    ("Filter Assignments",     filter_assignments),
    ("New Assignment",         new_assignment),
    ("Mark Sheet",             mark_sheet),
    ("Per-Student Summary",    student_summary),
    ("View Assignment",        view_assignment),
    ("Edit Assignment",        edit_assignment),
    ("Delete Assignment",      delete_assignment_flow),
]


def run() -> None:
    while True:
        print("\n── Homework & Coursework ──")
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
            logger.exception("Homework CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Homework & Coursework":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Homework CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
