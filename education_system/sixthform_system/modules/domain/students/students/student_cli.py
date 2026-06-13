"""CLI flows for Sixth Form Student CRUD.

Mirrors the GUI panels in `student_views`: add, directory list, search,
view profile, edit, delete. Each prompt swallows EOF / Ctrl-C and
returns the user to the calling submenu — never crashes the launcher.

Wired in from `cli_main.py` under the "Student Management" category.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.students import students as data
from education_system.sixthform_system.modules.domain.students.enrolments import enrolments as enrolments_data
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.sixthform_system.modules.domain.students.students.students import (
    A_LEVEL_SUBJECTS,
    Student,
    ValidationError,
)


def _active_subjects() -> list[str]:
    try:
        names = subjects_data.get_active_names()
        return names or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)

logger = logging.getLogger(__name__)


# ── Prompt helpers ───────────────────────────────────────────────────

class _UserAbort(Exception):
    """Raised when the user hits Ctrl-C or types ``cancel`` at a prompt."""


def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
    """Prompt with a default value and graceful EOF / Ctrl-C handling.

    Typing ``cancel`` at any prompt raises `_UserAbort` so callers can
    bail out of the whole flow cleanly.
    """
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


def _pick_subject(slot: int, existing: str | None = None) -> str:
    """Render the A-Level subject list and let the user pick one by number."""
    choices = _active_subjects()
    print(f"\n  A-Level subject {slot}:")
    for i, subj in enumerate(choices, 1):
        marker = " *" if subj == existing else "  "
        print(f"    {marker}{i:>2}) {subj}")
    while True:
        raw = _input(f"  Pick #1..{len(choices)}",
                     default=existing or "")
        if existing and raw == existing:
            return existing
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(choices)):
            print(f"    Out of range (1..{len(choices)}).")
            continue
        return choices[n - 1]


# ── Form (add + edit) ────────────────────────────────────────────────

def _collect_form(existing: Student | None) -> dict[str, Any]:
    """Prompt for every field, pre-filling from `existing` if provided."""
    is_edit = existing is not None
    print()
    print("  ── Identity ──")
    payload: dict[str, Any] = {
        "first_name":  _input("First name", default=(existing.first_name if is_edit else ""), allow_empty=False),
        "middle_name": _input("Middle name (optional)",
                              default=(existing.middle_name if is_edit else "")),
        "last_name":   _input("Last name", default=(existing.last_name if is_edit else ""), allow_empty=False),
    }
    print("\n  ── Contact ──")
    payload["phone"] = _input("Phone number",
                              default=(existing.phone if is_edit else ""))

    print("\n  ── Emergency contact ──")
    payload["emergency_contact_name"] = _input(
        "Name", default=(existing.emergency_contact_name if is_edit else ""))
    payload["emergency_contact_phone"] = _input(
        "Phone", default=(existing.emergency_contact_phone if is_edit else ""))
    payload["emergency_contact_relation"] = _input(
        "Relation", default=(existing.emergency_contact_relation if is_edit else ""))

    print("\n  ── A-Level subjects (pick three) ──")
    payload["subject_1"] = _pick_subject(1, existing.subject_1 if is_edit else None)
    payload["subject_2"] = _pick_subject(2, existing.subject_2 if is_edit else None)
    payload["subject_3"] = _pick_subject(3, existing.subject_3 if is_edit else None)
    return payload


def add_student() -> None:
    print("\n═══ Add Student ═══")
    print("  (type 'cancel' at any prompt to abort)\n")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        student = data.create_student(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI create_student failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return

    password = data._derive_password(student.first_name)
    print()
    print("  ✓ Student created")
    print(f"      Student ID : {student.student_id}")
    print(f"      Name       : {student.full_name}")
    print(f"      Email      : {student.email}")
    print()
    print("  Login credentials (shared auth):")
    print(f"      Username   : {student.student_id}")
    print(f"      Password   : {password}")
    _pause()


def edit_student(student_id: str | None = None) -> None:
    print("\n═══ Edit Student ═══")
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_student(sid)
    if existing is None:
        print(f"\n  ✗ No student with id {sid}")
        _pause()
        return
    print(f"\n  Editing {existing.student_id} — {existing.full_name}")
    print("  (Enter to keep the current value; 'cancel' to abort)\n")
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_student(sid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_student(%s) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated {updated.student_id} ({updated.full_name})")
    _pause()


# ── Read (list / search / profile) ──────────────────────────────────

def _print_table(rows: list[Student]) -> None:
    if not rows:
        print("\n  (no students)")
        return
    print()
    print(f"  {'ID':<10}  {'Name':<28}  {'Email':<32}  A-Levels")
    print(f"  {'-'*10}  {'-'*28}  {'-'*32}  {'-'*40}")
    for s in rows:
        print(
            f"  {s.student_id:<10}  {s.full_name[:28]:<28}  "
            f"{s.email[:32]:<32}  {', '.join(s.subjects)}"
        )
    print(f"\n  {len(rows)} student(s).")


def student_directory() -> None:
    print("\n═══ Student Directory ═══")
    try:
        rows = data.list_students()
    except Exception as e:
        logger.exception("CLI list_students failed")
        print(f"\n  ✗ Error loading directory: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def search_students() -> None:
    print("\n═══ Search Students ═══")
    try:
        q = _input("Search (id, name, or email)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.search_students(q)
    except Exception as e:
        logger.exception("CLI search_students(%r) failed", q)
        print(f"\n  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def view_profile(student_id: str | None = None) -> None:
    print("\n═══ Student Profile ═══")
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = data.get_student(sid)
    if student is None:
        print(f"\n  ✗ No student with id {sid}")
        _pause()
        return
    year_label = enrolments_data.current_year_group_label(sid) or "Not enrolled"
    print()
    print(f"    Student ID    : {student.student_id}")
    print(f"    Name          : {student.full_name}")
    print(f"    Current year  : {year_label}")
    print(f"    Sixth-form email: {student.email}")
    print(f"    Phone         : {student.phone or '—'}")
    print()
    print("    Emergency contact:")
    print(f"      Name        : {student.emergency_contact_name or '—'}")
    print(f"      Phone       : {student.emergency_contact_phone or '—'}")
    print(f"      Relation    : {student.emergency_contact_relation or '—'}")
    print()
    print("    A-Level subjects:")
    for i, subj in enumerate(student.subjects, 1):
        print(f"      {i}) {subj}")
    _pause()


def delete_student_flow(student_id: str | None = None) -> None:
    print("\n═══ Delete Student ═══")
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = data.get_student(sid)
    if student is None:
        print(f"\n  ✗ No student with id {sid}")
        _pause()
        return
    confirm = _input(
        f"Permanently delete {student.full_name} ({student.student_id})? Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_student(sid):
            print(f"\n  ✓ Deleted {sid}")
        else:
            print(f"\n  ✗ Could not delete {sid}")
    except Exception as e:
        logger.exception("CLI delete_student(%s) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Row-action helper for list & search results ─────────────────────

def _row_action_loop(rows: list[Student]) -> None:
    """After printing a list, let the user pick a row to view/edit/delete."""
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
            sid = _input("Student ID", allow_empty=False)
        except _UserAbort:
            print("  Cancelled.")
            return
        if choice == "v":
            view_profile(sid)
        elif choice == "e":
            edit_student(sid)
        elif choice == "d":
            delete_student_flow(sid)
        return


# ── Dispatch ────────────────────────────────────────────────────────

HANDLERS: dict[str, Callable[[], None]] = {
    "Student Directory": student_directory,
    "Add Student":       add_student,
    "Search Students":   search_students,
    "Student Profile":   view_profile,
}


def dispatch(label: str) -> bool:
    """Run the CLI flow matching a menu label.

    Returns True if a handler ran (the caller should skip its stub
    output), False if no real handler exists for that label.
    """
    handler = HANDLERS.get(label)
    if handler is None:
        return False
    try:
        handler()
    except _UserAbort:
        print("\n  Cancelled.")
    except Exception as e:
        logger.exception("CLI handler %r crashed", label)
        print(f"\n  ✗ Unexpected error in {label}: {e}")
        _pause()
    return True
