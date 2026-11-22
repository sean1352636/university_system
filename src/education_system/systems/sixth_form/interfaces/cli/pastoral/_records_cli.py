"""Terminal building blocks for the pastoral record menus.

The CLI twin of ``interfaces/gui/pastoral/_records_ui.py``: prompts are
generated from the same ``TableSpec`` columns the data layer validates,
so the CLI and the GUI always ask for the same fields.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Callable, Iterable, Sequence

from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.pastoral._records import Col, TableSpec

logger = logging.getLogger(__name__)

#: (heading, value function, width)
Column = tuple[str, Callable[[Any], Any], int]
MenuItem = tuple[str, Callable[[], None] | None]


class Abort(Exception):
    """The user typed 'cancel' or pressed Ctrl-D / Ctrl-C."""


def ask(prompt: str, *, default: str = "", required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            raw = input(f"  {prompt}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise Abort
        s = raw.strip()
        if s.lower() == "cancel":
            raise Abort
        if not s and default:
            return default
        if not s and required:
            print("    Value is required (or 'cancel').")
            continue
        return s


def ask_multiline(prompt: str, *, default: str = "") -> str:
    print(f"  {prompt} (finish with an empty line"
          + ("; Enter alone keeps the current text" if default else "")
          + "):")
    lines: list[str] = []
    while True:
        try:
            line = input("    > ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise Abort
        if line.strip().lower() == "cancel":
            raise Abort
        if not line.strip():
            break
        lines.append(line.rstrip())
    return "\n".join(lines) if lines else default


def yes_no(prompt: str, default: bool = False) -> bool:
    return ask(f"{prompt} (y/n)", default="y" if default else "n"
               ).lower() in ("y", "yes")


def pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def pick_from(label: str, options: Sequence[str], *,
              default: str | None = None, allow_blank: bool = False) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        print(f"    {'*' if opt == default else ' '}{i:>2}) {opt}")
    hint = " (blank = none)" if allow_blank and not default else ""
    while True:
        raw = ask(f"Pick #1..{len(options)}{hint}", default=default or "")
        if raw == (default or "") and (default or allow_blank):
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print("    Enter a number from the list (or 'cancel').")


def pick_student(prompt: str = "Student") -> str:
    students = sorted(student_data.list_students(), key=lambda s: s.student_id)
    if not students:
        print("    No students.")
        raise Abort
    while True:
        raw = ask(f"{prompt} ID (or part of a name, '?' to list)",
                  required=True)
        if raw == "?":
            for s in students:
                print(f"    {s.student_id:<10} {s.full_name}")
            continue
        exact = [s for s in students if s.student_id.lower() == raw.lower()]
        if exact:
            return exact[0].student_id
        hits = [s for s in students if raw.lower() in s.full_name.lower()]
        if len(hits) == 1:
            return hits[0].student_id
        if hits:
            for s in hits[:20]:
                print(f"    {s.student_id:<10} {s.full_name}")
            continue
        print("    No matching student.")


def student_names() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def fmt(v: Any) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v).replace("\n", " / ")


def spec_columns(spec: TableSpec) -> list[Column]:
    cols: list[Column] = [("#", lambda r: getattr(r, spec.id_col), 5)]
    names = student_names()
    for c in spec.cols:
        if not c.listed or c.hidden:
            continue
        if c.kind == "student":
            cols.append(("Student", lambda r, n=c.name: getattr(r, n), 9))
            cols.append(("Name", lambda r, n=c.name:
                         names.get(getattr(r, n), "?"), 20))
            continue
        width = {"date": 10, "time": 5, "bool": 4, "int": 6,
                 "money": 10, "multiline": 28}.get(c.kind, 18)
        cols.append((c.label, lambda r, n=c.name: getattr(r, n), width))
    return cols


def print_rows(rows: Sequence[Any], columns: Sequence[Column], *,
               empty: str = "(nothing to show)") -> None:
    if not rows:
        print(f"\n  {empty}")
        return
    head = "  ".join(f"{h[:w]:<{w}}" for h, _f, w in columns)
    print("\n  " + head)
    print("  " + "-" * len(head))
    for r in rows:
        cells = []
        for _h, fn, w in columns:
            try:
                s = fmt(fn(r))
            except Exception:
                s = "?"
            cells.append(f"{s[:w]:<{w}}")
        print("  " + "  ".join(cells))
    print(f"\n  {len(rows)} record(s).")


def show_record(row: Any, spec: TableSpec | None = None) -> None:
    labels = {c.name: c.label for c in spec.cols} if spec else {}
    data = dataclasses.asdict(row) if dataclasses.is_dataclass(row) \
        else dict(vars(row))
    print()
    for k, v in data.items():
        print(f"  {labels.get(k, k.replace('_', ' ').title()):<34} {fmt(v)}")


def prompt_fields(cols: Sequence[Col], *, existing: Any = None,
                  initial: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ask for each column. Blank keeps the current/initial value;
    '-' clears an optional value when editing."""
    out: dict[str, Any] = {}
    initial = initial or {}
    for c in cols:
        if c.hidden or (existing is not None and c.fixed):
            continue
        if existing is None and c.fixed and initial.get(c.name) not in (
                None, ""):
            out[c.name] = initial[c.name]      # e.g. the parent record
            continue
        cur = getattr(existing, c.name, None) if existing is not None \
            else initial.get(c.name)
        if cur is None and existing is None and c.default is not None:
            cur = c.default() if callable(c.default) else c.default
        label = c.label + (" *" if c.required else "")
        if c.kind == "student":
            if existing is None and initial.get(c.name):
                out[c.name] = initial[c.name]
                continue
            out[c.name] = pick_student(label)
        elif c.kind == "choice":
            out[c.name] = pick_from(label, c.choices,
                                    default=cur or None,
                                    allow_blank=not c.required)
        elif c.kind == "bool":
            out[c.name] = yes_no(label, bool(cur))
        elif c.kind == "multiline":
            out[c.name] = ask_multiline(label, default=cur or "")
        else:
            hint = {"date": " (YYYY-MM-DD)", "time": " (HH:MM)",
                    "money": " (£)"}.get(c.kind, "")
            raw = ask(label + hint, default="" if cur is None else str(cur))
            out[c.name] = "" if raw == "-" and not c.required else raw
    return out


def pick_row(rows: Sequence[Any], id_of: Callable[[Any], Any],
             what: str = "record") -> Any:
    if not rows:
        print(f"\n  (no {what}s)")
        raise Abort
    by_id = {str(id_of(r)): r for r in rows}
    while True:
        raw = ask(f"{what.capitalize()} #", required=True)
        if raw in by_id:
            return by_id[raw]
        print(f"    No {what} #{raw} in the list above.")


def run_menu(title: str, items: Sequence[MenuItem]) -> None:
    """Numbered menu loop; None handlers are section headings."""
    while True:
        print(f"\n── {title} ──")
        for i, (label, fn) in enumerate(items, 1):
            print(f"  {i:>2}) {label}" if fn else f"      {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        label, fn = items[int(choice) - 1]
        if fn is None:
            continue
        try:
            fn()
        except Abort:
            print("\n  Cancelled.")
        except Exception as e:      # ValidationError / AccessDenied / bugs
            if type(e).__name__ not in ("ValidationError", "AccessDenied") \
                    and not isinstance(e, (ValueError, PermissionError)):
                logger.exception("%s → %s crashed", title, label)
            print(f"\n  ✗ {e}")
            pause()


def crud_items(what: str, spec: TableSpec, *,
               load: Callable[[], Iterable[Any]],
               create: Callable[[dict[str, Any]], Any] | None = None,
               update: Callable[[int, dict[str, Any]], Any] | None = None,
               delete: Callable[[int], Any] | None = None,
               columns: Sequence[Column] | None = None,
               new_initial: Callable[[], dict[str, Any]] | None = None,
               ) -> list[MenuItem]:
    """List / view / new / edit / delete menu items for one spec."""
    cols = columns

    def _cols() -> Sequence[Column]:
        return cols if cols is not None else spec_columns(spec)

    def _id(r: Any) -> Any:
        return getattr(r, spec.id_col)

    def do_list() -> None:
        print_rows(list(load()), _cols())
        pause()

    def do_view() -> None:
        rows = list(load())
        print_rows(rows, _cols())
        show_record(pick_row(rows, _id, what), spec)
        pause()

    def do_new() -> None:
        initial = new_initial() if new_initial else {}
        vals = prompt_fields(spec.cols, initial=initial)
        vals = {**initial, **vals}
        out = create(vals)
        print(f"\n  ✓ Saved {what} #{_id(out)}.")
        pause()

    def do_edit() -> None:
        rows = list(load())
        print_rows(rows, _cols())
        row = pick_row(rows, _id, what)
        vals = prompt_fields(spec.cols, existing=row)
        update(_id(row), vals)
        print(f"\n  ✓ Updated {what} #{_id(row)}.")
        pause()

    def do_delete() -> None:
        rows = list(load())
        print_rows(rows, _cols())
        row = pick_row(rows, _id, what)
        if yes_no(f"Delete {what} #{_id(row)}?"):
            delete(_id(row))
            print("\n  ✓ Deleted.")
        pause()

    items: list[MenuItem] = [(f"List {what}s", do_list),
                             (f"View {what}", do_view)]
    if create is not None:
        items.append((f"New {what}", do_new))
    if update is not None:
        items.append((f"Edit {what}", do_edit))
    if delete is not None:
        items.append((f"Delete {what}", do_delete))
    return items
