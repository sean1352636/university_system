"""Tk building blocks for the pastoral record screens.

The pastoral data layers describe their child records with
``domain.pastoral._records.TableSpec``. :class:`RecordTab` turns one
spec plus its list / create / update / delete functions into a notebook
tab (filter bar, action bar, table), and :class:`FormDialog` builds the
add/edit form from the same column list — so the form always matches
what the data layer validates.
"""

from __future__ import annotations

import dataclasses
import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Any, Callable, Iterable, Sequence

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.pastoral._records import Col, TableSpec
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

logger = logging.getLogger(__name__)

#: (heading, value function, width)
Column = tuple[str, Callable[[Any], Any], int]
#: (button label, handler(tab, selected_row_or_None), needs a selected row)
Action = tuple[str, Callable[["RecordTab", Any], None], bool]


# ── Small helpers ─────────────────────────────────────────────────

def student_labels() -> tuple[list[str], dict[str, str]]:
    """(["S1 — Ann Smith", ...], {"S1": "Ann Smith"})."""
    rows = sorted(student_data.list_students(), key=lambda s: s.student_id)
    return ([f"{s.student_id} — {s.full_name}" for s in rows],
            {s.student_id: s.full_name for s in rows})


def _sid_from_label(label: str) -> str:
    return label.split(" — ", 1)[0].strip()


def fmt(v: Any) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v).replace("\n", " ⏎ ")


def show_error(parent: tk.Misc, title: str, exc: BaseException) -> None:
    if isinstance(exc, (ValueError, PermissionError)) \
            or type(exc).__name__ in ("ValidationError", "AccessDenied"):
        # Something the user can put right (bad date, missing field, no
        # permission): a warning, not an error.
        messagebox.showwarning(title, str(exc) or type(exc).__name__,
                               parent=parent)
        return
    logger.exception("%s failed", title, exc_info=exc)
    messagebox.showerror(title, str(exc) or type(exc).__name__,
                         parent=parent)


def ask_text(parent: tk.Misc, title: str, prompt: str,
             initial: str = "") -> str | None:
    return simpledialog.askstring(title, prompt, parent=parent,
                                  initialvalue=initial)


def spec_columns(spec: TableSpec, *, names: dict[str, str] | None = None
                 ) -> list[Column]:
    """Default table columns: id, student (+ name), then listed cols."""
    cols: list[Column] = [("#", lambda r: getattr(r, spec.id_col), 60)]
    for c in spec.cols:
        if not c.listed or c.hidden:
            continue
        if c.kind == "student":
            cols.append(("Student", lambda r, n=c.name: getattr(r, n), 90))
            if names is not None:
                cols.append(("Name", lambda r, n=c.name:
                             names.get(getattr(r, n), "?"), 170))
            continue
        width = {"multiline": 260, "date": 95, "time": 60, "bool": 60,
                 "int": 70, "money": 90}.get(c.kind, 140)
        cols.append((c.label, lambda r, n=c.name: getattr(r, n), width))
    return cols


# ── Form dialog ───────────────────────────────────────────────────

class FormDialog:
    """Modal add/edit form built from spec columns.

    ``result`` is the dict of entered values (strings / bools, the data
    layer validates), or None if cancelled. Only columns the user could
    change are returned on edit.
    """

    def __init__(self, parent: tk.Misc, title: str, cols: Sequence[Col], *,
                 initial: dict[str, Any] | None = None,
                 editing: bool = False,
                 on_save: Callable[[dict[str, Any]], Any] | None = None,
                 intro: str | None = None) -> None:
        self.result: dict[str, Any] | None = None
        self.saved: Any = None
        self._on_save = on_save
        self._cols = [c for c in cols if not c.hidden]
        self._editing = editing
        initial = initial or {}
        self._labels, _ = student_labels() if any(
            c.kind == "student" for c in self._cols) else ([], {})

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        rows = len(self._cols) + sum(2 for c in self._cols
                                     if c.kind == "multiline")
        window_sizing.fit(self.win, f"720x{min(820, 120 + rows * 34)}",
                          (520, 300))
        self.win.transient(parent)
        grab_when_viewable(self.win)

        bar = ttk.Frame(self.win)
        bar.pack(side="bottom", fill="x", padx=12, pady=(4, 10))
        ttk.Button(bar, text="Save", command=self._save).pack(
            side="right", padx=4)
        ttk.Button(bar, text="Cancel", command=self.win.destroy).pack(
            side="right")
        if intro:
            ttk.Label(self.win, text=intro, wraplength=660,
                      justify="left").pack(fill="x", padx=12, pady=(10, 0))

        outer = ttk.Frame(self.win)
        outer.pack(fill="both", expand=True, padx=8, pady=8)
        canvas = tk.Canvas(outer, highlightthickness=0)
        vs = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(
            win_id, width=e.width))
        canvas.configure(yscrollcommand=vs.set)
        canvas.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        body.grid_columnconfigure(1, weight=1)

        self._widgets: dict[str, Any] = {}
        for i, c in enumerate(self._cols):
            label = c.label + (" *" if c.required else "")
            ttk.Label(body, text=label).grid(row=i, column=0, sticky="nw",
                                             padx=4, pady=3)
            w = self._make_widget(body, c, initial.get(c.name))
            w.grid(row=i, column=1, sticky="ew", padx=4, pady=3)
            if editing and c.fixed:
                try:
                    w.configure(state="disabled")
                except tk.TclError:
                    pass
        self.win.wait_window()

    def _make_widget(self, body: tk.Misc, c: Col, value: Any) -> tk.Widget:
        if value is None and not self._editing and c.default is not None:
            value = c.default() if callable(c.default) else c.default
        if c.kind == "multiline":
            t = tk.Text(body, height=4, width=60, wrap="word")
            if value:
                t.insert("1.0", str(value))
            self._widgets[c.name] = t
            return t
        if c.kind == "bool":
            var = tk.BooleanVar(value=bool(value))
            self._widgets[c.name] = var
            return ttk.Checkbutton(body, variable=var)
        if c.kind == "choice":
            values = list(c.choices) if c.required else ["", *c.choices]
            cb = ttk.Combobox(body, values=values, state="readonly")
            cb.set(value or "")
            self._widgets[c.name] = cb
            return cb
        if c.kind == "student":
            cb = ttk.Combobox(body, values=self._labels, state="readonly",
                              width=44)
            if value:
                match = next((lbl for lbl in self._labels
                              if _sid_from_label(lbl) == value), value)
                cb.set(match)
            self._widgets[c.name] = cb
            return cb
        e = ttk.Entry(body, width=40)
        if value not in (None, ""):
            e.insert(0, str(value))
        self._widgets[c.name] = e
        return e

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for c in self._cols:
            if self._editing and c.fixed:
                continue
            w = self._widgets[c.name]
            if c.kind == "multiline":
                out[c.name] = w.get("1.0", "end").rstrip()
            elif c.kind == "bool":
                out[c.name] = bool(w.get())
            elif c.kind == "student":
                out[c.name] = _sid_from_label(w.get()) if w.get() else ""
            else:
                out[c.name] = w.get().strip()
        return out

    def _save(self) -> None:
        vals = self.values()
        if self._on_save is not None:
            try:
                self.saved = self._on_save(vals)
            except Exception as exc:          # shown to the user
                show_error(self.win, "Save", exc)
                return
        self.result = vals
        self.win.destroy()


def ask_form(parent: tk.Misc, title: str, cols: Sequence[Col], *,
             on_save: Callable[[dict[str, Any]], Any],
             initial: dict[str, Any] | None = None,
             editing: bool = False, intro: str | None = None) -> Any:
    """Show a form; return what *on_save* returned, or None."""
    d = FormDialog(parent, title, cols, initial=initial, editing=editing,
                   on_save=on_save, intro=intro)
    return d.saved if d.result is not None else None


# ── Record tab ────────────────────────────────────────────────────

class RecordTab:
    """Filter bar + action bar + table over one record type."""

    def __init__(self, nb: ttk.Notebook, title: str, spec: TableSpec | None,
                 *, load: Callable[[dict[str, Any]], Iterable[Any]],
                 create: Callable[[dict[str, Any]], Any] | None = None,
                 update: Callable[[int, dict[str, Any]], Any] | None = None,
                 delete: Callable[[int], Any] | None = None,
                 columns: Sequence[Column] | None = None,
                 filters: Sequence[Col] = (),
                 actions: Sequence[Action] = (),
                 form_cols: Sequence[Col] | None = None,
                 new_defaults: Callable[["RecordTab"], dict[str, Any] | None]
                 | None = None,
                 row_id: Callable[[Any], Any] | None = None,
                 intro: str | None = None,
                 row_tag: Callable[[Any], str | None] | None = None,
                 tag_colours: dict[str, tuple[str, str]] | None = None,
                 ) -> None:
        self.spec = spec
        self.title = title
        self._load = load
        self._create = create
        self._update = update
        self._delete = delete
        self._form_cols = list(form_cols if form_cols is not None
                               else (spec.cols if spec else ()))
        self._new_defaults = new_defaults
        self._row_id = row_id or (
            (lambda r: getattr(r, spec.id_col)) if spec else (lambda r: id(r)))
        self._row_tag = row_tag
        self.rows: list[Any] = []
        self._by_iid: dict[str, Any] = {}
        _, self.names = student_labels()
        self._columns = list(columns if columns is not None
                             else spec_columns(spec, names=self.names))

        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=title)
        self.parent = self.frame

        if intro:
            ttk.Label(self.frame, text=intro, wraplength=1100,
                      justify="left", foreground="#444").pack(
                fill="x", padx=8, pady=(8, 0))

        self._filter_widgets: dict[str, Any] = {}
        self._filters = list(filters)
        if self._filters:
            fb = ttk.Frame(self.frame)
            fb.pack(fill="x", padx=8, pady=(8, 4))
            labels, _ = student_labels()
            for c in self._filters:
                ttk.Label(fb, text=c.label + ":").pack(side="left")
                if c.kind == "bool":
                    var = tk.BooleanVar(value=bool(c.default))
                    ttk.Checkbutton(fb, variable=var,
                                    command=self.refresh).pack(
                        side="left", padx=(2, 10))
                    self._filter_widgets[c.name] = var
                    continue
                if c.kind in ("choice", "student"):
                    vals = labels if c.kind == "student" else list(c.choices)
                    w = ttk.Combobox(fb, values=["", *vals], state="readonly",
                                     width=28 if c.kind == "student" else 18)
                    w.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
                else:
                    w = ttk.Entry(fb, width=12)
                w.pack(side="left", padx=(2, 10))
                self._filter_widgets[c.name] = w
            ttk.Button(fb, text="Apply", command=self.refresh).pack(
                side="left")

        # Action bar is packed before the expanding table.
        ab = ttk.Frame(self.frame)
        ab.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
        if create is not None:
            ttk.Button(ab, text="New", command=self.new).pack(side="left")
        if update is not None:
            ttk.Button(ab, text="Edit", command=self.edit).pack(
                side="left", padx=4)
        if delete is not None:
            ttk.Button(ab, text="Delete", command=self.remove).pack(
                side="left", padx=4)
        ttk.Button(ab, text="View", command=self.view).pack(
            side="left", padx=4)
        for label, handler, needs_row in actions:
            ttk.Button(ab, text=label,
                       command=lambda h=handler, n=needs_row:
                       self._run_action(h, n)).pack(side="left", padx=4)
        ttk.Button(ab, text="Refresh", command=self.refresh).pack(
            side="right")
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                  anchor="w").pack(side="bottom", fill="x", padx=8)

        tf = ttk.Frame(self.frame)
        tf.pack(fill="both", expand=True, padx=8, pady=4)
        ids = [f"c{i}" for i in range(len(self._columns))]
        self.tree = ttk.Treeview(tf, columns=ids, show="headings",
                                 selectmode="browse")
        for cid, (heading, _fn, width) in zip(ids, self._columns):
            self.tree.heading(cid, text=heading)
            self.tree.column(cid, width=width, anchor="w")
        for tag, (bg, fg) in (tag_colours or {}).items():
            self.tree.tag_configure(tag, background=bg, foreground=fg)
        vs = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: (
            self.edit() if update is not None else self.view()))
        self.refresh()

    # ── data ──
    def filter_values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for c in self._filters:
            w = self._filter_widgets[c.name]
            v = w.get()
            if c.kind == "student" and v:
                v = _sid_from_label(v)
            out[c.name] = v.strip() if isinstance(v, str) else v
        return out

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._by_iid.clear()
        try:
            self.rows = list(self._load(self.filter_values()))
        except Exception as exc:
            self.rows = []
            self.count_var.set("")
            show_error(self.frame, self.title, exc)
            return
        for i, r in enumerate(self.rows):
            vals = []
            for _h, fn, _w in self._columns:
                try:
                    vals.append(fmt(fn(r)))
                except Exception:
                    vals.append("?")
            tag = self._row_tag(r) if self._row_tag else None
            iid = self.tree.insert("", "end", values=vals,
                                   tags=(tag,) if tag else ())
            self._by_iid[iid] = r
        self.count_var.set(f"{len(self.rows)} record(s).")

    def selected(self) -> Any:
        sel = self.tree.selection()
        return self._by_iid.get(sel[0]) if sel else None

    # ── actions ──
    def _run_action(self, handler: Callable[["RecordTab", Any], None],
                    needs_row: bool) -> None:
        row = self.selected()
        if needs_row and row is None:
            messagebox.showinfo(self.title, "Select a row first.",
                                parent=self.frame)
            return
        try:
            handler(self, row)
        except Exception as exc:
            show_error(self.frame, self.title, exc)
            return
        self.refresh()

    def new(self) -> None:
        initial = self._new_defaults(self) if self._new_defaults else {}
        if initial is None:
            return
        saved = ask_form(self.frame, f"New {self.spec.label.lower()}"
                         if self.spec else "New", self._form_cols,
                         initial=initial, on_save=self._create)
        if saved is not None:
            self.refresh()

    def edit(self) -> None:
        row = self.selected()
        if row is None:
            messagebox.showinfo(self.title, "Select a row first.",
                                parent=self.frame)
            return
        initial = dataclasses.asdict(row) if dataclasses.is_dataclass(row) \
            else {}
        rid = self._row_id(row)
        saved = ask_form(self.frame, f"Edit {self.spec.label.lower()} #{rid}"
                         if self.spec else "Edit", self._form_cols,
                         initial=initial, editing=True,
                         on_save=lambda vals: self._update(rid, vals))
        if saved is not None:
            self.refresh()

    def remove(self) -> None:
        row = self.selected()
        if row is None:
            messagebox.showinfo(self.title, "Select a row first.",
                                parent=self.frame)
            return
        rid = self._row_id(row)
        if not messagebox.askyesno(self.title, f"Delete record #{rid}?",
                                   parent=self.frame):
            return
        try:
            self._delete(rid)
        except Exception as exc:
            show_error(self.frame, self.title, exc)
            return
        self.refresh()

    def view(self) -> None:
        row = self.selected()
        if row is None:
            messagebox.showinfo(self.title, "Select a row first.",
                                parent=self.frame)
            return
        show_record(self.frame, f"{self.title} — details", row, self.spec)


def show_record(parent: tk.Misc, title: str, row: Any,
                spec: TableSpec | None = None) -> None:
    """Read-only window listing every field of a record."""
    win = tk.Toplevel(parent)
    win.title(title)
    window_sizing.fit(win, "700x600", (480, 320))
    win.transient(parent)
    ttk.Button(win, text="Close", command=win.destroy).pack(
        side="bottom", pady=8)
    txt = tk.Text(win, wrap="word")
    txt.pack(fill="both", expand=True, padx=10, pady=10)
    labels = {c.name: c.label for c in spec.cols} if spec else {}
    data = dataclasses.asdict(row) if dataclasses.is_dataclass(row) \
        else dict(vars(row))
    for k, v in data.items():
        if isinstance(v, (list, dict)):
            v = ", ".join(map(str, v)) if isinstance(v, list) else v
        txt.insert("end", f"{labels.get(k, k.replace('_', ' ').title())}: ")
        txt.insert("end", f"{'' if v is None else v}\n")
    txt.configure(state="disabled")


def open_records_window(parent: tk.Misc, title: str, spec: TableSpec, **kw
                        ) -> RecordTab:
    """A Toplevel holding one :class:`RecordTab` (child records of the
    row selected in another tab, e.g. a care record's PEP reviews)."""
    win = tk.Toplevel(parent)
    win.title(title)
    window_sizing.fit(win, "1200x700", (900, 500))
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    return RecordTab(nb, kw.pop("tab_title", spec.label + "s"), spec, **kw)
