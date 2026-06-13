"""CLI flows for Sixth Form Enrolment CRUD.

Mirrors `enrolment_views`: list/filter, create, view, edit, delete.
Wired in from `cli_main.py` via `dispatch("Enrolment")`, which opens a
small submenu since enrolment is itself a CRUD area.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.enrolments import enrolments
from education_system.sixthform_system.modules.domain.students.enrolments import enrolments as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.students.enrolments.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    """Raised when the user hits Ctrl-C / EOF or types ``cancel``."""


# ── Prompt helpers ──────────────────────────────────────────────────

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


def _default_academic_year() -> str:
    today = date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def _pick_student() -> str:
    """Show the student roll and return the chosen student_id."""
    try:
        students = student_data.list_students()
    except Exception as e:
        logger.exception("Could not load student list")
        print(f"    Error loading students: {e}")
        raise _UserAbort
    if not students:
        print("    No students on roll — add a student first.")
        raise _UserAbort
    print("\n  Students on roll:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or type a student ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            print(f"    Out of range (1..{len(students)}).")
            continue
        # Allow typing the id directly
        match = next((s for s in students if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print(f"    No student with id {raw}.")


# ── Form (add + edit) ───────────────────────────────────────────────

def _collect_form(existing: Enrolment | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing enrolment #{existing.enrolment_id} "
              f"for {existing.student_id}")
        payload["student_id"] = existing.student_id  # immutable
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    print("\n  ── Enrolment details ──")
    payload["academic_year"] = _input(
        "Academic year (YYYY/YY)",
        default=(existing.academic_year if is_edit else _default_academic_year()),
        allow_empty=False,
    )
    payload["year_group"] = _pick_from(
        "Year group",
        [str(y) for y in YEAR_GROUPS],
        default=(str(existing.year_group) if is_edit else str(YEAR_GROUPS[0])),
    )
    payload["tutor_group"] = _input(
        "Tutor group (optional)",
        default=(existing.tutor_group or "") if is_edit else "",
    )
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD, optional)",
        default=((existing.start_date or "") if is_edit
                 else date.today().isoformat()),
    )
    payload["status"] = _pick_from(
        "Status",
        list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS),
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


# ── CRUD entry points ───────────────────────────────────────────────

def _print_table(rows: list[Enrolment]) -> None:
    if not rows:
        print("\n  (no enrolments)")
        return
    try:
        names = {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception:
        logger.exception("Could not build student name map")
        names = {}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<24}  {'Year':<8}  "
          f"{'YG':<3}  {'Tutor':<6}  {'Status':<10}")
    print("  " + "-" * 78)
    for e in rows:
        print(
            f"  {e.enrolment_id:>4}  {e.student_id:<10}  "
            f"{names.get(e.student_id, '—')[:24]:<24}  "
            f"{e.academic_year:<8}  {e.year_group:<3}  "
            f"{(e.tutor_group or '—'):<6}  {e.status:<10}"
        )
    print(f"\n  {len(rows)} enrolment(s).")


def list_all() -> None:
    print("\n═══ Enrolment Directory ═══")
    try:
        rows = data.list_enrolments()
    except Exception as e:
        logger.exception("CLI list_enrolments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def filter_enrolments() -> None:
    print("\n═══ Filter Enrolments ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        year = _input("Academic year") or None
        yg_raw = _input("Year group (12 or 13)")
        status_raw = _input("Status (Enrolled / Pending / Withdrawn / Completed)")
    except _UserAbort:
        print("\n  Cancelled.")
        return

    yg: int | None = None
    if yg_raw:
        try:
            yg = int(yg_raw)
        except ValueError:
            print("  ✗ Year group must be a number.")
            _pause()
            return
    status = status_raw or None
    if status and status not in STATUSES:
        print(f"  ✗ Status must be one of: {', '.join(STATUSES)}")
        _pause()
        return

    try:
        rows = data.list_enrolments(
            academic_year=year, year_group=yg, status=status)
    except Exception as e:
        logger.exception("CLI filter_enrolments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def new_enrolment() -> None:
    print("\n═══ New Enrolment ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        created = data.create_enrolment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_enrolment failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return

    student = student_data.get_student(created.student_id)
    print()
    print(f"  ✓ Created enrolment #{created.enrolment_id}")
    print(f"      Student      : {created.student_id} "
          f"({student.full_name if student else '?'})")
    print(f"      Academic year: {created.academic_year}")
    print(f"      Year group   : {created.year_group}")
    print(f"      Tutor group  : {created.tutor_group or '—'}")
    print(f"      Status       : {created.status}")
    _pause()


def view_enrolment(enrolment_id: int | None = None) -> None:
    print("\n═══ View Enrolment ═══")
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        e = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if e is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    student = student_data.get_student(e.student_id)
    print()
    print(f"    Enrolment ID  : #{e.enrolment_id}")
    print(f"    Student       : {e.student_id} "
          f"({student.full_name if student else '(deleted)'})")
    print(f"    Academic year : {e.academic_year}")
    print(f"    Year group    : Year {e.year_group}")
    print(f"    Tutor group   : {e.tutor_group or '—'}")
    print(f"    Start date    : {e.start_date or '—'}")
    print(f"    Status        : {e.status}")
    print(f"    Created       : {e.created_at}")
    if e.notes:
        print(f"    Notes         : {e.notes}")
    _pause()


def edit_enrolment(enrolment_id: int | None = None) -> None:
    print("\n═══ Edit Enrolment ═══")
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_enrolment(eid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_enrolment(%d) failed", eid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated enrolment #{updated.enrolment_id}")
    _pause()


def delete_enrolment_flow(enrolment_id: int | None = None) -> None:
    print("\n═══ Delete Enrolment ═══")
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    confirm = _input(
        f"Delete enrolment #{existing.enrolment_id} "
        f"({existing.student_id}, {existing.academic_year})? "
        f"Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_enrolment(eid):
            print(f"\n  ✓ Deleted enrolment #{eid}")
        else:
            print(f"\n  ✗ Could not delete enrolment #{eid}")
    except Exception as e:
        logger.exception("CLI delete_enrolment(%d) failed", eid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Row-action helper for list & filter results ─────────────────────

def _row_action_loop(rows: list[Enrolment]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "d"):
            print("    Pick V, E, D, or Enter.")
            continue
        try:
            raw = _input("Enrolment ID", allow_empty=False)
        except _UserAbort:
            print("  Cancelled.")
            return
        try:
            eid = int(raw)
        except ValueError:
            print("    Enrolment ID must be a whole number.")
            continue
        if choice == "v":
            view_enrolment(eid)
        elif choice == "e":
            edit_enrolment(eid)
        elif choice == "d":
            delete_enrolment_flow(eid)
        return


# ── Submenu dispatcher ──────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Enrolments", list_all),
    ("Filter Enrolments",   filter_enrolments),
    ("New Enrolment",       new_enrolment),
    ("View Enrolment",      view_enrolment),
    ("Edit Enrolment",      edit_enrolment),
    ("Delete Enrolment",    delete_enrolment_flow),
]


def run() -> None:
    """Show the Enrolment submenu until the user picks Back."""
    while True:
        print("\n── Enrolment ──")
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
            logger.exception("Enrolment CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    """Run the enrolment submenu when the parent CLI hits "Enrolment".

    Returns True so the caller skips its stub message.
    """
    if label != "Enrolment":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Enrolment CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
