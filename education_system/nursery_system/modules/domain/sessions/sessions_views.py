"""Tkinter views for Sessions & Bookings (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). A four-tab notebook — the resolved day view, the contracted weekly
patterns, ad-hoc extras / cancellations, and closures — the GUI counterpart of
``sessions_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.sessions import sessions as data
from education_system.nursery_system.modules.domain.sessions.sessions import (
    BOOKING_KINDS,
    BOOKING_STATUSES,
    CLOSURE_TYPES,
    FUNDING_TYPES,
    PATTERN_STATUSES,
    SESSION_TYPES,
    WEEKDAYS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent)
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _pupil_choices() -> list[tuple[str, str]]:
    try:
        return data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


def _room_choices() -> list[str]:
    try:
        return data.list_room_choices()
    except Exception:
        logger.exception("Could not load room choices")
        return []


def _tree(parent: ttk.Frame, spec: list[tuple[str, str, int]],
          height: int = 12) -> ttk.Treeview:
    cols = tuple(c for c, _l, _w in spec)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, label, w in spec:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("alert", foreground="#c0392b")
    tree.tag_configure("muted", foreground="#7f8c8d")
    tree.pack(fill="both", expand=True)
    return tree


# ── Generic form dialog ──────────────────────────────────────────────────────
# Each field is (key, label, kind, choices). ``kind`` is entry / choice / bool /
# pupil — ``pupil`` renders the child picker and maps back to ``pupil_id``.

def _form_dialog(host, title: str, fields: list[tuple[str, str, str, Any]], *,
                 initial: dict[str, Any] | None = None,
                 geometry: str = "460x520") -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry(geometry)
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    pupil_by_label: dict[str, str] = {}
    row = 0

    for key, label, kind, choices in fields:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        cur = initial.get(key)
        if kind == "pupil":
            pupil_by_label = {lbl: pid for pid, lbl in (choices or [])}
            v = tk.StringVar()
            ttk.Combobox(frm, textvariable=v,
                         values=[lbl for _p, lbl in (choices or [])],
                         state="readonly" if choices else "normal",
                         width=34).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "choice":
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Combobox(frm, textvariable=v, values=list(choices or []),
                         width=32).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "bool":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, variable=v).grid(row=row, column=1, sticky="w",
                                                  pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for (key, _l, kind, _c) in fields:
            v = vars_[key]
            if kind == "pupil":
                out["pupil_id"] = pupil_by_label.get(
                    (str(v.get()) or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[key] = bool(v.get())
            else:
                out[key] = (str(v.get()) or "").strip()
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _selected(tree: ttk.Treeview, host, what: str, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Sessions & Bookings",
                            f"Select {what} to {verb}.", parent=host.root)
        return None
    return sel


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host, day: str | None = None) -> None:
    logger.debug("GUI: sessions open_manager")
    root = _clear(host)
    _header(root, "Sessions & Bookings")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    day_tab = ttk.Frame(nb, padding=8)
    pattern_tab = ttk.Frame(nb, padding=8)
    booking_tab = ttk.Frame(nb, padding=8)
    closure_tab = ttk.Frame(nb, padding=8)
    nb.add(day_tab, text="Day View")
    nb.add(pattern_tab, text="Weekly Patterns")
    nb.add(booking_tab, text="Extras & Cancellations")
    nb.add(closure_tab, text="Closures & Holidays")

    _build_day_tab(host, day_tab, day or data._today())
    _build_pattern_tab(host, pattern_tab)
    _build_booking_tab(host, booking_tab)
    _build_closure_tab(host, closure_tab)

    host.status_var.set("Sessions & bookings loaded")


# ── Day view tab ─────────────────────────────────────────────────────────────

def _build_day_tab(host, parent: ttk.Frame, day: str) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Date (YYYY-MM-DD):").pack(side="left")
    date_var = tk.StringVar(value=day)
    ttk.Entry(bar, textvariable=date_var, width=14).pack(side="left", padx=6)
    ttk.Button(bar, text="Show",
               command=lambda: _refresh_day(date_var.get(), summary, tree,
                                            cap_tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Today",
               command=lambda: (date_var.set(data._today()),
                                _refresh_day(date_var.get(), summary, tree,
                                             cap_tree))).pack(side="left", padx=2)

    summary = ttk.Label(parent, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("child", "Child", 200), ("session", "Session", 90),
        ("times", "Times", 130), ("room", "Room", 150),
        ("source", "Source", 110), ("funding", "Funding", 90),
    ], height=11)

    ttk.Label(parent, text="Room capacity", font=("", 11, "bold")).pack(
        anchor="w", pady=(10, 2))
    cap_tree = _tree(parent, [
        ("room", "Room", 200), ("booked", "Booked", 90),
        ("capacity", "Capacity", 90), ("free", "Free", 90),
        ("flag", "", 160),
    ], height=5)

    _refresh_day(day, summary, tree, cap_tree)


def _refresh_day(day: str, summary: ttk.Label, tree: ttk.Treeview,
                 cap_tree: ttk.Treeview) -> None:
    for t in (tree, cap_tree):
        for i in t.get_children():
            t.delete(i)
    try:
        s = data.summary(day)
        sessions = data.day_sessions(s["date"])
        rooms = data.room_day_capacity(s["date"])
    except ValidationError as e:
        summary.config(text=str(e), foreground="#a00")
        return
    except Exception:
        logger.exception("Could not load day sessions")
        summary.config(text="Could not load — see logs.", foreground="#a00")
        return

    if s["closed"]:
        summary.config(
            text=f"{s['date']} — SETTING CLOSED ({', '.join(s['closure_names'])})",
            foreground="#c0392b")
    else:
        summary.config(
            text=f"{s['date']} — {s['booked_children']} children, "
                 f"{s['booked_sessions']} sessions, {s['extras']} extra, "
                 f"{s['cancellations']} cancelled, {s['booked_hours']} hours",
            foreground="#c0392b" if s["over_capacity_rooms"] else "#555")

    for i, x in enumerate(sessions):
        tree.insert("", "end", iid=f"{x.source_id}-{i}",
                    tags=("muted",) if x.source == "extra" else (),
                    values=(x.child_name or x.pupil_id, x.session_type,
                            f"{x.start_time or '-'}–{x.end_time or '-'}",
                            x.room or "-", x.source, x.funding or "-"))
    for r in rooms:
        cap_tree.insert("", "end", iid=r.room,
                        tags=("alert",) if r.over_capacity else (),
                        values=(r.room, r.booked, r.capacity or "-",
                                r.free if r.capacity else "-",
                                "OVER CAPACITY" if r.over_capacity else ""))


# ── Weekly patterns tab ──────────────────────────────────────────────────────

_PATTERN_FIELDS: list[tuple[str, str, str, Any]] = [
    ("weekday",      "Weekday",                 "choice", WEEKDAYS),
    ("session_type", "Session",                 "choice", SESSION_TYPES),
    ("start_time",   "Start time (HH:MM)",      "entry",  None),
    ("end_time",     "End time (HH:MM)",        "entry",  None),
    ("room",         "Room",                    "choice", None),
    ("funding",      "Funding",                 "choice", FUNDING_TYPES),
    ("start_date",   "Start date (YYYY-MM-DD)", "entry",  None),
    ("end_date",     "End date (optional)",     "entry",  None),
    ("status",       "Status",                  "choice", PATTERN_STATUSES),
    ("notes",        "Notes",                   "entry",  None),
]


def _pattern_fields(*, with_pupil: bool) -> list[tuple[str, str, str, Any]]:
    fields = [(k, lb, kd, _room_choices() if k == "room" else ch)
              for k, lb, kd, ch in _PATTERN_FIELDS]
    if with_pupil:
        fields.insert(0, ("pupil_id", "Child", "pupil", _pupil_choices()))
    return fields


def _build_pattern_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Contracted Session",
               command=lambda: _add_pattern(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_pattern(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="End",
               command=lambda: _end_pattern(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_pattern(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_patterns(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("child", "Child", 180), ("day", "Weekday", 100),
        ("session", "Session", 80), ("times", "Times", 120),
        ("room", "Room", 130), ("funding", "Funding", 80),
        ("from", "From", 100), ("to", "To", 100), ("status", "Status", 80),
    ], height=16)
    tree.bind("<Double-1>", lambda _e: _edit_pattern(host, tree))
    _refresh_patterns(tree)


def _refresh_patterns(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_patterns()
    except Exception:
        logger.exception("Could not refresh booking patterns")
        return
    for p in rows:
        tree.insert("", "end", iid=p.pattern_id,
                    tags=("muted",) if p.status == "ended" else (),
                    values=(p.pattern_id, p.child_name or p.pupil_id,
                            p.weekday_name, p.session_type,
                            f"{p.start_time or '-'}–{p.end_time or '-'}",
                            p.room or "-", p.funding, p.start_date,
                            p.end_date or "-", p.status))


@_safe_view
def _add_pattern(host) -> None:
    fields = _form_dialog(host, "Add Contracted Session",
                          _pattern_fields(with_pupil=True),
                          initial={"session_type": "all-day",
                                   "funding": "funded", "status": "active",
                                   "start_date": data._today()})
    if not fields:
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add session", "Please choose a child.",
                             parent=host.root)
        return
    try:
        p = data.create_pattern(fields)
    except ValidationError as e:
        messagebox.showerror("Add session", str(e), parent=host.root)
        return
    host.status_var.set(f"Added contracted session {p.pattern_id}")
    open_manager(host)


@_safe_view
def _edit_pattern(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a pattern", "edit")
    if not sel:
        return
    p = data.get_pattern(sel)
    if p is None:
        return
    initial = {k: getattr(p, k) for k, _l, _kd, _c in _PATTERN_FIELDS}
    initial["weekday"] = p.weekday_name
    fields = _form_dialog(host, f"Edit session — {p.child_name or p.pupil_id}",
                          _pattern_fields(with_pupil=False), initial=initial)
    if not fields:
        return
    try:
        data.update_pattern(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Edit session", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated contracted session {sel}")
    open_manager(host)


@_safe_view
def _end_pattern(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a pattern", "end")
    if not sel:
        return
    if not messagebox.askyesno(
            "End contracted session",
            f"End pattern {sel} today? It stops appearing in the day view "
            "from tomorrow.", parent=host.root):
        return
    try:
        data.end_pattern(sel)
    except ValidationError as e:
        messagebox.showerror("End session", str(e), parent=host.root)
        return
    host.status_var.set(f"Ended contracted session {sel}")
    open_manager(host)


@_safe_view
def _delete_pattern(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a pattern", "delete")
    if not sel:
        return
    if not messagebox.askyesno("Delete pattern", f"Delete pattern {sel}?",
                               parent=host.root):
        return
    data.delete_pattern(sel)
    host.status_var.set(f"Deleted pattern {sel}")
    open_manager(host)


# ── Extras & cancellations tab ───────────────────────────────────────────────

_BOOKING_FIELDS: list[tuple[str, str, str, Any]] = [
    ("session_date", "Date (YYYY-MM-DD)",   "entry",  None),
    ("session_type", "Session",             "choice", SESSION_TYPES),
    ("kind",         "Kind",                "choice", BOOKING_KINDS),
    ("start_time",   "Start time (HH:MM)",  "entry",  None),
    ("end_time",     "End time (HH:MM)",    "entry",  None),
    ("room",         "Room",                "choice", None),
    ("chargeable",   "Chargeable",          "bool",   None),
    ("notice_days",  "Notice given (days)", "entry",  None),
    ("reason",       "Reason",              "entry",  None),
    ("status",       "Status",              "choice", BOOKING_STATUSES),
    ("notes",        "Notes",               "entry",  None),
]


def _booking_fields(*, with_pupil: bool) -> list[tuple[str, str, str, Any]]:
    fields = [(k, lb, kd, _room_choices() if k == "room" else ch)
              for k, lb, kd, ch in _BOOKING_FIELDS]
    if with_pupil:
        fields.insert(0, ("pupil_id", "Child", "pupil", _pupil_choices()))
    return fields


def _build_booking_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Extra / Cancellation",
               command=lambda: _add_booking(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_booking(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_booking(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_bookings(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("child", "Child", 190), ("date", "Date", 100),
        ("session", "Session", 80), ("kind", "Kind", 110),
        ("charge", "Chargeable", 90), ("status", "Status", 90),
        ("reason", "Reason", 200),
    ], height=16)
    tree.bind("<Double-1>", lambda _e: _edit_booking(host, tree))
    _refresh_bookings(tree)


def _refresh_bookings(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_bookings()
    except Exception:
        logger.exception("Could not refresh session bookings")
        return
    for b in rows:
        tree.insert("", "end", iid=b.booking_id,
                    tags=("muted",) if b.kind == "cancellation" else (),
                    values=(b.booking_id, b.child_name or b.pupil_id,
                            b.session_date, b.session_type, b.kind,
                            "Yes" if b.chargeable else "No", b.status,
                            b.reason or "-"))


@_safe_view
def _add_booking(host) -> None:
    fields = _form_dialog(host, "Add Extra Session / Cancellation",
                          _booking_fields(with_pupil=True),
                          initial={"session_date": data._today(),
                                   "session_type": "all-day", "kind": "extra",
                                   "chargeable": True, "status": "confirmed"})
    if not fields:
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add booking", "Please choose a child.",
                             parent=host.root)
        return
    try:
        b = data.create_booking(fields)
    except ValidationError as e:
        messagebox.showerror("Add booking", str(e), parent=host.root)
        return
    host.status_var.set(f"Logged {b.kind} {b.booking_id}")
    open_manager(host)


@_safe_view
def _edit_booking(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a booking", "edit")
    if not sel:
        return
    b = data.get_booking(sel)
    if b is None:
        return
    initial = {k: getattr(b, k) for k, _l, _kd, _c in _BOOKING_FIELDS}
    fields = _form_dialog(host, f"Edit booking — {b.child_name or b.pupil_id}",
                          _booking_fields(with_pupil=False), initial=initial)
    if not fields:
        return
    try:
        data.update_booking(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Edit booking", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated booking {sel}")
    open_manager(host)


@_safe_view
def _delete_booking(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a booking", "delete")
    if not sel:
        return
    if not messagebox.askyesno("Delete booking", f"Delete booking {sel}?",
                               parent=host.root):
        return
    data.delete_booking(sel)
    host.status_var.set(f"Deleted booking {sel}")
    open_manager(host)


# ── Closures tab ─────────────────────────────────────────────────────────────

_CLOSURE_FIELDS: list[tuple[str, str, str, Any]] = [
    ("name",         "Name",                        "entry",  None),
    ("start_date",   "First closed day (YYYY-MM-DD)", "entry", None),
    ("end_date",     "Last closed day",             "entry",  None),
    ("closure_type", "Type",                        "choice", CLOSURE_TYPES),
    ("room",         "Room (blank = whole setting)", "choice", None),
    ("chargeable",   "Still charged to parents",    "bool",   None),
    ("notes",        "Notes",                       "entry",  None),
]


def _closure_fields() -> list[tuple[str, str, str, Any]]:
    return [(k, lb, kd, [""] + _room_choices() if k == "room" else ch)
            for k, lb, kd, ch in _CLOSURE_FIELDS]


def _build_closure_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Closure",
               command=lambda: _add_closure(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_closure(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_closure(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_closures(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("name", "Name", 220), ("from", "From", 110),
        ("to", "To", 110), ("type", "Type", 120), ("scope", "Scope", 160),
        ("charge", "Charged", 90),
    ], height=16)
    tree.bind("<Double-1>", lambda _e: _edit_closure(host, tree))
    _refresh_closures(tree)


def _refresh_closures(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_closures()
    except Exception:
        logger.exception("Could not refresh closures")
        return
    today = data._today()
    for c in rows:
        tree.insert("", "end", iid=c.closure_id,
                    tags=("muted",) if c.end_date < today else (),
                    values=(c.closure_id, c.name, c.start_date, c.end_date,
                            c.closure_type, c.room or "whole setting",
                            "Yes" if c.chargeable else "No"))


@_safe_view
def _add_closure(host) -> None:
    fields = _form_dialog(host, "Add Closure", _closure_fields(),
                          initial={"closure_type": "holiday"},
                          geometry="460x400")
    if not fields:
        return
    try:
        c = data.create_closure(fields)
    except ValidationError as e:
        messagebox.showerror("Add closure", str(e), parent=host.root)
        return
    host.status_var.set(f"Added closure {c.closure_id}")
    open_manager(host)


@_safe_view
def _edit_closure(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a closure", "edit")
    if not sel:
        return
    c = data.get_closure(sel)
    if c is None:
        return
    initial = {k: getattr(c, k) for k, _l, _kd, _ch in _CLOSURE_FIELDS}
    fields = _form_dialog(host, f"Edit closure — {c.name}", _closure_fields(),
                          initial=initial, geometry="460x400")
    if not fields:
        return
    try:
        data.update_closure(sel, fields)
    except ValidationError as e:
        messagebox.showerror("Edit closure", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated closure {sel}")
    open_manager(host)


@_safe_view
def _delete_closure(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a closure", "delete")
    if not sel:
        return
    if not messagebox.askyesno("Delete closure", f"Delete closure {sel}?",
                               parent=host.root):
        return
    data.delete_closure(sel)
    host.status_var.set(f"Deleted closure {sel}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Sessions & Bookings", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Sessions & Bookings from the navigation menu."
              ).pack(anchor="w")
    return frame
