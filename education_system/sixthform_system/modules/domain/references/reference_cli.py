"""CLI flows for Sixth Form UCAS References."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.references import references
from education_system.sixthform_system.modules.domain.students import students as data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.references.references import (
    DEFAULT_STATUS,
    Reference,
    SOFT_CHAR_LIMIT,
    STATUSES,
    ValidationError,
    compute_counts,
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


def _read_body(*, default: str = "") -> str:
    """Same body-reader as personal_statement_cli: `@/path`, `EDITOR`,
    or paste-until-`END`. Returns empty string if the user just types
    `END` on the first line."""
    print("\n  Body input (three options):")
    print("    @path/to/file.txt   — read from a file")
    print("    EDITOR              — open $EDITOR / $VISUAL on a temp file")
    print("    (otherwise)         — paste lines; end with 'END' on its own line.")
    if default:
        print("  (current body retained if you type END immediately.)")
    try:
        first = input("  > ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    if first.strip().lower() == "cancel":
        raise _UserAbort

    if first.startswith("@"):
        path = first[1:].strip()
        try:
            return Path(path).expanduser().read_text(encoding="utf-8")
        except OSError as e:
            raise ValidationError(f"Could not read {path}: {e}") from e

    if first.strip().upper() == "EDITOR":
        import os
        import subprocess
        import tempfile
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
        with tempfile.NamedTemporaryFile(
                "w+", suffix=".txt", delete=False, encoding="utf-8") as f:
            if default:
                f.write(default)
            tmp = f.name
        try:
            subprocess.call([editor, tmp])
            return Path(tmp).read_text(encoding="utf-8")
        finally:
            try:
                Path(tmp).unlink()
            except OSError:
                pass

    if first.strip() == "END":
        return default

    lines = [first]
    while True:
        try:
            ln = input()
        except (EOFError, KeyboardInterrupt):
            print()
            raise _UserAbort
        if ln.strip() == "END":
            break
        lines.append(ln)
    return "\n".join(lines)


# ── Print helpers ──────────────────────────────────────────────────

def _print_references(rows: list[Reference]) -> None:
    if not rows:
        print("\n  (no references)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Referee':<18}  "
          f"{'Status':<10}  {'Chars':>5}  {'Submitted':<20}  Updated")
    print("  " + "-" * 96)
    for r in rows:
        sub = r.submitted_at or "—"
        print(f"  {r.reference_id:>4}  {r.student_id:<10}  "
              f"{r.referee[:18]:<18}  {r.status:<10}  "
              f"{r.char_count:>5}  {sub[:20]:<20}  {r.updated_at}")
    print(f"\n  {len(rows)} reference(s).")


# ── CRUD entry points ──────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ References ═══")
    try:
        rows = data.list_references()
    except Exception as e:
        logger.exception("CLI list_references failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_references(rows)
    _row_action_loop(rows)


def filter_references() -> None:
    print("\n═══ Filter References ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        referee = _input("Referee (substring)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_references(
            student_id=sid, referee=referee, status=status)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_references(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.references_for_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_references(rows)
    _row_action_loop(rows)


def view_reference(reference_id: int | None = None) -> None:
    print("\n═══ View Reference ═══")
    try:
        rid = reference_id if reference_id is not None else int(
            _input("Reference ID", allow_empty=False))
    except ValueError:
        print("  ✗ Reference ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    r = data.get_reference(rid)
    if r is None:
        print(f"  ✗ No reference #{rid}")
        _pause()
        return
    print()
    print(f"    Reference ID  : #{r.reference_id}")
    print(f"    Student       : {r.student_id}")
    print(f"    Referee       : {r.referee}  ({r.referee_role or '—'})")
    print(f"    Status        : {r.status}")
    print(f"    Requested at  : {r.requested_at or '—'}")
    print(f"    Submitted at  : {r.submitted_at or '—'}")
    print(f"    Counts        : "
          f"{r.word_count} words · {r.char_count}/{SOFT_CHAR_LIMIT} chars · "
          f"{r.line_count} lines")
    if r.title:
        print(f"    Title         : {r.title}")
    if r.notes:
        print(f"    Notes         : {r.notes}")
    print()
    print("    ── Body ──")
    if r.body:
        for line in r.body.splitlines() or [""]:
            print(f"    {line}")
    else:
        print("    (no body yet)")
    _pause()


def new_reference() -> None:
    print("\n═══ New Reference ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        sid = _pick_student()
        referee = _input("Referee name", allow_empty=False)
        role = _input("Referee role (e.g. Form Tutor)")
        title = _input("Title (optional)")
        status = _pick_from("Status", list(STATUSES),
                             default=DEFAULT_STATUS)
        body = ""
        if status != "Requested":
            body = _read_body()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return

    if body:
        w, c, l = compute_counts(body)
        print(f"\n  Counts: {w} words · {c}/{SOFT_CHAR_LIMIT} chars · "
              f"{l} lines")
        if c > SOFT_CHAR_LIMIT:
            print("  ⚠ Over soft limit — save will be rejected.")
    try:
        r = data.create_reference({
            "student_id":  sid, "referee": referee,
            "referee_role": role, "title": title,
            "body": body, "status": status,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("create_reference crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Saved reference #{r.reference_id} ({r.status})")
    _pause()


def edit_metadata(reference_id: int | None = None) -> None:
    print("\n═══ Edit Metadata ═══")
    try:
        rid = reference_id if reference_id is not None else int(
            _input("Reference ID", allow_empty=False))
    except ValueError:
        print("  ✗ Reference ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_reference(rid)
    if existing is None:
        print(f"  ✗ No reference #{rid}")
        _pause()
        return
    try:
        referee = _input("Referee", default=existing.referee, allow_empty=False)
        role = _input("Referee role", default=existing.referee_role or "")
        title = _input("Title", default=existing.title or "")
        status = _pick_from("Status", list(STATUSES),
                             default=existing.status)
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_reference(rid, {
            "referee": referee, "referee_role": role,
            "title": title, "status": status, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_reference(metadata) crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated reference #{rid}")
    _pause()


def replace_body(reference_id: int | None = None) -> None:
    print("\n═══ Replace Body ═══")
    try:
        rid = reference_id if reference_id is not None else int(
            _input("Reference ID", allow_empty=False))
    except ValueError:
        print("  ✗ Reference ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_reference(rid)
    if existing is None:
        print(f"  ✗ No reference #{rid}")
        _pause()
        return
    try:
        body = _read_body(default=existing.body or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    w, c, l = compute_counts(body)
    print(f"\n  Counts: {w} words · {c}/{SOFT_CHAR_LIMIT} chars · "
          f"{l} lines")
    try:
        data.update_reference(rid, {"body": body})
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_reference(body) crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Body updated.")
    _pause()


def change_status(reference_id: int | None = None) -> None:
    print("\n═══ Change Status ═══")
    try:
        rid = reference_id if reference_id is not None else int(
            _input("Reference ID", allow_empty=False))
    except ValueError:
        print("  ✗ Reference ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_reference(rid)
    if existing is None:
        print(f"  ✗ No reference #{rid}")
        _pause()
        return
    try:
        status = _pick_from("Status", list(STATUSES),
                             default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(rid, status)
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
    if status == "Submitted":
        # The data layer auto-demotes any older Submitted refs for the
        # student. Surface that to the operator.
        print("    (any previously Submitted reference for this student "
              "has been demoted to Drafting)")
    _pause()


def delete_reference_flow(reference_id: int | None = None) -> None:
    print("\n═══ Delete Reference ═══")
    try:
        rid = reference_id if reference_id is not None else int(
            _input("Reference ID", allow_empty=False))
    except ValueError:
        print("  ✗ Reference ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_reference(rid)
    if existing is None:
        print(f"  ✗ No reference #{rid}")
        _pause()
        return
    confirm = _input(
        f"Delete reference #{rid} ({existing.student_id}, "
        f"{existing.referee})? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_reference(rid):
            print(f"\n  ✓ Deleted #{rid}")
    except Exception as e:
        logger.exception("delete_reference crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def summary() -> None:
    print("\n═══ Per-Student Summary ═══")
    rows = data.per_student_summary()
    if not rows:
        print("  (no references yet)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Drafts':>6}  {'Latest':<10}  "
          f"{'Submitted?':<10}  Last referee")
    print("  " + "-" * 68)
    for r in rows:
        print(f"  {r.student_id:<10}  {r.drafts:>6}  "
              f"{(r.latest_status or '—'):<10}  "
              f"{('Yes' if r.has_submitted else 'No'):<10}  "
              f"{r.last_referee or '—'}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[Reference]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit metadata   B) Replace body   "
          "S) Status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "b", "s", "d"):
            print("    Pick V, E, B, S, D, or Enter.")
            continue
        try:
            raw = _input("Reference ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            rid = int(raw)
        except ValueError:
            print("    Reference ID must be a whole number.")
            continue
        if choice == "v":
            view_reference(rid)
        elif choice == "e":
            edit_metadata(rid)
        elif choice == "b":
            replace_body(rid)
        elif choice == "s":
            change_status(rid)
        elif choice == "d":
            delete_reference_flow(rid)
        return


# ── Submenu dispatcher ───────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List References",     list_all),
    ("Filter References",   filter_references),
    ("Per-Student",         per_student),
    ("View Reference",      view_reference),
    ("New Reference",       new_reference),
    ("Edit Metadata",       edit_metadata),
    ("Replace Body",        replace_body),
    ("Change Status",       change_status),
    ("Delete Reference",    delete_reference_flow),
    ("Per-Student Summary", summary),
]


def run() -> None:
    while True:
        print("\n── References ──")
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
            logger.exception("References CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "References":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("References CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
