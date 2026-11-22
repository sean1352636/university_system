"""The tabbed page the SEND, Medical and Pupil Premium screens share.

A page lists its tabs in ``TABS``; each tab is built the first time it is
shown by ``_tab_<slug>(frame)``, which returns that tab's refresh function.
The chosen tab is remembered in ``state["tab"]``. The helpers here keep the
three screens alike: toolbars with filters, buttons that are disabled for
people who can't use them, tables that remember their rows, forms, CSV export
and e-mail sent in the background.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.gui.components import widgets as W

YEARS = ("7", "8", "9", "10", "11")
ERRORS = W.ERRORS


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def money(v: float | None) -> str:
    return "" if v is None else f"£{v:,.2f}"


def num(v: Any) -> str:
    return "-" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))


def changed(obj: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Only the values that differ from *obj* (blank = None)."""
    out = {}
    for k, v in values.items():
        cur = getattr(obj, k, None)
        if isinstance(cur, bool) or isinstance(v, bool):
            if bool(v) != bool(cur):
                out[k] = v
        elif str(v if v is not None else "") != str(cur if cur is not None else ""):
            out[k] = v
    return out


def filled(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if v not in ("", None)}


class Table:
    """A tree plus the objects behind its rows."""

    def __init__(self, parent, columns, *, height: int = 14, stretch: Iterable[str] = (),
                 select: str = "browse", tags: dict | None = None) -> None:
        self.tree = W.tree(parent, columns, height=height, select=select, stretch=stretch,
                           tags={**W.STANDARD_TAGS, **(tags or {})})
        self.rows: dict[str, Any] = {}

    def fill(self, items: Iterable[Any], key: Callable[[Any], Any],
             values: Callable[[Any], tuple], tag: Callable[[Any], str | None] | None = None
             ) -> None:
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for i, x in enumerate(items):
            iid = str(key(x) if key else i)
            if iid in self.rows:
                iid = f"{iid}:{i}"
            self.rows[iid] = x
            t = tag(x) if tag else None
            self.tree.insert("", "end", iid=iid, values=values(x), tags=(t,) if t else ())

    def selected(self) -> Any:
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def selected_all(self) -> list[Any]:
        return [self.rows[s] for s in self.tree.selection() if s in self.rows]

    def on_double(self, fn: Callable[[], None]) -> None:
        self.tree.bind("<Double-1>", lambda _e: fn())


class TabbedPage:
    TITLE = ""
    TABS: tuple[str, ...] = ()

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None, editor: bool = False) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil, self.editor = open_pupil, editor
        ttk.Label(parent, text=self.TITLE, font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.frames = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.frames.items():
            self.book.add(f, text=n)
        self.refreshers: dict[str, Callable[[], None]] = {}
        start = state.get("tab") if state.get("tab") in self.TABS else self.TABS[0]
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── tabs ─────────────────────────────────────────────────────────

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self.refreshers:
            self.refreshers[name] = getattr(self, f"_tab_{slug(name)}")(self.frames[name])
        self._run(name)

    def _run(self, name: str) -> None:
        try:
            self.refreshers[name]()
        except ERRORS as e:
            self.err(name, e)

    def refresh_all(self) -> None:
        for name in list(self.refreshers):
            self._run(name)

    def show_tab(self, name: str) -> None:
        self.book.select(self.TABS.index(name))

    # ── messages ─────────────────────────────────────────────────────

    def top(self):
        return self.parent.winfo_toplevel()

    def err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self.top())

    def info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self.top())

    def ask(self, title: str, text: str) -> bool:
        return bool(messagebox.askyesno(title, text, parent=self.top()))

    def text(self, title: str, text: str, save_name: str | None = None) -> None:
        W.text_window(self.parent, title, text, save_name=save_name)

    # ── building blocks ──────────────────────────────────────────────

    def bar(self, tab, pady=(0, 4)) -> ttk.Frame:
        b = ttk.Frame(tab)
        b.pack(fill="x", pady=pady)
        return b

    def button(self, bar, text: str, command, editor_only: bool = False,
               allowed: bool | None = None) -> ttk.Button:
        def run() -> None:
            try:
                command()
            except ERRORS as e:
                self.err(text.rstrip("…"), e)
        b = ttk.Button(bar, text=text, command=run)
        ok = allowed if allowed is not None else (self.editor or not editor_only)
        if not ok:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def buttons(self, bar, specs) -> None:
        for spec in specs:
            self.button(bar, *spec)

    def combo(self, bar, label: str, key: str, values, refresh, width: int = 12,
              default: str = "") -> tk.StringVar:
        var = tk.StringVar(value=self.state.get(key, default))
        ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
        cb = ttk.Combobox(bar, textvariable=var, values=list(values), state="readonly",
                          width=width)
        cb.pack(side="left", padx=(0, 6))

        def chosen(_e=None) -> None:
            self.state[key] = var.get()
            refresh()
        cb.bind("<<ComboboxSelected>>", chosen)
        return var

    def check(self, bar, label: str, key: str, refresh) -> tk.BooleanVar:
        var = tk.BooleanVar(value=bool(self.state.get(key, False)))

        def toggled() -> None:
            self.state[key] = var.get()
            refresh()
        ttk.Checkbutton(bar, text=label, variable=var, command=toggled).pack(
            side="left", padx=(0, 6))
        return var

    def entry(self, bar, label: str, key: str, refresh, width: int = 16) -> tk.StringVar:
        var = tk.StringVar(value=self.state.get(key, ""))
        ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
        e = ttk.Entry(bar, textvariable=var, width=width)
        e.pack(side="left", padx=(0, 6))

        def go(_e=None) -> None:
            self.state[key] = var.get()
            refresh()
        e.bind("<Return>", go)
        return var

    def note(self, tab, text: str) -> None:
        ttk.Label(tab, text=text, foreground="#555", wraplength=900, justify="left").pack(
            anchor="w", pady=(0, 4))

    def heading(self, tab, text: str) -> None:
        ttk.Label(tab, text=text, font=("", 11, "bold")).pack(anchor="w", pady=(8, 2))

    def form(self, title: str, fields: list, on_save: Callable[[dict], Any],
             note: str | None = None, owner=None) -> None:
        def save(v: dict) -> None:
            on_save(v)
            self.refresh_all()
        W.form_dialog(owner or self.parent, title, fields, save, note)

    def pick(self, table: Table, title: str) -> Any:
        x = table.selected()
        if x is None:
            self.info(title, "Select a row first.")
        return x

    def open_selected(self, table: Table) -> None:
        x = table.selected()
        pid = (x.get("pupil_id") if isinstance(x, dict) else getattr(x, "pupil_id", None)) \
            if x is not None else None
        if pid and self.open_pupil:
            self.open_pupil(pid)
        elif x is None:
            self.info("Open pupil", "Select a row first.")

    def save_csv(self, name: str, fn: Callable[[str], int], what: str = "row") -> None:
        path = filedialog.asksaveasfilename(parent=self.top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")], initialfile=name)
        if not path:
            return
        try:
            n = fn(path)
        except ERRORS as e:
            self.err("Export", e)
            return
        self.info("Export", f"Exported {n} {what}(s).")

    def deliver(self, title: str, res: dict[str, Any]) -> None:
        """Send a letter the domain saved in the outbox, off the Tk thread."""
        if not res.get("message_id"):
            self.info(title, "No contact with parental responsibility has an e-mail address. "
                             "Contact the family another way.")
            return
        text = f"{res['emails']} e-mail(s) prepared."
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self.info(title, text + (f"\n\nQueued - delivery failed: {error}" if error
                                         else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def history_text(self, rows: list[dict[str, Any]]) -> str:
        return "\n".join(
            f"{h['at']}  {h['actor']:<14} {h.get('item', ''):<11} {h['action']:<12} "
            + ", ".join(f"{k}={v}" for k, v in (h.get("detail") or {}).items())
            for h in rows) or "No changes recorded."

    def counts(self, d: dict[str, Any]) -> str:
        return ", ".join(f"{k} {v}" for k, v in d.items()) or "-"
