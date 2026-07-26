"""CLI flows for Sixth Form Personal Statements.

The CLI doesn't expose a full multi-line editor (that's what the GUI
is for); instead it lets staff:

* list / filter drafts,
* view a draft inline (with paginated body output),
* create a new draft by pasting a single block (`END` on its own line
  finishes input),
* change status,
* update feedback / reviewer / title,
* push an approved draft to the student's UCAS application,
* delete drafts.

It also offers a "import from file" shortcut so staff can edit the body
in their preferred editor and paste a path.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable
from education_system.systems.sixth_form.domain.progression.personal_statements import personal_statements
from education_system.systems.sixth_form.domain.progression.personal_statements import personal_statements as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.progression.personal_statements.personal_statements import (
    DEFAULT_STATUS,
    MAX_CHARS,
    MAX_LINES,
    PersonalStatement,
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


def _read_body() -> str:
    """Prompt staff for the body. Three modes:

    1. ``@<path>`` reads the file at that path.
    2. ``EDITOR`` opens ``$EDITOR`` (or ``$VISUAL``) on a temp file.
    3. Otherwise: keep reading until a line of just ``END`` is seen.

    Returns the body (may exceed UCAS limits — the save step validates).
    """
    print("\n  Enter the statement body. Three options:")
    print("    @path/to/file.txt    — read from a file")
    print("    EDITOR               — open $EDITOR / $VISUAL on a temp file")
    print("    (otherwise)          — type or paste lines; end with 'END' "
          "on its own line.")
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
            tmp = f.name
        try:
            subprocess.call([editor, tmp])
            return Path(tmp).read_text(encoding="utf-8")
        finally:
            try:
                Path(tmp).unlink()
            except OSError:
                pass

    # Free-form: keep reading lines until END.
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


# ── CRUD entry points ──────────────────────────────────────────────

def _print_statements(rows: list[PersonalStatement]) -> None:
    if not rows:
        print("\n  (no statements)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Status':<10}  {'Chars':>5}  "
          f"{'Lines':>5}  {'Title':<24}  Updated")
    print("  " + "-" * 86)
    for s in rows:
        print(f"  {s.statement_id:>4}  {s.student_id:<10}  "
              f"{s.status:<10}  {s.char_count:>5}  {s.line_count:>5}  "
              f"{(s.title or '—')[:24]:<24}  {s.updated_at}")
    print(f"\n  {len(rows)} statement(s).")


def list_all() -> None:
    print("\n═══ Personal Statements ═══")
    try:
        rows = data.list_statements()
    except Exception as e:
        logger.exception("CLI list_statements failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_statements(rows)
    _row_action_loop(rows)


def filter_statements() -> None:
    print("\n═══ Filter Statements ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_statements(student_id=sid, status=status)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_statements(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.statements_for_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_statements(rows)
    _row_action_loop(rows)


def view_statement(statement_id: int | None = None) -> None:
    print("\n═══ View Statement ═══")
    try:
        sid = statement_id if statement_id is not None else int(
            _input("Statement ID", allow_empty=False))
    except ValueError:
        print("  ✗ Statement ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    s = data.get_statement(sid)
    if s is None:
        print(f"  ✗ No statement #{sid}")
        _pause()
        return
    print()
    print(f"    Statement ID : #{s.statement_id}")
    print(f"    Student      : {s.student_id}")
    print(f"    Title        : {s.title or '—'}")
    print(f"    Status       : {s.status}")
    print(f"    Counts       : "
          f"{s.word_count} words · {s.char_count}/{MAX_CHARS} chars · "
          f"{s.line_count}/{MAX_LINES} lines")
    if s.reviewer:
        print(f"    Reviewer     : {s.reviewer}  (at {s.reviewed_at or '—'})")
    if s.feedback:
        print(f"    Feedback     : {s.feedback}")
    print(f"    Updated      : {s.updated_at}")
    print()
    print("    ── Body ──")
    for line in s.body.splitlines() or [""]:
        print(f"    {line}")
    _pause()


def new_statement() -> None:
    print("\n═══ New Personal Statement ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        sid = _pick_student()
        title = _input("Title (optional)")
        status = _pick_from("Status", list(STATUSES),
                             default=DEFAULT_STATUS)
        body = _read_body()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return

    # Live preview before save
    w, c, l = compute_counts(body)
    print(f"\n  Counts: {w} words · {c}/{MAX_CHARS} chars · "
          f"{l}/{MAX_LINES} lines")
    if c > MAX_CHARS or l > MAX_LINES:
        print("  ⚠ This will be rejected at save — over UCAS limit.")
    try:
        s = data.create_statement({
            "student_id": sid, "title": title, "body": body,
            "status": status,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("create_statement crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Saved statement #{s.statement_id}")
    _pause()


def edit_metadata(statement_id: int | None = None) -> None:
    """Edit title / status / reviewer / feedback (not the body)."""
    print("\n═══ Edit Metadata ═══")
    try:
        sid = statement_id if statement_id is not None else int(
            _input("Statement ID", allow_empty=False))
    except ValueError:
        print("  ✗ Statement ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_statement(sid)
    if existing is None:
        print(f"  ✗ No statement #{sid}")
        _pause()
        return
    try:
        title = _input("Title", default=existing.title or "")
        status = _pick_from("Status", list(STATUSES),
                             default=existing.status)
        reviewer = _input("Reviewer", default=existing.reviewer or "")
        feedback = _input("Feedback", default=existing.feedback or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_statement(sid, {
            "title": title, "status": status,
            "reviewer": reviewer, "feedback": feedback,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_statement(metadata) crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated statement #{sid}")
    _pause()


def replace_body(statement_id: int | None = None) -> None:
    """Replace the body — re-prompts using the same body-reader."""
    print("\n═══ Replace Body ═══")
    try:
        sid = statement_id if statement_id is not None else int(
            _input("Statement ID", allow_empty=False))
    except ValueError:
        print("  ✗ Statement ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_statement(sid)
    if existing is None:
        print(f"  ✗ No statement #{sid}")
        _pause()
        return

    try:
        body = _read_body()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    w, c, l = compute_counts(body)
    print(f"\n  Counts: {w} words · {c}/{MAX_CHARS} chars · "
          f"{l}/{MAX_LINES} lines")
    try:
        data.update_statement(sid, {"body": body})
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_statement(body) crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print("\n  ✓ Body updated.")
    _pause()


def change_status(statement_id: int | None = None) -> None:
    print("\n═══ Change Status ═══")
    try:
        sid = statement_id if statement_id is not None else int(
            _input("Statement ID", allow_empty=False))
    except ValueError:
        print("  ✗ Statement ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_statement(sid)
    if existing is None:
        print(f"  ✗ No statement #{sid}")
        _pause()
        return
    try:
        status = _pick_from("Status", list(STATUSES),
                             default=existing.status)
        reviewer = _input("Reviewer (optional)",
                          default=existing.reviewer or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(sid, status, reviewer=reviewer or None)
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


def push_to_ucas_flow(statement_id: int | None = None) -> None:
    print("\n═══ Push to UCAS ═══")
    try:
        sid = statement_id if statement_id is not None else int(
            _input("Statement ID", allow_empty=False))
    except ValueError:
        print("  ✗ Statement ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_statement(sid)
    if existing is None:
        print(f"  ✗ No statement #{sid}")
        _pause()
        return
    confirm = _input(
        f"Copy statement #{sid} to {existing.student_id}'s UCAS application?\n"
        f"  (Status will be set to Submitted.) Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        aid = data.push_to_ucas(sid)
        print(f"\n  ✓ Copied to UCAS application #{aid}.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("push_to_ucas crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def delete_statement_flow(statement_id: int | None = None) -> None:
    print("\n═══ Delete Statement ═══")
    try:
        sid = statement_id if statement_id is not None else int(
            _input("Statement ID", allow_empty=False))
    except ValueError:
        print("  ✗ Statement ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_statement(sid)
    if existing is None:
        print(f"  ✗ No statement #{sid}")
        _pause()
        return
    confirm = _input(
        f"Delete statement #{sid} ({existing.student_id})? Type 'yes'",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_statement(sid):
            print(f"\n  ✓ Deleted #{sid}")
    except Exception as e:
        logger.exception("delete_statement crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Per-student summary ──────────────────────────────────────────

def summary() -> None:
    print("\n═══ Per-Student Summary ═══")
    rows = data.per_student_summary()
    if not rows:
        print("  (no statements yet)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Drafts':>6}  {'Latest':<12}  "
          f"{'Chars':>5}  {'Lines':>5}  Submitted?")
    print("  " + "-" * 64)
    for s in rows:
        print(f"  {s.student_id:<10}  {s.drafts:>6}  "
              f"{(s.latest_status or '—'):<12}  "
              f"{s.latest_chars:>5}  {s.latest_lines:>5}  "
              f"{'Yes' if s.has_submitted else 'No'}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[PersonalStatement]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit metadata   B) Replace body   "
          "S) Status   P) Push to UCAS   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "b", "s", "p", "d"):
            print("    Pick V, E, B, S, P, D, or Enter.")
            continue
        try:
            raw = _input("Statement ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            sid = int(raw)
        except ValueError:
            print("    Statement ID must be a whole number.")
            continue
        if choice == "v":
            view_statement(sid)
        elif choice == "e":
            edit_metadata(sid)
        elif choice == "b":
            replace_body(sid)
        elif choice == "s":
            change_status(sid)
        elif choice == "p":
            push_to_ucas_flow(sid)
        elif choice == "d":
            delete_statement_flow(sid)
        return


# ── Submenu dispatcher ───────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Statements",      list_all),
    ("Filter Statements",    filter_statements),
    ("Per-Student",          per_student),
    ("View Statement",       view_statement),
    ("New Statement",        new_statement),
    ("Edit Metadata",        edit_metadata),
    ("Replace Body",         replace_body),
    ("Change Status",        change_status),
    ("Push to UCAS",         push_to_ucas_flow),
    ("Delete Statement",     delete_statement_flow),
    ("Per-Student Summary",  summary),
]


def run() -> None:
    while True:
        print("\n── Personal Statements ──")
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
            logger.exception("Personal-statements CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Personal Statements":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Personal-statements CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
