"""Small shared Tk building blocks for the newer finance / GDPR tabs
(bursary payments, free meals, trip refunds, fee rules, budgets, SAR and
retention). Kept deliberately plain: a scrolling table, a modal form, a
read-only text panel and an error-reporting call wrapper.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable, Iterable, Sequence

from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)

logger = logging.getLogger(__name__)

CURRENCY_SYMBOL = "£"


def money(v: Any) -> str:
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    return f"{'-' if x < 0 else ''}{CURRENCY_SYMBOL}{abs(x):,.2f}"


def actor() -> str:
    """The signed-in username (empty when nobody is bound)."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or ""
    except Exception:  # noqa: BLE001 - never block a screen on this
        return ""


def call(widget: tk.Misc, fn: Callable[[], Any], *,
         done: str | None = None) -> Any:
    """Run *fn*; show validation / permission errors as a message box.
    Returns fn's result, or None if it failed."""
    try:
        out = fn()
    except (ValueError, PermissionError) as exc:
        messagebox.showerror("Not done", str(exc), parent=widget)
        return None
    except Exception as exc:  # noqa: BLE001 - report, keep the window
        logger.exception("Finance screen action failed")
        messagebox.showerror("Error", f"Unexpected error: {exc}",
                             parent=widget)
        return None
    if done:
        messagebox.showinfo("Done", done, parent=widget)
    return out


class Table:
    """A Treeview with a vertical scrollbar. ``columns`` is a list of
    (heading, width) pairs; the first value of each row is its iid."""

    def __init__(self, parent: tk.Misc, columns: Sequence[tuple[str, int]],
                 *, height: int = 18) -> None:
        self.frame = ttk.Frame(parent)
        ids = [f"c{i}" for i in range(len(columns))]
        self.tree = ttk.Treeview(self.frame, columns=ids, show="headings",
                                 height=height, selectmode="browse")
        for cid, (head, width) in zip(ids, columns):
            self.tree.heading(cid, text=head)
            self.tree.column(cid, width=width, anchor="w")
        sb = ttk.Scrollbar(self.frame, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("alert", foreground="#b00020")

    def pack(self, **kw: Any) -> None:
        self.frame.pack(**kw)

    def set_rows(self, rows: Iterable[Sequence[Any]], *,
                 alert: Callable[[Sequence[Any]], bool] | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for n, r in enumerate(rows):
            vals = ["" if v is None else v for v in r]
            tags = ("alert",) if alert and alert(r) else ()
            self.tree.insert("", "end", iid=f"{n}:{vals[0]}", values=vals,
                             tags=tags)

    def selected(self) -> list[Any] | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return list(self.tree.item(sel[0], "values"))

    def selected_id(self) -> int | None:
        row = self.selected()
        if not row:
            return None
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return None


def need_selection(widget: tk.Misc, table: Table) -> int | None:
    rid = table.selected_id()
    if rid is None:
        messagebox.showinfo("Select a row", "Select a row first.",
                            parent=widget)
    return rid


class TextPanel:
    def __init__(self, parent: tk.Misc, *, height: int = 20) -> None:
        self.frame = ttk.Frame(parent)
        self.text = tk.Text(self.frame, wrap="word", height=height,
                            font=("TkFixedFont", 10), state="disabled")
        sb = ttk.Scrollbar(self.frame, orient="vertical",
                           command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

    def pack(self, **kw: Any) -> None:
        self.frame.pack(**kw)

    def set(self, content: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")


# A form field: (key, label, kind, default, options)
# kind is "entry", "combo", "check" or "text".
Field = tuple[str, str, str, Any, Sequence[str] | None]


def ask_form(parent: tk.Misc, title: str, fields: Sequence[Field], *,
             note: str | None = None) -> dict[str, Any] | None:
    """A modal form. Returns {key: value} (strings, bools for checks;
    empty strings become None), or None if cancelled."""
    top = tk.Toplevel(parent)
    top.title(title)
    top.transient(parent.winfo_toplevel())
    body = ttk.Frame(top, padding=12)
    body.pack(fill="both", expand=True)
    if note:
        ttk.Label(body, text=note, wraplength=460,
                  justify="left").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))
    vars_: dict[str, Any] = {}
    for row, (key, label, kind, default, options) in enumerate(fields, 1):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="nw",
                                         padx=(0, 8), pady=3)
        if kind == "check":
            v: Any = tk.BooleanVar(value=bool(default))
            ttk.Checkbutton(body, variable=v).grid(row=row, column=1,
                                                   sticky="w")
        elif kind == "combo":
            v = tk.StringVar(value="" if default is None else str(default))
            ttk.Combobox(body, textvariable=v, values=list(options or []),
                         state="readonly", width=48).grid(
                row=row, column=1, sticky="we", pady=3)
        elif kind == "text":
            v = tk.Text(body, width=50, height=4, wrap="word")
            if default:
                v.insert("1.0", str(default))
            v.grid(row=row, column=1, sticky="we", pady=3)
        else:
            v = tk.StringVar(value="" if default is None else str(default))
            ttk.Entry(body, textvariable=v, width=50).grid(
                row=row, column=1, sticky="we", pady=3)
        vars_[key] = (kind, v)
    body.columnconfigure(1, weight=1)
    result: dict[str, Any] = {}
    ok = {"pressed": False}

    def _ok() -> None:
        for key, (kind, v) in vars_.items():
            if kind == "check":
                result[key] = bool(v.get())
            elif kind == "text":
                result[key] = v.get("1.0", "end").strip() or None
            else:
                result[key] = v.get().strip() or None
        ok["pressed"] = True
        top.destroy()

    bar = ttk.Frame(top, padding=(12, 0, 12, 12))
    bar.pack(fill="x")
    ttk.Button(bar, text="OK", command=_ok).pack(side="right")
    ttk.Button(bar, text="Cancel", command=top.destroy).pack(
        side="right", padx=6)
    top.bind("<Escape>", lambda _e: top.destroy())
    grab_when_viewable(top)
    top.wait_window()
    return result if ok["pressed"] else None


def num(v: Any) -> float | None:
    """A form value as a float (None for blank)."""
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(CURRENCY_SYMBOL, "").replace(",", ""))
    except ValueError:
        raise ValueError(f"{v!r} is not a number") from None


def whole(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(str(v))
    except ValueError:
        raise ValueError(f"{v!r} is not a whole number") from None


def student_choices() -> list[str]:
    """'ID — Name' strings for a student combobox."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return [f"{s.student_id} — {s.full_name}"
            for s in students.list_students()]


def student_id(choice: Any) -> str | None:
    if not choice:
        return None
    return str(choice).split(" — ", 1)[0].strip()


def button_bar(parent: tk.Misc,
               buttons: Sequence[tuple[str, Callable[[], None]]]) -> ttk.Frame:
    """A row of buttons, packed at the top (before any expanding table)."""
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=(8, 4))
    for label, cmd in buttons:
        ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=2)
    return bar
