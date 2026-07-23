"""CLI flows for Sixth Form Study Planner."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.academics.study_planner import (
    study_planner as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.academics.study_planner.study_planner import (
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    DEFAULT_TASK_TYPE,
    PRIORITIES,
    STATUSES,
    StudyTask,
    TASK_TYPES,
    ValidationError,
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


def _pick_from(label: str, options: list[str],
                default: str | None = None,
                allow_custom: bool = False) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    if allow_custom:
        print("        (or type a custom value)")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1]
            print("    Out of range.")
            continue
        if allow_custom and raw:
            return raw
        print("    Enter a number (or 'cancel' to abort).")


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


def _pick_subject() -> str | None:
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject") or None
    return _pick_from("Subject", [""] + names, allow_custom=True) or None


def _pick_task() -> StudyTask:
    rows = data.list_tasks()
    if not rows:
        print("    No tasks yet.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Tasks:")
    for i, t in enumerate(rows, 1):
        flag = "!" if t.is_overdue else " "
        print(f"    {i:>3}){flag}#{t.task_id}  "
              f"{(t.planned_date or '—'):<10}  "
              f"{t.student_id}  "
              f"{names.get(t.student_id, '?')[:14]:<14}  "
              f"{t.title[:30]:<30}  [{t.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((t for t in rows if t.task_id == n), None)
            if match:
                return match
        print("    No matching task.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_tasks(rows: list[StudyTask]) -> None:
    if not rows:
        print("\n  (no tasks)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Student':<10}  "
          f"{'Subject':<14}  {'Type':<14}  "
          f"{'Pri':<8}  {'Status':<14}  Title")
    print("  " + "-" * 120)
    for t in rows:
        flag = " !" if t.is_overdue else "  "
        print(f"  {t.task_id:>4}{flag}"
              f"{(t.planned_date or '—'):<10}  "
              f"{t.student_id:<10}  "
              f"{(t.subject_name or '—')[:14]:<14}  "
              f"{t.task_type[:14]:<14}  "
              f"{t.priority:<8}  "
              f"{t.status:<14}  {t.title[:40]}")
    print(f"\n  {len(rows)} task(s).")


def _print_task_full(t: StudyTask) -> None:
    print()
    print(f"    #{t.task_id}  {t.title}")
    print(f"    Student        : {t.student_id}")
    print(f"    Subject        : {t.subject_name or '—'}")
    print(f"    Topic          : {t.topic or '—'}")
    print(f"    Type           : {t.task_type}")
    print(f"    Priority       : {t.priority}")
    print(f"    Status         : {t.status}"
          + ("  (overdue)" if t.is_overdue else ""))
    print(f"    Planned date   : {t.planned_date or '—'}")
    print(f"    Start time     : {t.time_label}")
    print(f"    Planned mins   : {t.planned_duration or '—'}")
    print(f"    Actual mins    : {t.actual_duration or '—'}")
    print(f"    Completed on   : {t.completed_on or '—'}")
    for label, val in (
            ("Description", t.description),
            ("Resources",   t.resources),
            ("Reflection",  t.reflection),
            ("Notes",       t.notes),
    ):
        if val:
            print()
            print(f"    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Tasks ═══")
    _print_tasks(data.list_tasks())
    _pause()


def list_today() -> None:
    print("\n═══ Today ═══")
    _print_tasks(data.list_tasks(today_only=True))
    _pause()


def list_open() -> None:
    print("\n═══ Open Tasks ═══")
    _print_tasks(data.list_tasks(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Tasks ═══")
    _print_tasks(data.list_tasks(overdue_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Tasks ═══")
    try:
        sid = _input("Student id") or None
        subject = _input("Subject") or None
        ttype = _input(f"Type ({'/'.join(TASK_TYPES[:4])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        priority = _input(
            f"Priority ({'/'.join(PRIORITIES)})") or None
        title = _input("Title contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_tasks(
            student_id=sid, subject_name=subject,
            task_type=ttype, status=status, priority=priority,
            title_like=title, date_from=df, date_to=dt2,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_tasks(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_tasks(student_id=sid)
    _print_tasks(rows)
    summ = data.student_summary(sid)
    print(f"\n  Summary for {sid}:")
    print(f"    Total           : {summ.total}")
    print(f"    Completed       : {summ.completed}")
    print(f"    Open            : {summ.open_count}")
    print(f"    Overdue         : {summ.overdue}")
    print(f"    Planned minutes : {summ.minutes_planned}")
    print(f"    Actual minutes  : {summ.minutes_actual}")
    _pause()


def view_task_flow() -> None:
    print("\n═══ View Task ═══")
    try:
        t = _pick_task()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_task_full(t)
    _pause()


def _collect_form(existing: StudyTask | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        print(f"\n  Editing for student {existing.student_id}")
    else:
        payload["student_id"] = _pick_student()
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    if is_edit:
        payload["subject_name"] = _input(
            "Subject",
            default=existing.subject_name or "")
    else:
        payload["subject_name"] = _pick_subject()
    payload["topic"] = _input(
        "Topic",
        default=(existing.topic or "") if is_edit else "")
    payload["task_type"] = _pick_from(
        "Type", list(TASK_TYPES),
        default=(existing.task_type if is_edit
                  else DEFAULT_TASK_TYPE))
    payload["priority"] = _pick_from(
        "Priority", list(PRIORITIES),
        default=(existing.priority if is_edit
                  else DEFAULT_PRIORITY))
    payload["planned_date"] = _input(
        "Planned date (YYYY-MM-DD)",
        default=(existing.planned_date if is_edit
                  else _date.today().isoformat()))
    payload["planned_start"] = _input(
        "Planned start (HH:MM)",
        default=(existing.planned_start[:5]
                  if is_edit and existing.planned_start else ""))
    payload["planned_duration"] = _input(
        "Planned duration (mins)",
        default=(str(existing.planned_duration)
                  if is_edit and existing.planned_duration is not None
                  else "60"))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    payload["resources"] = _input(
        "Resources",
        default=(existing.resources or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_task() -> None:
    print("\n═══ New Study Task ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t = data.create_task(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created task #{t.task_id} {t.title!r}")
    _pause()


def edit_task() -> None:
    print("\n═══ Edit Study Task ═══")
    try:
        t = _pick_task()
        payload = _collect_form(t)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_task(t.task_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{t.task_id}")
    _pause()


def start_flow() -> None:
    print("\n═══ Start Task ═══")
    try:
        t = _pick_task()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.start_task(t.task_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{t.task_id} → In Progress")
    _pause()


def complete_flow() -> None:
    print("\n═══ Complete Task ═══")
    try:
        t = _pick_task()
        actual_raw = _input(
            "Actual duration (mins, optional)",
            default=(str(t.planned_duration)
                      if t.planned_duration is not None else ""))
        reflection = _input("Reflection (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.complete_task(
            t.task_id,
            actual_duration=int(actual_raw) if actual_raw else None,
            reflection=reflection or None,
        )
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{t.task_id} → Completed")
    _pause()


def skip_flow() -> None:
    print("\n═══ Skip Task ═══")
    try:
        t = _pick_task()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.skip_task(t.task_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{t.task_id} → Skipped")
    _pause()


def reschedule_flow() -> None:
    print("\n═══ Reschedule Task ═══")
    try:
        t = _pick_task()
        new_date = _input("New date (YYYY-MM-DD)", allow_empty=False)
        new_start = _input(
            "New start (HH:MM, optional)",
            default=(t.planned_start[:5]
                      if t.planned_start else ""))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.reschedule(t.task_id, new_date=new_date,
                          new_start=new_start or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Rescheduled #{t.task_id} → {new_date}")
    _pause()


def duplicate_flow() -> None:
    print("\n═══ Duplicate Task ═══")
    try:
        t = _pick_task()
        new_date = _input("New planned date (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        new = data.duplicate_task(
            t.task_id, new_date=new_date or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Duplicated → #{new.task_id}")
    _pause()


def plan_block_flow() -> None:
    print("\n═══ Plan Revision Block ═══")
    try:
        sid = _pick_student()
        subject = _pick_subject() or _input("Subject",
                                                allow_empty=False)
        topics_raw = _input("Topics (comma-separated)",
                              allow_empty=False)
        start_date = _input(
            "Start date (YYYY-MM-DD)",
            default=_date.today().isoformat())
        mins = int(_input("Minutes per topic", default="45"))
        priority = _pick_from(
            "Priority", list(PRIORITIES),
            default=DEFAULT_PRIORITY)
        task_type = _pick_from(
            "Type", list(TASK_TYPES),
            default=DEFAULT_TASK_TYPE)
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    topics = [t.strip() for t in topics_raw.split(",")
               if t.strip()]
    try:
        created = data.plan_revision_block(
            sid, subject_name=subject, topics=topics,
            start_date=start_date, daily_minutes=mins,
            priority=priority, task_type=task_type)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Planned {len(created)} task(s) "
          f"({created[0].planned_date} → "
          f"{created[-1].planned_date})")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        t = _pick_task()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=t.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(t.task_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{t.task_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete Task ═══")
    try:
        t = _pick_task()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete task #{t.task_id} ({t.title})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_task(t.task_id):
        print(f"\n  ✓ Deleted #{t.task_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Study Planner Summary ═══")
    try:
        win = int(_input("Upcoming window (days)", default="7"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total tasks       : {summ.total_tasks}")
    print(f"  Open              : {summ.open_count}")
    print(f"  Completed         : {summ.completed_count}")
    print(f"  Overdue           : {summ.overdue}")
    print(f"  Today             : {summ.today_count}")
    print(f"  This week         : {summ.this_week_count}")
    print(f"  Upcoming ({win}d)    : {summ.upcoming}")
    print(f"  Minutes planned   : {summ.minutes_planned}")
    print(f"  Minutes actual    : {summ.minutes_actual}")
    print(f"  Distinct students : {summ.distinct_students}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By type:")
    for t in TASK_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<20} : {n}")
    print("\n  By priority:")
    for p in PRIORITIES:
        n = summ.by_priority.get(p, 0)
        if n:
            print(f"    {p:<8} : {n}")
    if summ.by_subject:
        print("\n  Top subjects:")
        for sub, n in list(summ.by_subject.items())[:10]:
            print(f"    {sub:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Today",              list_today),
    ("Open",               list_open),
    ("Overdue",            list_overdue),
    ("All",                list_all),
    ("Filter",             filter_flow),
    ("Per-student",        per_student_flow),
    ("View task",          view_task_flow),
    ("─" * 6,              lambda: None),
    ("New task",           new_task),
    ("Edit task",          edit_task),
    ("Start",              start_flow),
    ("Complete",           complete_flow),
    ("Skip",               skip_flow),
    ("Reschedule",         reschedule_flow),
    ("Duplicate",          duplicate_flow),
    ("Change status",      set_status_flow),
    ("Delete",             delete_flow),
    ("─" * 6,              lambda: None),
    ("Plan revision block", plan_block_flow),
    ("Summary",            summary_flow),
]


def run() -> None:
    while True:
        print("\n── Study Planner ──")
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
            logger.exception("Study-planner CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Study Planner":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Study-planner CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
