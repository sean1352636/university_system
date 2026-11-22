"""Terminal prompt helpers shared by the exams-office menus."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable, Sequence

logger = logging.getLogger(__name__)


class UserAbort(Exception):
    pass


def default_year() -> int:
    today = _date.today()
    return today.year if today.month < 9 else today.year + 1


def ask(prompt: str, *, default: Any = "", required: bool = False) -> str:
    d = "" if default is None else str(default)
    suffix = f" [{d}]" if d else ""
    while True:
        try:
            raw = input(f"  {prompt}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise UserAbort
        s = raw.strip()
        if s.lower() == "cancel":
            raise UserAbort
        if not s:
            s = d
        if s == "-":          # explicit blank over a default
            s = ""
        if s or not required:
            return s
        print("    Value is required.")


def yes(prompt: str, *, default: bool = False) -> bool:
    return ask(f"{prompt} (y/n)", default="y" if default else "n").lower().startswith("y")


def pick(label: str, options: Sequence[str], *, default: str | None = None,
         allow_blank: bool = False) -> str:
    print(f"\n  {label}:")
    if allow_blank:
        print("     0) (none)")
    for i, opt in enumerate(options, 1):
        mark = " *" if opt == default else "  "
        print(f"   {mark}{i:>2}) {opt}")
    while True:
        raw = ask(f"Pick #1..{len(options)}", default=default or "")
        if raw == (default or None):
            return raw
        if allow_blank and raw in ("", "0"):
            return ""
        if raw in options:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("    Enter a number from the list (or 'cancel').")


def pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def pick_student() -> str:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise UserAbort
    raw = ask("Student ID (or '?' to list)", required=True)
    if raw == "?":
        for s in rows:
            print(f"    {s.student_id:<10} {s.full_name}")
        raw = ask("Student ID", required=True)
    match = next((s for s in rows if s.student_id.lower() == raw.lower()), None)
    if match is None:
        print("    No such student.")
        raise UserAbort
    return match.student_id


def series() -> tuple[str, int]:
    from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
        DEFAULT_SEASON, SEASONS,
    )
    season = pick("Season", list(SEASONS), default=DEFAULT_SEASON)
    year = ask("Year", default=default_year(), required=True)
    try:
        return season, int(year)
    except ValueError:
        print("    Year must be a number.")
        raise UserAbort from None


def board(*, allow_blank: bool = False, default: str | None = None) -> str:
    from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
        EXAM_BOARDS,
    )
    return pick("Board", list(EXAM_BOARDS), default=default, allow_blank=allow_blank)


def form(fields: Sequence[tuple], initial: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prompt for each field. A field is ``(key, label)`` for free text,
    ``(key, label, options)`` for a pick list, or ``(key, label, bool)``
    for yes/no. Enter keeps the shown default; '-' clears it."""
    initial = initial or {}
    out: dict[str, Any] = {}
    for f in fields:
        key, label = f[0], f[1]
        cur = initial.get(key)
        if len(f) > 2 and isinstance(f[2], bool):
            out[key] = yes(label, default=bool(cur))
        elif len(f) > 2:
            out[key] = pick(label, list(f[2]), default=cur or None, allow_blank=True)
        else:
            out[key] = ask(label, default="" if cur is None else cur)
    return out


def show_table(headers: Sequence[tuple[str, int]], rows: Sequence[Sequence[Any]]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print("  " + "  ".join(f"{h:<{w}}" for h, w in headers))
    print("  " + "-" * (sum(w for _, w in headers) + 2 * len(headers)))
    for r in rows:
        cells = ["—" if v in (None, "") else str(v) for v in r]
        print("  " + "  ".join(f"{c[:w]:<{w}}" for c, (_, w) in zip(cells, headers)))
    print(f"\n  {len(rows)} row(s).")


def save_text(content: str, default_name: str) -> None:
    print()
    print(content)
    path = ask("Save to file (blank = don't)", default="")
    if path:
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(content)
            print(f"  ✓ Saved to {path}")
        except OSError as e:
            print(f"  ✗ Could not save: {e}")


def run_menu(title: str, menu: Sequence[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(menu, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(menu)):
            print("  Invalid selection.")
            continue
        try:
            menu[int(choice) - 1][1]()
        except UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            if type(e).__name__ == "_UserAbort":     # reused attendance CLI flows
                print("\n  Cancelled.")
            elif isinstance(e, (ValueError, PermissionError)):
                print(f"\n  ✗ {e}")
                pause()
            else:
                logger.exception("%s CLI handler crashed", title)
                print(f"\n  ✗ Unexpected error: {e}")
                pause()


def sensitive(area: str, capabilities: Sequence[str]) -> bool:
    """Check + log access for a restricted menu; prints a refusal."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        p = access.current()
        allowed = any(p.can(getattr(access, c)) for c in capabilities)
        access.log_sensitive_access(p, area, "view", allowed=allowed)
    except (ImportError, AttributeError):
        allowed = True
    if not allowed:
        print("\n  ✗ This area is restricted to the exams office.")
        pause()
    return allowed


def log_change(area: str, action: str, *, student_id: str | None = None,
               record_ref: str | None = None) -> None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        access.log_sensitive_access(access.current(), area, action,
                                    student_id=student_id, record_ref=record_ref)
    except (ImportError, AttributeError):
        pass
