"""CLI flows for Sixth Form Subjects & A-Levels."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.subjects import subjects as data
from education_system.systems.sixth_form.domain.academics.subjects.subjects import (
    DEFAULT_QUALIFICATION,
    EXAM_BOARDS,
    QUALIFICATIONS,
    Subject,
    ValidationError,
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


def _yes_no(prompt: str, default: bool = True) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


# ── Form (add + edit) ───────────────────────────────────────────────

def _collect_form(existing: Subject | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    print("\n  ── Subject details ──")
    payload["name"] = _input(
        "Subject name",
        default=(existing.name if is_edit else ""),
        allow_empty=False,
    )
    payload["qualification"] = _pick_from(
        "Qualification", list(QUALIFICATIONS),
        default=(existing.qualification if is_edit else DEFAULT_QUALIFICATION),
    )
    payload["exam_board"] = _pick_from(
        "Exam board (or 'None')",
        ["None", *EXAM_BOARDS],
        default=(existing.exam_board if (is_edit and existing.exam_board)
                 else "None"),
    )
    if payload["exam_board"] == "None":
        payload["exam_board"] = ""
    payload["description"] = _input(
        "Description (optional)",
        default=(existing.description or "") if is_edit else "",
    )
    payload["is_active"] = _yes_no(
        "Active?", default=(existing.is_active if is_edit else True),
    )
    return payload


# ── CRUD entry points ───────────────────────────────────────────────

def _print_table(rows: list[Subject]) -> None:
    if not rows:
        print("\n  (no subjects)")
        return
    print()
    print(f"  {'#':>3}  {'Subject':<28}  {'Qualification':<18}  "
          f"{'Board':<14}  Active  Students  Courses")
    print("  " + "-" * 92)
    for s in rows:
        usage = data.is_in_use(s.name)
        print(
            f"  {s.subject_id:>3}  {s.name[:28]:<28}  "
            f"{s.qualification:<18}  {(s.exam_board or '—'):<14}  "
            f"{'Yes' if s.is_active else 'No ':<6}  "
            f"{usage['students']:>8}  {usage['courses']:>7}"
        )
    print(f"\n  {len(rows)} subject(s).")


def list_all() -> None:
    print("\n═══ Subjects & A-Levels ═══")
    try:
        rows = data.list_subjects()
    except Exception as e:
        logger.exception("CLI list_subjects failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def filter_subjects() -> None:
    print("\n═══ Filter Subjects ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        qual = _input("Qualification (e.g. A-Level)") or None
        if qual and qual not in QUALIFICATIONS:
            print(f"  ✗ Unknown qualification: {qual}")
            _pause()
            return
        board = _input("Exam board") or None
        if board and board not in EXAM_BOARDS:
            print(f"  ✗ Unknown exam board: {board}")
            _pause()
            return
        show = _input("Show (all / active / inactive)", default="all").lower()
        search = _input("Search (name / description)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        rows = data.list_subjects(
            qualification=qual, exam_board=board,
            include_inactive=(show != "active"),
            search=search,
        )
        if show == "inactive":
            rows = [r for r in rows if not r.is_active]
    except Exception as e:
        logger.exception("CLI filter_subjects failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def new_subject() -> None:
    print("\n═══ New Subject ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        created = data.create_subject(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_subject failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print()
    print(f"  ✓ Created subject #{created.subject_id}")
    print(f"      Name          : {created.name}")
    print(f"      Qualification : {created.qualification}")
    print(f"      Exam board    : {created.exam_board or '—'}")
    print(f"      Active        : {'Yes' if created.is_active else 'No'}")
    _pause()


def view_subject(subject_id: int | None = None) -> None:
    print("\n═══ View Subject ═══")
    try:
        sid = subject_id if subject_id is not None else int(
            _input("Subject ID", allow_empty=False))
    except ValueError:
        print("  ✗ Subject ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        s = data.get_subject(sid)
    except Exception as exc:
        logger.exception("CLI get_subject(%d) failed", sid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if s is None:
        print(f"  ✗ No subject #{sid}")
        _pause()
        return

    usage = data.is_in_use(s.name)
    print()
    print(f"    Subject ID    : #{s.subject_id}")
    print(f"    Name          : {s.name}")
    print(f"    Qualification : {s.qualification}")
    print(f"    Exam board    : {s.exam_board or '—'}")
    print(f"    Active        : {'Yes' if s.is_active else 'No'}")
    print(f"    Created       : {s.created_at}")
    print(f"    In use        : {usage['students']} student(s), "
          f"{usage['courses']} course(s)")
    if s.description:
        print(f"    Description   : {s.description}")
    _pause()


def edit_subject(subject_id: int | None = None) -> None:
    print("\n═══ Edit Subject ═══")
    try:
        sid = subject_id if subject_id is not None else int(
            _input("Subject ID", allow_empty=False))
    except ValueError:
        print("  ✗ Subject ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_subject(sid)
    except Exception as exc:
        logger.exception("CLI get_subject(%d) failed", sid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No subject #{sid}")
        _pause()
        return

    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_subject(sid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_subject(%d) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated subject #{updated.subject_id} ({updated.name})")
    _pause()


def toggle_active() -> None:
    print("\n═══ Activate / Deactivate Subject ═══")
    try:
        sid = int(_input("Subject ID", allow_empty=False))
    except ValueError:
        print("  ✗ Subject ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    existing = data.get_subject(sid)
    if existing is None:
        print(f"  ✗ No subject #{sid}")
        _pause()
        return
    try:
        if existing.is_active:
            data.deactivate(sid)
            print(f"\n  ✓ Deactivated '{existing.name}' "
                  f"(hidden from new dropdowns; existing rows unaffected).")
        else:
            data.activate(sid)
            print(f"\n  ✓ Activated '{existing.name}'.")
    except Exception as e:
        logger.exception("CLI toggle_active(%d) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def delete_subject_flow(subject_id: int | None = None) -> None:
    print("\n═══ Delete Subject ═══")
    try:
        sid = subject_id if subject_id is not None else int(
            _input("Subject ID", allow_empty=False))
    except ValueError:
        print("  ✗ Subject ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    existing = data.get_subject(sid)
    if existing is None:
        print(f"  ✗ No subject #{sid}")
        _pause()
        return

    usage = data.is_in_use(existing.name)
    if usage["students"] or usage["courses"]:
        print(f"\n  '{existing.name}' is in use by {usage['students']} "
              f"student(s) and {usage['courses']} course(s). "
              f"Hard delete is blocked.")
        if _yes_no("Deactivate it instead", default=True):
            try:
                data.deactivate(sid)
                print(f"  ✓ Deactivated '{existing.name}'.")
            except Exception as e:
                logger.exception("Deactivate fallback failed")
                print(f"  ✗ {e}")
        else:
            print("  No change.")
        _pause()
        return

    confirm = _input(
        f"Permanently delete '{existing.name}'? Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_subject(sid):
            print(f"\n  ✓ Deleted subject #{sid}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("CLI delete_subject(%d) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Row-action loop ─────────────────────────────────────────────────

def _row_action_loop(rows: list[Subject]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   T) Toggle Active   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "t", "d"):
            print("    Pick V, E, T, D, or Enter.")
            continue
        try:
            raw = _input("Subject ID", allow_empty=False)
        except _UserAbort:
            print("  Cancelled.")
            return
        try:
            sid = int(raw)
        except ValueError:
            print("    Subject ID must be a whole number.")
            continue
        if choice == "v":
            view_subject(sid)
        elif choice == "e":
            edit_subject(sid)
        elif choice == "t":
            existing = data.get_subject(sid)
            if existing is None:
                print(f"    No subject #{sid}.")
                continue
            try:
                if existing.is_active:
                    data.deactivate(sid)
                    print(f"  ✓ Deactivated '{existing.name}'.")
                else:
                    data.activate(sid)
                    print(f"  ✓ Activated '{existing.name}'.")
            except Exception as e:
                logger.exception("Toggle failed")
                print(f"  ✗ {e}")
            _pause()
        elif choice == "d":
            delete_subject_flow(sid)
        return


# ── Submenu dispatcher ──────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Subjects",  list_all),
    ("Filter Subjects",    filter_subjects),
    ("New Subject",        new_subject),
    ("View Subject",       view_subject),
    ("Edit Subject",       edit_subject),
    ("Activate/Deactivate", toggle_active),
    ("Delete Subject",     delete_subject_flow),
]


def run() -> None:
    while True:
        print("\n── Subjects & A-Levels ──")
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
            logger.exception("Subjects CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Subjects & A-Levels":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Subjects CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
