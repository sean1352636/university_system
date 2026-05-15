"""CLI flows for Sixth Form Enrichments."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.academics.enrichment import (
    enrichment as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.academics.enrichment.enrichment import (
    ACTIVITY_STATUSES,
    Activity,
    CATEGORIES,
    DAYS,
    DEFAULT_ACTIVITY_STATUS,
    DEFAULT_CATEGORY,
    DEFAULT_ENROLMENT_STATUS,
    ENROLMENT_STATUSES,
    Enrolment,
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


def _pick_activity() -> Activity:
    rows = data.list_activities()
    if not rows:
        print("    No activities yet.")
        raise _UserAbort
    print("\n  Activities:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.activity_id}  "
              f"{a.name[:24]:<24}  "
              f"{a.when_label[:22]:<22}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows
                            if a.activity_id == n), None)
            if match:
                return match
        print("    No matching activity.")


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


def _pick_enrolment(activity_id: int) -> Enrolment:
    rows = data.list_enrolments(activity_id=activity_id)
    if not rows:
        print("    No enrolments on this activity.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Enrolments:")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>3}) #{e.enrolment_id}  "
              f"{e.student_id}  "
              f"{names.get(e.student_id, '?')[:18]:<18}  "
              f"[{e.status}]  attended={e.sessions_attended}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((e for e in rows
                            if e.enrolment_id == n), None)
            if match:
                return match
        print("    No matching enrolment.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_activities(rows: list[Activity]) -> None:
    if not rows:
        print("\n  (no activities)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<24}  {'Category':<22}  "
          f"{'When':<22}  {'Lead':<14}  "
          f"{'Cap':>4}  Status")
    print("  " + "-" * 110)
    for a in rows:
        cap = (str(a.capacity) if a.capacity is not None else "—")
        print(f"  {a.activity_id:>4}  {a.name[:24]:<24}  "
              f"{a.category[:22]:<22}  "
              f"{a.when_label[:22]:<22}  "
              f"{(a.lead_staff or '—')[:14]:<14}  "
              f"{cap:>4}  {a.status}")
    print(f"\n  {len(rows)} activity/activities.")


def _print_activity_full(a: Activity) -> None:
    detail = data.get_activity_detail(a.activity_id)
    print()
    print(f"    #{a.activity_id}  {a.name}")
    print(f"    Category       : {a.category}")
    print(f"    When           : {a.when_label}")
    print(f"    Location       : {a.location or '—'}")
    print(f"    Lead staff     : {a.lead_staff or '—'}")
    print(f"    Year group     : {a.year_group or '—'}")
    print(f"    Term           : {a.term or '—'}")
    print(f"    Capacity       : "
          f"{a.capacity if a.capacity is not None else '—'}")
    if detail:
        print(f"    Active enrolled: {detail.active_count}/"
              f"{detail.total_enrolments}"
              + (f"  ({detail.remaining_capacity} free)"
                 if detail.remaining_capacity is not None else "")
              + ("  [FULL]" if detail.is_full else ""))
    print(f"    Cost           : "
          f"{('£' + format(a.cost, '.2f')) if a.cost is not None else '—'}")
    print(f"    Status         : {a.status}")
    if a.description:
        print()
        print("    Description:")
        for line in a.description.splitlines():
            print(f"      {line}")
    if a.notes:
        print()
        print("    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")
    if detail and detail.enrolments:
        names = {s.student_id: s.full_name
                  for s in student_data.list_students()}
        print()
        print(f"    Enrolments:")
        for e in detail.enrolments:
            print(f"      #{e.enrolment_id}  {e.student_id}  "
                  f"{names.get(e.student_id, '?')[:18]:<18}  "
                  f"[{e.status}]  attended={e.sessions_attended}"
                  + (f"  last={e.last_attended}"
                     if e.last_attended else ""))


# ── Activity flows ─────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Activities ═══")
    _print_activities(data.list_activities())
    _pause()


def list_open() -> None:
    print("\n═══ Open Activities ═══")
    _print_activities(data.list_activities(open_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Activities ═══")
    try:
        cat = _input(f"Category ({'/'.join(CATEGORIES[:3])}…)") or None
        status = _input(f"Status ({'/'.join(ACTIVITY_STATUSES)})") or None
        day = _input(f"Day ({'/'.join(DAYS[:5])}…)") or None
        year = _input(f"Year ({'/'.join(YEAR_GROUPS)})") or None
        search = _input("Search (name/desc/lead)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_activities(
            category=cat, status=status, day_of_week=day,
            year_group=year, search=search,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_activities(rows)
    _pause()


def view_activity_flow() -> None:
    print("\n═══ View Activity ═══")
    try:
        a = _pick_activity()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_activity_full(a)
    _pause()


def _collect_form(existing: Activity | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["name"] = _input(
        "Name",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["day_of_week"] = _pick_from(
        "Day", [""] + list(DAYS),
        default=(existing.day_of_week if is_edit else ""))
    payload["start_time"] = _input(
        "Start time (HH:MM)",
        default=(existing.start_time[:5]
                  if is_edit and existing.start_time else ""))
    payload["end_time"] = _input(
        "End time (HH:MM)",
        default=(existing.end_time[:5]
                  if is_edit and existing.end_time else ""))
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["lead_staff"] = _input(
        "Lead staff",
        default=(existing.lead_staff or "") if is_edit else "")
    payload["capacity"] = _input(
        "Capacity (optional)",
        default=(str(existing.capacity)
                  if is_edit and existing.capacity is not None
                  else ""))
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["term"] = _input(
        "Term (free text)",
        default=(existing.term or "") if is_edit else "")
    payload["cost"] = _input(
        "Cost (£, optional)",
        default=(f"{existing.cost:.2f}"
                  if is_edit and existing.cost is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(ACTIVITY_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ACTIVITY_STATUS))
    payload["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_activity() -> None:
    print("\n═══ New Activity ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_activity(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created activity #{a.activity_id} {a.name!r}")
    _pause()


def edit_activity() -> None:
    print("\n═══ Edit Activity ═══")
    try:
        a = _pick_activity()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_activity(a.activity_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.activity_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Activity Status ═══")
    try:
        a = _pick_activity()
        new_status = _pick_from("New status",
                                   list(ACTIVITY_STATUSES),
                                   default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_activity_status(a.activity_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.activity_id} → {new_status}")
    _pause()


def delete_activity_flow() -> None:
    print("\n═══ Delete Activity ═══")
    try:
        a = _pick_activity()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete activity #{a.activity_id} ({a.name})? "
              "All enrolments go too. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_activity(a.activity_id):
        print(f"\n  ✓ Deleted #{a.activity_id}")
    _pause()


# ── Enrolment flows ───────────────────────────────────────────────

def sign_up_flow() -> None:
    print("\n═══ Sign Student Up ═══")
    try:
        a = _pick_activity()
        sid = _pick_student()
        role = _input("Role (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.sign_up(a.activity_id, sid, role=role or None)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Enrolled (#{e.enrolment_id})")
    _pause()


def record_attendance_flow() -> None:
    print("\n═══ Record Attendance ═══")
    try:
        a = _pick_activity()
        e = _pick_enrolment(a.activity_id)
        sessions = int(_input("Sessions to add", default="1"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        data.record_attendance(e.enrolment_id, sessions=sessions)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Recorded {sessions} session(s)")
    _pause()


def withdraw_flow() -> None:
    print("\n═══ Withdraw ═══")
    try:
        a = _pick_activity()
        e = _pick_enrolment(a.activity_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw(e.enrolment_id)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Withdrew #{e.enrolment_id}")
    _pause()


def complete_flow() -> None:
    print("\n═══ Complete Enrolment ═══")
    try:
        a = _pick_activity()
        e = _pick_enrolment(a.activity_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.complete(e.enrolment_id)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ #{e.enrolment_id} → Completed")
    _pause()


def set_enrolment_status_flow() -> None:
    print("\n═══ Change Enrolment Status ═══")
    try:
        a = _pick_activity()
        e = _pick_enrolment(a.activity_id)
        new_status = _pick_from(
            "New status", list(ENROLMENT_STATUSES),
            default=e.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_enrolment_status(e.enrolment_id, new_status)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ #{e.enrolment_id} → {new_status}")
    _pause()


def delete_enrolment_flow() -> None:
    print("\n═══ Delete Enrolment ═══")
    try:
        a = _pick_activity()
        e = _pick_enrolment(a.activity_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete enrolment #{e.enrolment_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_enrolment(e.enrolment_id):
        print(f"\n  ✓ Deleted #{e.enrolment_id}")
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Activities ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_enrolments_with_detail(student_id=sid)
    if not rows:
        print("\n  (no enrolments for this student)")
        _pause()
        return
    print(f"\n  {sid} is enrolled on {len(rows)} activity/activities:")
    for r in rows:
        print(f"    #{r.enrolment.enrolment_id}  {r.activity_name}  "
              f"[{r.enrolment.status}]  "
              f"attended={r.enrolment.sessions_attended}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Enrichment Summary ═══")
    summ = data.summary()
    print(f"\n  Total activities  : {summ.total_activities}")
    print(f"  Open              : {summ.open_count}")
    print(f"  Full              : {summ.full_activities}")
    print(f"  Enrolments        : {summ.total_enrolments}")
    print(f"  Active enrolments : {summ.active_enrolments}")
    print(f"  Students engaged  : {summ.students_engaged}")
    print("\n  By status:")
    for s in ACTIVITY_STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By category:")
    for c in CATEGORIES:
        n = summ.by_category.get(c, 0)
        if n:
            print(f"    {c:<26} : {n}")
    if summ.by_day:
        print("\n  By day:")
        for d, n in summ.by_day.items():
            print(f"    {d:<14} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",             list_all),
    ("List open",            list_open),
    ("Filter",               filter_flow),
    ("View activity",        view_activity_flow),
    ("New activity",         new_activity),
    ("Edit activity",        edit_activity),
    ("Change activity status", set_status_flow),
    ("Delete activity",      delete_activity_flow),
    ("─" * 6,                lambda: None),
    ("Sign student up",      sign_up_flow),
    ("Record attendance",    record_attendance_flow),
    ("Withdraw",             withdraw_flow),
    ("Complete",             complete_flow),
    ("Change enrolment status", set_enrolment_status_flow),
    ("Delete enrolment",     delete_enrolment_flow),
    ("Per-student",          per_student_flow),
    ("─" * 6,                lambda: None),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Enrichment ──")
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
            logger.exception("Enrichment CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Enrichment":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Enrichment CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
