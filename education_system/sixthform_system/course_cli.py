"""CLI flows for Sixth Form Course CRUD.

Mirrors `course_views`: directory, filter, new/view/edit/delete. Wired
in from `cli_main.py` via `dispatch("Courses")`, which opens a small
submenu (Courses is itself a CRUD area).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable

from education_system.sixthform_system import courses as data
from education_system.sixthform_system.courses import (
    Course,
    DEFAULT_MAX_STUDENTS,
    ValidationError,
    YEAR_GROUPS,
)
from education_system.sixthform_system import subjects as subjects_data
from education_system.sixthform_system.students import A_LEVEL_SUBJECTS


def _active_subjects() -> list[str]:
    try:
        names = subjects_data.get_active_names()
        return names or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)

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


# ── Form (add + edit) ───────────────────────────────────────────────

def _collect_form(existing: Course | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    print("\n  ── Course details ──")
    payload["course_code"] = _input(
        "Course code (e.g. MATH-12-2025)",
        default=(existing.course_code if is_edit else ""),
        allow_empty=False,
    )
    subj_choices = _active_subjects()
    payload["subject"] = _pick_from(
        "Subject", subj_choices,
        default=(existing.subject if is_edit else
                 (subj_choices[0] if subj_choices else "")),
    )
    payload["title"] = _input(
        "Title", default=(existing.title if is_edit else ""), allow_empty=False)
    payload["year_group"] = _pick_from(
        "Year group", [str(y) for y in YEAR_GROUPS],
        default=(str(existing.year_group) if is_edit else str(YEAR_GROUPS[0])),
    )
    payload["academic_year"] = _input(
        "Academic year (YYYY/YY)",
        default=(existing.academic_year if is_edit else _default_academic_year()),
        allow_empty=False,
    )
    payload["teacher"] = _input(
        "Teacher (optional)",
        default=(existing.teacher or "") if is_edit else "")
    payload["room"] = _input(
        "Room (optional)",
        default=(existing.room or "") if is_edit else "")
    payload["max_students"] = _input(
        "Max students",
        default=str(existing.max_students if is_edit else DEFAULT_MAX_STUDENTS),
    )
    payload["description"] = _input(
        "Description (optional)",
        default=(existing.description or "") if is_edit else "")
    return payload


# ── CRUD entry points ───────────────────────────────────────────────

def _print_table(rows: list[Course]) -> None:
    if not rows:
        print("\n  (no courses)")
        return
    print()
    print(f"  {'#':>4}  {'Code':<14}  {'Subject':<20}  {'Title':<28}  "
          f"{'YG':<3}  {'Year':<8}  Teacher")
    print("  " + "-" * 95)
    for c in rows:
        print(
            f"  {c.course_id:>4}  {c.course_code:<14}  "
            f"{c.subject[:20]:<20}  {c.title[:28]:<28}  "
            f"{c.year_group:<3}  {c.academic_year:<8}  {c.teacher or '—'}"
        )
    print(f"\n  {len(rows)} course(s).")


def list_all() -> None:
    print("\n═══ Courses ═══")
    try:
        rows = data.list_courses()
    except Exception as e:
        logger.exception("CLI list_courses failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def filter_courses() -> None:
    print("\n═══ Filter Courses ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        subject = _input("Subject (exact, or blank)") or None
        if subject and not subjects_data.is_valid_subject(subject):
            print(f"  ✗ Unknown subject: {subject}")
            _pause()
            return
        yg_raw = _input("Year group (12 or 13)")
        year = _input("Academic year") or None
        search = _input("Search (code / title / teacher)") or None
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

    try:
        rows = data.list_courses(
            subject=subject, year_group=yg,
            academic_year=year, search=search,
        )
    except Exception as e:
        logger.exception("CLI filter_courses failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def new_course() -> None:
    print("\n═══ New Course ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        created = data.create_course(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_course failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print()
    print(f"  ✓ Created course #{created.course_id}")
    print(f"      Code         : {created.course_code}")
    print(f"      Subject      : {created.subject}")
    print(f"      Title        : {created.title}")
    print(f"      Year group   : Year {created.year_group}")
    print(f"      Academic year: {created.academic_year}")
    print(f"      Teacher      : {created.teacher or '—'}")
    print(f"      Room         : {created.room or '—'}")
    _pause()


def view_course(course_id: int | None = None) -> None:
    print("\n═══ View Course ═══")
    try:
        cid = course_id if course_id is not None else int(
            _input("Course ID", allow_empty=False))
    except ValueError:
        print("  ✗ Course ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        c = data.get_course(cid)
    except Exception as exc:
        logger.exception("CLI get_course(%d) failed", cid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if c is None:
        print(f"  ✗ No course #{cid}")
        _pause()
        return
    print()
    print(f"    Course ID    : #{c.course_id}")
    print(f"    Code         : {c.course_code}")
    print(f"    Subject      : {c.subject}")
    print(f"    Title        : {c.title}")
    print(f"    Year group   : Year {c.year_group}")
    print(f"    Academic year: {c.academic_year}")
    print(f"    Teacher      : {c.teacher or '—'}")
    print(f"    Room         : {c.room or '—'}")
    print(f"    Max students : {c.max_students}")
    print(f"    Created      : {c.created_at}")
    if c.description:
        print(f"    Description  : {c.description}")
    _pause()


def edit_course(course_id: int | None = None) -> None:
    print("\n═══ Edit Course ═══")
    try:
        cid = course_id if course_id is not None else int(
            _input("Course ID", allow_empty=False))
    except ValueError:
        print("  ✗ Course ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_course(cid)
    except Exception as exc:
        logger.exception("CLI get_course(%d) failed", cid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No course #{cid}")
        _pause()
        return

    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_course(cid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_course(%d) failed", cid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated course #{updated.course_id} ({updated.course_code})")
    _pause()


def delete_course_flow(course_id: int | None = None) -> None:
    print("\n═══ Delete Course ═══")
    try:
        cid = course_id if course_id is not None else int(
            _input("Course ID", allow_empty=False))
    except ValueError:
        print("  ✗ Course ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_course(cid)
    except Exception as exc:
        logger.exception("CLI get_course(%d) failed", cid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No course #{cid}")
        _pause()
        return

    confirm = _input(
        f"Delete course {existing.course_code} ({existing.subject}, "
        f"Year {existing.year_group} {existing.academic_year})? "
        f"Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_course(cid):
            print(f"\n  ✓ Deleted course #{cid}")
        else:
            print(f"\n  ✗ Could not delete course #{cid}")
    except Exception as e:
        logger.exception("CLI delete_course(%d) failed", cid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Row-action loop ────────────────────────────────────────────────

def _row_action_loop(rows: list[Course]) -> None:
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
            raw = _input("Course ID", allow_empty=False)
        except _UserAbort:
            print("  Cancelled.")
            return
        try:
            cid = int(raw)
        except ValueError:
            print("    Course ID must be a whole number.")
            continue
        if choice == "v":
            view_course(cid)
        elif choice == "e":
            edit_course(cid)
        elif choice == "d":
            delete_course_flow(cid)
        return


# ── Submenu dispatcher ──────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Courses", list_all),
    ("Filter Courses",   filter_courses),
    ("New Course",       new_course),
    ("View Course",      view_course),
    ("Edit Course",      edit_course),
    ("Delete Course",    delete_course_flow),
]


def run() -> None:
    while True:
        print("\n── Courses ──")
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
            logger.exception("Courses CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Courses":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Courses CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
