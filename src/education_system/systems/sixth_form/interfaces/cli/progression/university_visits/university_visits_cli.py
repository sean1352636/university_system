"""CLI flows for Sixth Form University Visits."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.systems.sixth_form.domain.progression.university_visits import university_visits as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.progression.university_visits.university_visits import (
    DEFAULT_TRANSPORT,
    DEFAULT_VISIT_STATUS,
    DEFAULT_VISIT_TYPE,
    DEFAULT_YEAR_GROUP,
    TRANSPORT_MODES,
    UniversityVisit,
    VISIT_STATUSES,
    VISIT_TYPES,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


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


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            print(f"    Out of range (1..{len(students)}).")
            continue
        match = next((s for s in students
                      if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Listing / printing ────────────────────────────────────────────

def _print_visits(rows: list[UniversityVisit]) -> None:
    if not rows:
        print("\n  (no visits)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'University':<26}  "
          f"{'Type':<14}  {'Year':<9}  {'Status':<10}  Capacity")
    print("  " + "-" * 92)
    for v in rows:
        cap = "—" if v.capacity is None else str(v.capacity)
        print(f"  {v.visit_id:>4}  {v.visit_date:<10}  "
              f"{v.university_name[:26]:<26}  "
              f"{v.visit_type[:14]:<14}  "
              f"{v.year_group:<9}  {v.status:<10}  {cap}")
    print(f"\n  {len(rows)} visit(s).")


def list_visits() -> None:
    print("\n═══ University Visits ═══")
    rows = data.list_visits()
    _print_visits(rows)
    _row_action_loop(rows)


def filter_visits() -> None:
    print("\n═══ Filter Visits ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        uni = _input("University substring") or None
        vtype = _input(f"Type ({'/'.join(VISIT_TYPES)})") or None
        yg = _input(f"Year group ({'/'.join(YEAR_GROUPS)})") or None
        status = _input(f"Status ({'/'.join(VISIT_STATUSES)})") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_visits(
            university_like=uni, visit_type=vtype,
            year_group=yg, status=status,
            date_from=df, date_to=dt,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_visits(rows)
    _row_action_loop(rows)


def view_visit(visit_id: int | None = None) -> None:
    print("\n═══ View Visit ═══")
    try:
        vid = visit_id if visit_id is not None else int(
            _input("Visit ID", allow_empty=False))
    except ValueError:
        print("  ✗ Visit ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    v = data.get_visit(vid)
    if v is None:
        print(f"  ✗ No visit #{vid}")
        _pause()
        return
    print()
    print(f"    Visit ID       : #{v.visit_id}")
    print(f"    University     : {v.university_name}")
    print(f"    Type           : {v.visit_type}")
    print(f"    Date           : {v.visit_date}")
    print(f"    Depart / Return: {v.departure_time or '—'}"
          f"  /  {v.return_time or '—'}")
    print(f"    Location       : {v.location or '—'}")
    print(f"    Year group     : {v.year_group}")
    print(f"    Organiser      : {v.organiser_staff_id or '—'}")
    print(f"    Transport      : {v.transport}")
    print(f"    Cost / student : £{v.cost_per_student:.2f}")
    print(f"    Capacity       : "
          f"{'—' if v.capacity is None else v.capacity}")
    print(f"    Status         : {v.status}")
    attendees = data.list_attendees(v.visit_id)
    print(f"    Attendees      : {len(attendees)}")
    if attendees:
        for a in attendees:
            mark = "✓" if a.attended else " "
            print(f"      [{mark}] {a.student_id}"
                  + (f"  — {a.notes}" if a.notes else ""))
    if v.notes:
        print(f"\n    Notes: {v.notes}")
    _pause()


def _collect_visit(existing: UniversityVisit | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing visit #{existing.visit_id} — "
              f"{existing.university_name}")

    print("\n  ── Visit details ──")
    today = _date.today().isoformat()
    payload["university_name"] = _input(
        "University name",
        default=(existing.university_name if is_edit else ""),
        allow_empty=False,
    )
    payload["visit_type"] = _pick_from(
        "Visit type", list(VISIT_TYPES),
        default=(existing.visit_type if is_edit else DEFAULT_VISIT_TYPE),
    )
    payload["visit_date"] = _input(
        "Visit date (YYYY-MM-DD)",
        default=(existing.visit_date if is_edit else today),
        allow_empty=False,
    )
    payload["departure_time"] = _input(
        "Departure time (HH:MM, optional)",
        default=(existing.departure_time or "") if is_edit else "",
    )
    payload["return_time"] = _input(
        "Return time (HH:MM, optional)",
        default=(existing.return_time or "") if is_edit else "",
    )
    payload["location"] = _input(
        "Pick-up location (optional)",
        default=(existing.location or "") if is_edit else "",
    )
    payload["year_group"] = _pick_from(
        "Year group", list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else DEFAULT_YEAR_GROUP),
    )
    payload["organiser_staff_id"] = _input(
        "Organiser (staff ID, optional)",
        default=(existing.organiser_staff_id or "") if is_edit else "",
    )
    payload["transport"] = _pick_from(
        "Transport", list(TRANSPORT_MODES),
        default=(existing.transport if is_edit else DEFAULT_TRANSPORT),
    )
    payload["cost_per_student"] = _input(
        "Cost per student (£)",
        default=(f"{existing.cost_per_student:.2f}" if is_edit else "0.00"),
    )
    payload["capacity"] = _input(
        "Capacity (optional)",
        default=(str(existing.capacity) if is_edit and existing.capacity
                 else ""),
    )
    payload["status"] = _pick_from(
        "Status", list(VISIT_STATUSES),
        default=(existing.status if is_edit else DEFAULT_VISIT_STATUS),
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


def new_visit() -> None:
    print("\n═══ New University Visit ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_visit(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = data.create_visit(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created visit #{v.visit_id} "
          f"({v.university_name}, {v.visit_date})")
    _pause()


def edit_visit(visit_id: int | None = None) -> None:
    print("\n═══ Edit Visit ═══")
    try:
        vid = visit_id if visit_id is not None else int(
            _input("Visit ID", allow_empty=False))
    except ValueError:
        print("  ✗ Visit ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_visit(vid)
    if existing is None:
        print(f"  ✗ No visit #{vid}")
        _pause()
        return
    try:
        payload = _collect_visit(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_visit(vid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated visit #{vid}")
    _pause()


def delete_visit_flow(visit_id: int | None = None) -> None:
    print("\n═══ Delete Visit ═══")
    try:
        vid = visit_id if visit_id is not None else int(
            _input("Visit ID", allow_empty=False))
    except ValueError:
        print("  ✗ Visit ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_visit(vid)
    if existing is None:
        print(f"  ✗ No visit #{vid}")
        _pause()
        return
    confirm = _input(
        f"Delete visit #{vid} ({existing.university_name}, "
        f"{existing.visit_date})? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_visit(vid):
        print(f"\n  ✓ Deleted #{vid}")
    _pause()


# ── Attendees ─────────────────────────────────────────────────────

def add_attendee_flow() -> None:
    print("\n═══ Add Attendee ═══")
    try:
        vid = int(_input("Visit ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_visit(vid) is None:
        print(f"  ✗ No visit #{vid}")
        _pause()
        return
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        notes = _input("Notes (optional)")
    except _UserAbort:
        return
    try:
        data.add_attendee(vid, sid, notes=notes or None)
        print(f"\n  ✓ Added {sid} to visit #{vid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def record_attendance() -> None:
    print("\n═══ Record Attendance ═══")
    try:
        vid = int(_input("Visit ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    attendees = data.list_attendees(vid)
    if not attendees:
        print(f"  (no attendees on visit #{vid})")
        _pause()
        return
    print("\n  Attendees:")
    for i, a in enumerate(attendees, 1):
        mark = "✓" if a.attended else " "
        print(f"    {i:>3}) [{mark}] {a.student_id}")
    try:
        raw = _input(
            "Pick #N to toggle attended (Enter to finish)",
            allow_empty=True)
    except _UserAbort:
        return
    if not raw:
        return
    if not raw.isdigit() or not (1 <= int(raw) <= len(attendees)):
        print("    Invalid selection.")
        _pause()
        return
    target = attendees[int(raw) - 1]
    data.set_attendance(target.attendee_id, not target.attended)
    print(f"\n  ✓ {'Marked as attended' if not target.attended else 'Unmarked'} "
          f"for {target.student_id}")
    _pause()


def remove_attendee_flow() -> None:
    print("\n═══ Remove Attendee ═══")
    try:
        vid = int(_input("Visit ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    attendees = data.list_attendees(vid)
    if not attendees:
        print(f"  (no attendees on visit #{vid})")
        _pause()
        return
    print("\n  Attendees:")
    for i, a in enumerate(attendees, 1):
        print(f"    {i:>3}) {a.student_id}")
    try:
        raw = _input(f"Pick #1..{len(attendees)}",
                     allow_empty=False)
    except _UserAbort:
        return
    if not raw.isdigit() or not (1 <= int(raw) <= len(attendees)):
        print("    Invalid selection.")
        _pause()
        return
    target = attendees[int(raw) - 1]
    confirm = _input(f"Remove {target.student_id} from #{vid}? Type 'yes'",
                     default="no")
    if confirm.lower() != "yes":
        return
    data.remove_attendee(target.attendee_id)
    print(f"\n  ✓ Removed {target.student_id}")
    _pause()


# ── Per-student ──────────────────────────────────────────────────

def per_student() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    visits = data.visits_for_student(sid)
    print(f"\n  Visits for {sid} ({len(visits)}):")
    _print_visits(visits)
    _pause()


# ── Summary ───────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ University Visits Summary ═══")
    try:
        window = int(_input("Upcoming window in days", default="30"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    s = data.summary(upcoming_window_days=window)

    print(f"\n  Total visits      : {s.total_visits}")
    print(f"  Total attendees   : {s.total_attendees}")
    print(f"  Students attended : {s.students_attended}")
    print(f"  Upcoming ({window}d)  : {s.upcoming_visits}")

    print("\n  By status:")
    for k in VISIT_STATUSES:
        print(f"    {k:<12} : {s.by_status.get(k, 0)}")

    print("\n  By type:")
    for k in VISIT_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<24} : {n}")

    print("\n  By year group:")
    for k in YEAR_GROUPS:
        print(f"    {k:<10} : {s.by_year_group.get(k, 0)}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[UniversityVisit]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   D) Delete   "
          "A) Add attendee   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "d", "a"):
            print("    Pick V, E, D, A, or Enter.")
            continue
        try:
            raw = _input("Visit ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            vid = int(raw)
        except ValueError:
            print("    Visit ID must be a whole number.")
            continue
        if choice == "v":
            view_visit(vid)
        elif choice == "e":
            edit_visit(vid)
        elif choice == "d":
            delete_visit_flow(vid)
        elif choice == "a":
            if data.get_visit(vid) is None:
                print(f"  ✗ No visit #{vid}")
                _pause()
                return
            try:
                sid = _pick_student()
            except _UserAbort:
                return
            try:
                data.add_attendee(vid, sid)
                print(f"\n  ✓ Added {sid} to visit #{vid}")
            except ValidationError as e:
                print(f"\n  ✗ {e}")
            _pause()
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Visits",        list_visits),
    ("Filter Visits",      filter_visits),
    ("New Visit",          new_visit),
    ("View Visit",         view_visit),
    ("Edit Visit",         edit_visit),
    ("Delete Visit",       delete_visit_flow),
    ("Add Attendee",       add_attendee_flow),
    ("Record Attendance",  record_attendance),
    ("Remove Attendee",    remove_attendee_flow),
    ("Per-Student",        per_student),
    ("Summary",            summary),
]


def run() -> None:
    while True:
        print("\n── University Visits ──")
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
            logger.exception("University-visits CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "University Visits":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("University-visits CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
