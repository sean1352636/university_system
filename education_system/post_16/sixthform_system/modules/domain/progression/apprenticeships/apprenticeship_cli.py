"""CLI flows for Sixth Form Apprenticeships."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.progression.apprenticeships import apprenticeships
from education_system.post_16.sixthform_system.modules.domain.progression.apprenticeships import apprenticeships as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.progression.apprenticeships.apprenticeships import (
    Application,
    DEFAULT_STATUS,
    LEVELS,
    SECTORS,
    STATUSES,
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


# ── Print helpers ──────────────────────────────────────────────────

def _print_applications(rows: list[Application]) -> None:
    if not rows:
        print("\n  (no applications)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Employer':<20}  "
          f"{'Title':<28}  {'L':>2}  {'Status':<12}  "
          f"{'Deadline':<10}  {'Interview':<10}")
    print("  " + "-" * 108)
    for a in rows:
        print(f"  {a.application_id:>4}  {a.student_id:<10}  "
              f"{a.employer[:20]:<20}  "
              f"{a.apprenticeship_name[:28]:<28}  "
              f"{(str(a.level) if a.level else '—'):>2}  "
              f"{a.status:<12}  "
              f"{(a.deadline or '—'):<10}  "
              f"{(a.interview_date or '—'):<10}")
    print(f"\n  {len(rows)} application(s).")


# ── CRUD entry points ──────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Apprenticeships ═══")
    try:
        rows = data.list_applications()
    except Exception as e:
        logger.exception("list_applications failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_applications(rows)
    _row_action_loop(rows)


def filter_applications() -> None:
    print("\n═══ Filter Apprenticeships ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        employer = _input("Employer substring") or None
        level_raw = _input("Level (2-7)") or None
        sector = _input(
            "Sector (exact match — see SECTORS list)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    level = None
    if level_raw:
        try:
            level = int(level_raw)
        except ValueError:
            print("  ✗ Level must be a number.")
            _pause()
            return
    try:
        rows = data.list_applications(
            student_id=sid, employer_like=employer, level=level,
            sector=sector, status=status,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_applications(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.applications_for_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_applications(rows)
    _row_action_loop(rows)


def view_application(application_id: int | None = None) -> None:
    print("\n═══ View Apprenticeship ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except ValueError:
        print("  ✗ Application ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    a = data.get_application(aid)
    if a is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    print()
    print(f"    Application ID  : #{a.application_id}")
    print(f"    Student         : {a.student_id}")
    print(f"    Employer        : {a.employer}")
    print(f"    Apprenticeship  : {a.apprenticeship_name}")
    print(f"    Level           : "
          f"{a.level if a.level else '—'}")
    print(f"    Sector          : {a.sector or '—'}")
    print(f"    Reference       : {a.reference_no or '—'}")
    print(f"    Location        : {a.location or '—'}")
    print(f"    Salary          : "
          f"{('£' + format(a.salary, ',.2f')) if a.salary is not None else '—'}")
    print(f"    Submitted at    : {a.submitted_at or '—'}")
    print(f"    Deadline        : {a.deadline or '—'}")
    print(f"    Interview date  : {a.interview_date or '—'}")
    print(f"    Start date      : {a.start_date or '—'}")
    print(f"    Status          : {a.status}")
    if a.notes:
        print(f"    Notes           : {a.notes}")
    _pause()


def _collect_form(existing: Application | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing apprenticeship #{existing.application_id} "
              f"for {existing.student_id}")
        payload["student_id"] = existing.student_id
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    print("\n  ── Apprenticeship details ──")
    payload["employer"] = _input(
        "Employer",
        default=(existing.employer if is_edit else ""),
        allow_empty=False,
    )
    payload["apprenticeship_name"] = _input(
        "Apprenticeship title",
        default=(existing.apprenticeship_name if is_edit else ""),
        allow_empty=False,
    )
    payload["level"] = _input(
        f"Level ({'/'.join(str(l) for l in LEVELS)}, blank = none)",
        default=(str(existing.level) if is_edit and existing.level else ""),
    )
    sector_options = ["None", *SECTORS]
    sector_default = (existing.sector
                      if is_edit and existing.sector else "None")
    payload["sector"] = _pick_from(
        "Sector", sector_options, default=sector_default)
    if payload["sector"] == "None":
        payload["sector"] = ""

    payload["reference_no"] = _input(
        "Reference number (optional)",
        default=(existing.reference_no or "") if is_edit else "",
    )
    payload["location"] = _input(
        "Location (optional)",
        default=(existing.location or "") if is_edit else "",
    )
    payload["salary"] = _input(
        "Salary £ (optional)",
        default=(f"{existing.salary:.2f}"
                 if is_edit and existing.salary is not None else ""),
    )
    payload["submitted_at"] = _input(
        "Submitted at (YYYY-MM-DD, optional)",
        default=(existing.submitted_at or "") if is_edit else "",
    )
    payload["deadline"] = _input(
        "Deadline (YYYY-MM-DD, optional)",
        default=(existing.deadline or "") if is_edit else "",
    )
    payload["interview_date"] = _input(
        "Interview date (YYYY-MM-DD, optional)",
        default=(existing.interview_date or "") if is_edit else "",
    )
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD, optional)",
        default=(existing.start_date or "") if is_edit else "",
    )
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS),
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


def new_application() -> None:
    print("\n═══ New Apprenticeship ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_application(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("create_application crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Created #{a.application_id} "
          f"({a.employer} — {a.apprenticeship_name}, {a.status})")
    _pause()


def edit_application(application_id: int | None = None) -> None:
    print("\n═══ Edit Apprenticeship ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except ValueError:
        print("  ✗ Application ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_application(aid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_application crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{aid}")
    _pause()


def change_status(application_id: int | None = None) -> None:
    print("\n═══ Change Status ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except ValueError:
        print("  ✗ Application ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    try:
        status = _pick_from("Status", list(STATUSES),
                             default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(aid, status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("set_status crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Status → {status}")
    _pause()


def delete_application_flow(application_id: int | None = None) -> None:
    print("\n═══ Delete Apprenticeship ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except ValueError:
        print("  ✗ Application ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    confirm = _input(
        f"Delete #{aid} ({existing.employer} — "
        f"{existing.apprenticeship_name})? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_application(aid):
            print(f"\n  ✓ Deleted #{aid}")
    except Exception as e:
        logger.exception("delete_application crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def summary() -> None:
    print("\n═══ Summary ═══")
    try:
        iv = int(_input("Interview window in days", default="30"))
        dl = int(_input("Deadline window in days",  default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(
        interview_window_days=iv, deadline_window_days=dl)
    print(f"\n  Applications: {summ.total}  ·  Active: {summ.active}  "
          f"·  Accepted: {summ.accepted}")
    print("\n  By status:")
    for st in STATUSES:
        print(f"    {st:<14} : {summ.by_status.get(st, 0)}")
    if summ.by_sector:
        print("\n  By sector:")
        for sector, n in sorted(summ.by_sector.items(),
                                 key=lambda x: -x[1]):
            print(f"    {sector[:36]:<36} : {n}")
    if summ.by_level:
        print("\n  By level:")
        for level in sorted(summ.by_level.keys()):
            print(f"    Level {level:<8} : {summ.by_level[level]}")
    print()
    print(f"  Upcoming interviews ({iv}d) : {summ.upcoming_interviews}")
    print(f"  Upcoming deadlines  ({dl}d) : {summ.upcoming_deadlines}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[Application]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   S) Status   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "s", "d"):
            print("    Pick V, E, S, D, or Enter.")
            continue
        try:
            raw = _input("Application ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            aid = int(raw)
        except ValueError:
            print("    Application ID must be a whole number.")
            continue
        if choice == "v":
            view_application(aid)
        elif choice == "e":
            edit_application(aid)
        elif choice == "s":
            change_status(aid)
        elif choice == "d":
            delete_application_flow(aid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Applications",     list_all),
    ("Filter Applications",   filter_applications),
    ("Per-Student",           per_student),
    ("View Application",      view_application),
    ("New Application",       new_application),
    ("Edit Application",      edit_application),
    ("Change Status",         change_status),
    ("Delete Application",    delete_application_flow),
    ("Summary",               summary),
]


def run() -> None:
    while True:
        print("\n── Apprenticeships ──")
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
            logger.exception("Apprenticeships CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Apprenticeships":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Apprenticeships CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
