"""CLI flows for Sixth Form Lesson Plans."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.lesson_plans import (
    lesson_plans as data,
)
from education_system.systems.sixth_form.domain.academics.lesson_plans.lesson_plans import (
    DEFAULT_STATUS,
    LEVELS,
    LessonPlan,
    STATUSES,
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
    print(f"\n  {prompt} (end with a single '.' on its own line; "
          f"blank-Enter to accept default)")
    if default:
        print("    [default below, ENTER to keep]")
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


def _pick_subject() -> str:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject", allow_empty=False)
    return _pick_from("Subject", names, allow_custom=True)


def _pick_plan() -> LessonPlan:
    rows = data.list_plans()
    if not rows:
        print("    No lesson plans yet.")
        raise _UserAbort
    print("\n  Lesson plans:")
    for i, p in enumerate(rows, 1):
        date_label = p.planned_date or "—"
        print(f"    {i:>3}) #{p.plan_id}  {date_label:<10}  "
              f"{p.subject_name[:18]:<18}  "
              f"{p.title[:30]:<30}  [{p.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or plan id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((p for p in rows if p.plan_id == n), None)
            if match:
                return match
        print("    No matching plan.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_plans(rows: list[LessonPlan]) -> None:
    if not rows:
        print("\n  (no plans)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Subject':<16}  "
          f"{'Level':<10}  {'Year':<8}  {'Teacher':<16}  "
          f"{'Status':<10}  Title")
    print("  " + "-" * 110)
    for p in rows:
        print(f"  {p.plan_id:>4}  {p.planned_date or '—':<10}  "
              f"{p.subject_name[:16]:<16}  "
              f"{(p.level or '—')[:10]:<10}  "
              f"{(p.year_group or '—'):<8}  "
              f"{(p.teacher or '—')[:16]:<16}  "
              f"{p.status:<10}  {p.title[:40]}")
    print(f"\n  {len(rows)} plan(s).")


def _print_plan_full(p: LessonPlan) -> None:
    print()
    print(f"    #{p.plan_id}  {p.title}")
    print(f"    Subject         : {p.subject_name}")
    print(f"    Level / Year    : "
          f"{p.level or '—'}  ·  {p.year_group or '—'}")
    print(f"    Course id       : {p.course_id or '—'}")
    print(f"    Class group id  : {p.class_group_id or '—'}")
    print(f"    Teacher         : {p.teacher or '—'}")
    print(f"    Sequence / Week : "
          f"#{p.sequence_number or '—'}  ·  wk {p.week_number or '—'}")
    print(f"    Planned date    : {p.planned_date or '—'}")
    print(f"    Delivered on    : {p.delivered_on or '—'}")
    print(f"    Duration        : "
          f"{p.duration_minutes or '—'} min")
    print(f"    Status          : {p.status}")
    if p.topic:
        print(f"    Topic           : {p.topic}")
    if p.keywords:
        print(f"    Keywords        : {p.keywords}")
    for label, value in (
            ("Objectives",       p.objectives),
            ("Success criteria", p.success_criteria),
            ("Activities",       p.activities),
            ("Resources",        p.resources),
            ("Homework",         p.homework),
            ("Assessment",       p.assessment),
            ("Differentiation",  p.differentiation),
            ("Notes",            p.notes),
    ):
        if value:
            print()
            print(f"    {label}:")
            for line in value.splitlines():
                print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Lesson Plans ═══")
    _print_plans(data.list_plans())
    _pause()


def list_open() -> None:
    print("\n═══ Draft / Ready Plans ═══")
    _print_plans(data.list_plans(open_only=True))
    _pause()


def filter_plans() -> None:
    print("\n═══ Filter Plans ═══")
    try:
        subject = _input("Subject (exact match)") or None
        teacher = _input("Teacher contains") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        year = _input(f"Year group ({'/'.join(YEAR_GROUPS)})") or None
        level = _input(f"Level ({'/'.join(LEVELS)})") or None
        title = _input("Title contains") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_plans(
            subject_name=subject, teacher_like=teacher,
            status=status, year_group=year, level=level,
            title_like=title, date_from=date_from, date_to=date_to,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_plans(rows)
    _pause()


def view_plan_flow() -> None:
    print("\n═══ View Plan ═══")
    try:
        p = _pick_plan()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_plan_full(p)
    _pause()


def _collect_form(existing: LessonPlan | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    if is_edit:
        payload["subject_name"] = _input(
            "Subject", default=existing.subject_name, allow_empty=False)
    else:
        payload["subject_name"] = _pick_subject()
    payload["level"] = _pick_from(
        "Level", [""] + list(LEVELS),
        default=(existing.level if is_edit else ""))
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["teacher"] = _input(
        "Teacher",
        default=(existing.teacher or "") if is_edit else "")
    payload["sequence_number"] = _input(
        "Sequence number",
        default=(str(existing.sequence_number)
                  if is_edit and existing.sequence_number is not None
                  else ""))
    payload["week_number"] = _input(
        "Week number",
        default=(str(existing.week_number)
                  if is_edit and existing.week_number is not None
                  else ""))
    payload["planned_date"] = _input(
        "Planned date (YYYY-MM-DD)",
        default=(existing.planned_date or "") if is_edit else "")
    payload["duration_minutes"] = _input(
        "Duration (minutes)",
        default=(str(existing.duration_minutes)
                  if is_edit and existing.duration_minutes is not None
                  else "60"))
    payload["topic"] = _input(
        "Topic",
        default=(existing.topic or "") if is_edit else "")
    payload["keywords"] = _input(
        "Keywords (comma-separated)",
        default=(existing.keywords or "") if is_edit else "")
    try:
        payload["objectives"] = _multiline(
            "Objectives",
            default=(existing.objectives or "") if is_edit else "")
        payload["success_criteria"] = _multiline(
            "Success criteria",
            default=(existing.success_criteria or "")
            if is_edit else "")
        payload["activities"] = _multiline(
            "Activities",
            default=(existing.activities or "") if is_edit else "")
        payload["resources"] = _multiline(
            "Resources",
            default=(existing.resources or "") if is_edit else "")
        payload["homework"] = _multiline(
            "Homework",
            default=(existing.homework or "") if is_edit else "")
        payload["assessment"] = _multiline(
            "Assessment / AfL",
            default=(existing.assessment or "") if is_edit else "")
        payload["differentiation"] = _multiline(
            "Differentiation",
            default=(existing.differentiation or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_plan() -> None:
    print("\n═══ New Lesson Plan ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_plan(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created plan #{p.plan_id} {p.title!r}")
    _pause()


def edit_plan() -> None:
    print("\n═══ Edit Lesson Plan ═══")
    try:
        p = _pick_plan()
        payload = _collect_form(p)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_plan(p.plan_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{p.plan_id}")
    _pause()


def mark_delivered_flow() -> None:
    print("\n═══ Mark Delivered ═══")
    try:
        p = _pick_plan()
        when = _input("Delivered on",
                       default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_delivered(p.plan_id, delivered_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{p.plan_id} → Delivered ({when})")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        p = _pick_plan()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=p.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(p.plan_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{p.plan_id} → {new_status}")
    _pause()


def duplicate_flow() -> None:
    print("\n═══ Duplicate Plan ═══")
    try:
        p = _pick_plan()
        title = _input("New title",
                        default=f"{p.title} (copy)")
        date_str = _input("New planned date (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        new = data.duplicate_plan(p.plan_id, new_title=title,
                                     new_date=date_str or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Duplicated → #{new.plan_id}")
    _pause()


def delete_plan_flow() -> None:
    print("\n═══ Delete Plan ═══")
    try:
        p = _pick_plan()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete plan #{p.plan_id} ({p.title})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_plan(p.plan_id):
        print(f"\n  ✓ Deleted #{p.plan_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Lesson Plans Summary ═══")
    try:
        win = int(_input("Upcoming window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total plans     : {summ.total}")
    print(f"  Drafts          : {summ.drafts}")
    print(f"  Ready           : {summ.ready}")
    print(f"  Delivered       : {summ.delivered}")
    print(f"  Upcoming ({win}d)  : {summ.upcoming}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    if summ.by_subject:
        print("\n  Top subjects:")
        for sub, n in list(summ.by_subject.items())[:10]:
            print(f"    {sub:<22} : {n}")
    if summ.by_teacher:
        print("\n  Top teachers:")
        for t, n in list(summ.by_teacher.items())[:10]:
            print(f"    {t:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",              list_all),
    ("List draft/ready",      list_open),
    ("Filter",                filter_plans),
    ("View plan",             view_plan_flow),
    ("New plan",              new_plan),
    ("Edit plan",             edit_plan),
    ("Mark delivered",        mark_delivered_flow),
    ("Change status",         set_status_flow),
    ("Duplicate plan",        duplicate_flow),
    ("Delete plan",           delete_plan_flow),
    ("Summary",               summary_flow),
]


def run() -> None:
    while True:
        print("\n── Lesson Plans ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Lesson-plans CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Lesson Plans":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Lesson-plans CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
