"""CLI flows for Sixth Form Assignments."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.academics.assignments import (
    assignments as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.academics.assignments.assignments import (
    ASSIGNMENT_STATUSES,
    ASSIGNMENT_TYPES,
    Assignment,
    DEFAULT_ASSIGNMENT_STATUS,
    DEFAULT_ASSIGNMENT_TYPE,
    DEFAULT_SUBMISSION_STATUS,
    DONE_SUBMISSION_STATUSES,
    SUBMISSION_STATUSES,
    Submission,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
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


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.' on its own line; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_subject() -> str:
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject", allow_empty=False)
    return _pick_from("Subject", names)


def _pick_assignment() -> Assignment:
    rows = data.list_assignments()
    if not rows:
        print("    No assignments yet.")
        raise _UserAbort
    print("\n  Assignments:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.assignment_id}  "
              f"{(a.due_date or '—'):<10}  "
              f"{a.subject_name[:14]:<14}  "
              f"{a.title[:32]:<32}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows
                            if a.assignment_id == n), None)
            if match:
                return match
        print("    No matching assignment.")


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_submission(assignment_id: int) -> Submission:
    subs = data.list_submissions(assignment_id=assignment_id)
    if not subs:
        print("    No submissions on this assignment.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Submissions:")
    for i, sub in enumerate(subs, 1):
        marks = (f"{sub.marks}" if sub.marks is not None else "—")
        print(f"    {i:>3}) #{sub.submission_id}  "
              f"{sub.student_id}  "
              f"{names.get(sub.student_id, '?')[:20]:<20}  "
              f"[{sub.status}]  marks={marks}")
    while True:
        raw = _input(f"  Pick #1..{len(subs)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(subs):
                return subs[n - 1]
            match = next((s for s in subs
                            if s.submission_id == n), None)
            if match:
                return match
        print("    No matching submission.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_assignments(rows: list[Assignment]) -> None:
    if not rows:
        print("\n  (no assignments)")
        return
    print()
    print(f"  {'#':>4}  {'Due':<10}  {'Subject':<16}  "
          f"{'Type':<14}  {'Teacher':<14}  "
          f"{'Status':<10}  Title")
    print("  " + "-" * 110)
    for a in rows:
        print(f"  {a.assignment_id:>4}  "
              f"{(a.due_date or '—'):<10}  "
              f"{a.subject_name[:16]:<16}  "
              f"{a.assignment_type[:14]:<14}  "
              f"{(a.teacher or '—')[:14]:<14}  "
              f"{a.status:<10}  {a.title[:40]}")
    print(f"\n  {len(rows)} assignment(s).")


def _print_assignment_full(a: Assignment) -> None:
    detail = data.get_assignment_detail(a.assignment_id)
    print()
    print(f"    #{a.assignment_id}  {a.title}")
    print(f"    Subject       : {a.subject_name}")
    print(f"    Type          : {a.assignment_type}")
    print(f"    Year / Course : "
          f"{a.year_group or '—'}  ·  course #{a.course_id or '—'}  "
          f"·  group #{a.class_group_id or '—'}")
    print(f"    Teacher       : {a.teacher or '—'}")
    print(f"    Set / Due     : "
          f"{a.set_date or '—'}  →  {a.due_date or '—'}")
    print(f"    Max marks     : {a.max_marks or '—'}")
    print(f"    Weight %      : {a.weight_percent or '—'}")
    print(f"    Status        : {a.status}"
          + ("  (overdue)" if a.is_overdue else ""))
    print(f"    Submission    : {a.submission_method or '—'}")
    for label, val in (
            ("Brief",      a.brief),
            ("Rubric",     a.rubric),
            ("Resources",  a.resources),
            ("Notes",      a.notes),
    ):
        if val:
            print()
            print(f"    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    if detail and detail.submissions:
        print()
        print(f"    Submissions ({detail.submitted_count}"
              f"/{detail.total_submissions}, "
              f"avg={detail.average_mark or '—'}):")
        names = {s.student_id: s.full_name
                  for s in student_data.list_students()}
        for sub in detail.submissions:
            marks = (f"{sub.marks}/{a.max_marks or '?'}"
                     if sub.marks is not None else "—")
            print(f"      #{sub.submission_id}  "
                  f"{sub.student_id}  "
                  f"{names.get(sub.student_id, '?')[:18]:<18}  "
                  f"[{sub.status}]  marks={marks}")


# ── Assignment flows ───────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Assignments ═══")
    _print_assignments(data.list_assignments())
    _pause()


def list_open() -> None:
    print("\n═══ Open Assignments ═══")
    _print_assignments(data.list_assignments(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Assignments ═══")
    _print_assignments(data.list_assignments(overdue_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Assignments ═══")
    try:
        subj = _input("Subject (exact)") or None
        teacher = _input("Teacher contains") or None
        status = _input(f"Status ({'/'.join(ASSIGNMENT_STATUSES)})") or None
        atype = _input(f"Type ({'/'.join(ASSIGNMENT_TYPES)})") or None
        year = _input(f"Year ({'/'.join(YEAR_GROUPS)})") or None
        title = _input("Title contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_assignments(
            subject_name=subj, teacher_like=teacher,
            status=status, assignment_type=atype,
            year_group=year, title_like=title,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_assignments(rows)
    _pause()


def view_assignment_flow() -> None:
    print("\n═══ View Assignment ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_assignment_full(a)
    _pause()


def _collect_form(existing: Assignment | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    if is_edit:
        payload["subject_name"] = _input(
            "Subject", default=existing.subject_name,
            allow_empty=False)
    else:
        payload["subject_name"] = _pick_subject()
    payload["assignment_type"] = _pick_from(
        "Type", list(ASSIGNMENT_TYPES),
        default=(existing.assignment_type if is_edit
                  else DEFAULT_ASSIGNMENT_TYPE))
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["teacher"] = _input(
        "Teacher",
        default=(existing.teacher or "") if is_edit else "")
    payload["set_date"] = _input(
        "Set date (YYYY-MM-DD)",
        default=(existing.set_date or "") if is_edit
                  else _date.today().isoformat())
    payload["due_date"] = _input(
        "Due date (YYYY-MM-DD)",
        default=(existing.due_date or "") if is_edit else "")
    payload["max_marks"] = _input(
        "Max marks",
        default=(str(existing.max_marks)
                  if is_edit and existing.max_marks is not None
                  else ""))
    payload["weight_percent"] = _input(
        "Weight %",
        default=(str(existing.weight_percent)
                  if is_edit and existing.weight_percent is not None
                  else ""))
    payload["submission_method"] = _input(
        "Submission method",
        default=(existing.submission_method or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(ASSIGNMENT_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ASSIGNMENT_STATUS))
    try:
        payload["brief"] = _multiline(
            "Brief",
            default=(existing.brief or "") if is_edit else "")
        payload["rubric"] = _multiline(
            "Rubric",
            default=(existing.rubric or "") if is_edit else "")
        payload["resources"] = _multiline(
            "Resources",
            default=(existing.resources or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_assignment() -> None:
    print("\n═══ New Assignment ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_assignment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created assignment #{a.assignment_id} {a.title!r}")
    _pause()


def edit_assignment() -> None:
    print("\n═══ Edit Assignment ═══")
    try:
        a = _pick_assignment()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_assignment(a.assignment_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.assignment_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Assignment Status ═══")
    try:
        a = _pick_assignment()
        new_status = _pick_from(
            "New status", list(ASSIGNMENT_STATUSES),
            default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_assignment_status(a.assignment_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.assignment_id} → {new_status}")
    _pause()


def delete_assignment_flow() -> None:
    print("\n═══ Delete Assignment ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete assignment #{a.assignment_id}? "
              "All submissions go too. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_assignment(a.assignment_id):
        print(f"\n  ✓ Deleted #{a.assignment_id}")
    _pause()


# ── Submission flows ───────────────────────────────────────────────

def add_students_flow() -> None:
    print("\n═══ Add Student(s) to Assignment ═══")
    try:
        a = _pick_assignment()
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        sub = data.add_student(a.assignment_id, sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added {sid} to #{a.assignment_id} "
          f"(submission #{sub.submission_id})")
    _pause()


def add_class_group_flow() -> None:
    print("\n═══ Add Class Group to Assignment ═══")
    try:
        a = _pick_assignment()
        gid = int(_input("Class group id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        n = data.add_class_group(a.assignment_id, gid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added {n} new student(s) from group #{gid}")
    _pause()


def submit_flow() -> None:
    print("\n═══ Submit ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        late_raw = _input("Late submission? (y/n)", default="n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.submit(sub.submission_id,
                      late=late_raw.lower() in ("y", "yes"))
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Submitted #{sub.submission_id}")
    _pause()


def mark_flow() -> None:
    print("\n═══ Mark Submission ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        marks_raw = _input(
            f"Marks (0-{a.max_marks or '?'})", allow_empty=False)
        grade = _input("Grade letter (optional)") or None
        feedback = _multiline("Feedback")
        marked_by = _input("Marked by",
                              default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        marks = float(marks_raw)
    except ValueError:
        print("  ✗ Marks must be a number.")
        _pause()
        return
    try:
        data.mark_submission(sub.submission_id,
                                marks=marks, grade=grade,
                                feedback=feedback or None,
                                marked_by=marked_by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Marked #{sub.submission_id}: {marks}")
    _pause()


def set_sub_status_flow() -> None:
    print("\n═══ Change Submission Status ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        new_status = _pick_from(
            "New status", list(SUBMISSION_STATUSES),
            default=sub.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_submission_status(sub.submission_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{sub.submission_id} → {new_status}")
    _pause()


def delete_submission_flow() -> None:
    print("\n═══ Delete Submission ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete submission #{sub.submission_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_submission(sub.submission_id):
        print(f"\n  ✓ Deleted #{sub.submission_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Assignments Summary ═══")
    try:
        win = int(_input("Upcoming window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total assignments : {summ.total_assignments}")
    print(f"  Open              : {summ.open_count}")
    print(f"  Overdue           : {summ.overdue}")
    print(f"  Upcoming due ({win}d): {summ.upcoming_due}")
    print(f"\n  Submissions       : {summ.total_submissions}")
    print(f"  Submitted         : {summ.submitted_total}")
    print(f"  Marked            : {summ.marked_total}")
    print("\n  By status:")
    for s in ASSIGNMENT_STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<12} : {n}")
    print("\n  By type:")
    for t in ASSIGNMENT_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")
    if summ.by_subject:
        print("\n  Top subjects:")
        for sub, n in list(summ.by_subject.items())[:10]:
            print(f"    {sub:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",                list_all),
    ("List open",               list_open),
    ("List overdue",            list_overdue),
    ("Filter",                  filter_flow),
    ("View assignment",         view_assignment_flow),
    ("New assignment",          new_assignment),
    ("Edit assignment",         edit_assignment),
    ("Change status",           set_status_flow),
    ("Delete assignment",       delete_assignment_flow),
    ("─" * 6,                   lambda: None),
    ("Add student",             add_students_flow),
    ("Add class group",         add_class_group_flow),
    ("Submit",                  submit_flow),
    ("Mark",                    mark_flow),
    ("Change submission status", set_sub_status_flow),
    ("Delete submission",       delete_submission_flow),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    while True:
        print("\n── Assignments ──")
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
            logger.exception("Assignments CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Assignments":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Assignments CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
