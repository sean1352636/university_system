"""Small building blocks shared by the wave-2 enrolment screens: a page
in the content frame with its action bar, tables, CSV / text saving,
year pickers, permission checks and result messages."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable, Sequence

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

from .enrolment_common import (
    _clear,
    _default_academic_year,
    _heading,
    _year_choices,
    back_to_directory,
    show_error,
)

logger = logging.getLogger(__name__)

Column = tuple[str, str, int]


def can(*capabilities: str) -> bool:
    """Whether the signed-in user holds any of the capabilities."""
    try:
        from education_system.systems.sixth_form.domain.admissions import _guard
        return any(_guard.can(c) for c in capabilities)
    except Exception:  # noqa: BLE001 — no principal: treat as not allowed
        logger.exception("Capability check failed")
        return False


def can_write() -> bool:
    try:
        return data.can_write()
    except Exception:  # noqa: BLE001
        logger.exception("can_write failed")
        return False


def state(ok: bool) -> str:
    return "normal" if ok else "disabled"


def username() -> str | None:
    return ui.current_username()


def page(gui, title: str, *, back: Callable[[], None] | None = None,
         back_text: str = "Back to Directory") -> tuple[ttk.Frame, ttk.Frame]:
    """Clear the content frame, add the heading and an action bar packed
    at the bottom first (so a tall table never hides it). Returns
    (frame, bar); the bar already holds the Back button."""
    frame = _clear(gui)
    _heading(frame, title)
    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", fill="x", pady=(10, 0))
    ttk.Button(bar, text=back_text,
               command=back or (lambda: back_to_directory(gui))
               ).pack(side="right")
    return frame, bar


def button(bar, text: str, command: Callable[[], Any], *,
           enabled: bool = True) -> ttk.Button:
    b = ttk.Button(bar, text=text, command=command, state=state(enabled))
    b.pack(side="left", padx=(0, 6))
    return b


def note(parent, text: str, *, colour: str = "#555", wrap: int = 900) -> ttk.Label:
    lbl = ttk.Label(parent, text=text, foreground=colour, wraplength=wrap,
                    justify="left")
    lbl.pack(anchor="w", pady=(2, 2))
    return lbl


def section(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 11, "bold")).pack(
        anchor="w", pady=(10, 2))


def fields_grid(parent, rows: Sequence[tuple[str, Any]], *,
                columns: int = 2) -> ttk.Frame:
    """Label/value pairs laid out in ``columns`` pairs per row."""
    grid = ttk.Frame(parent)
    grid.pack(anchor="w", pady=(4, 0))
    for i, (label, value) in enumerate(rows):
        r, c = divmod(i, columns)
        ttk.Label(grid, text=label + ":", foreground="#555", anchor="e",
                  width=22).grid(row=r, column=c * 2, sticky="e", padx=(0, 6), pady=1)
        ttk.Label(grid, text="—" if value in (None, "") else str(value),
                  wraplength=360, justify="left").grid(
            row=r, column=c * 2 + 1, sticky="w", padx=(0, 18), pady=1)
    return grid


def table(parent, columns: Sequence[Column], rows: Iterable[Sequence[Any]], *,
          iids: Sequence[str] | None = None, height: int = 12,
          selectmode: str = "browse", expand: bool = True) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both" if expand else "x", expand=expand, pady=(2, 0))
    tree = ui.make_tree(holder, list(columns), height=height,
                        selectmode=selectmode)
    for i, row in enumerate(rows):
        values = ["" if v is None else v for v in row]
        if iids is not None:
            tree.insert("", "end", iid=str(iids[i]), values=values)
        else:
            tree.insert("", "end", values=values)
    return tree


def selected(tree: ttk.Treeview, title: str, what: str = "a row") -> str | None:
    sel = tree.selection()
    if not sel:
        messagebox.showinfo(title, f"Select {what} first.", parent=tree)
        return None
    return sel[0]


def year_picker(parent, value: str | None = None, *, label: str = "Academic year:",
                on_change: Callable[[str], None] | None = None,
                allow_all: bool = False) -> tk.StringVar:
    """A read-only academic-year picker (``known_academic_years``)."""
    ttk.Label(parent, text=label).pack(side="left")
    choices = _year_choices(*( [value] if value else []))
    if allow_all:
        choices = ["", *choices]
    var = tk.StringVar(value=value if value is not None else _default_academic_year())
    box = ttk.Combobox(parent, textvariable=var, values=choices,
                       state="readonly", width=10)
    box.pack(side="left", padx=(4, 10))
    if on_change is not None:
        box.bind("<<ComboboxSelected>>", lambda _e: on_change(var.get()))
    return var


def save_text(gui, text: str, default_name: str, *, title: str = "Save CSV",
              ext: str = ".csv") -> str | None:
    """Ask where to save ``text`` and write it. Returns the path."""
    if not text:
        messagebox.showinfo(title, "There is nothing to save.", parent=gui.root)
        return None
    path = filedialog.asksaveasfilename(
        parent=gui.root, defaultextension=ext, initialfile=default_name,
        filetypes=[("CSV files" if ext == ".csv" else "Files", f"*{ext}")],
        title=title)
    if not path:
        return None
    try:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    except OSError as exc:
        show_error(gui.root, title, exc)
        return None
    gui.status_var.set(f"Saved {path}")
    messagebox.showinfo(title, f"Saved to:\n{path}", parent=gui.root)
    return path


def csv_rows(rows: Iterable[Any]) -> str:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolment_reports,
    )
    return enrolment_reports.to_csv(list(rows))


def csv_button(bar, gui, rows: Callable[[], Iterable[Any]], name: str,
               text: str = "Export CSV") -> ttk.Button:
    def go() -> None:
        try:
            body = csv_rows(rows())
        except Exception as exc:  # noqa: BLE001 — shown
            show_error(gui.root, "Export CSV", exc)
            return
        save_text(gui, body, name)
    return button(bar, text, go)


def show_lines(gui, title: str, lines: Sequence[str], problems: Sequence[str] = (),
               *, parent=None) -> None:
    """One message with the result lines and, when any, the problems
    (shown as a warning)."""
    body = list(lines) or ["Done."]
    if problems:
        body += ["", "Problems — please check:", *(f"  • {p}" for p in problems)]
    show = messagebox.showwarning if problems else messagebox.showinfo
    show(title, "\n".join(body), parent=parent or gui.root)


def attempt(gui, title: str, fn: Callable[[], Any], *, parent=None) -> Any:
    """Run ``fn``; show a refusal / validation message and return None
    on failure."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — every refusal is shown
        show_error(parent or gui.root, title, exc)
        return None


def ask_form(parent, title: str, fields: list, initial: dict | None = None, *,
             on_submit: Callable[[dict], Any] | None = None) -> dict | None:
    """The admissions modal form (kept here so screens share one)."""
    return ui.ask_form(parent, title, fields, initial, on_submit=on_submit)


def code_of(choice: str | None) -> str:
    """'25 — 16-19 …' -> '25'; '' -> ''."""
    return (choice or "").split(" — ", 1)[0].strip()


def blank_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
    return None if value in ("", None) else value
