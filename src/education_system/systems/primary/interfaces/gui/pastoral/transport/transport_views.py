"""Tkinter views for Primary School Transport."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.primary.domain.pastoral.transport import (
    transport as data,
)
from education_system.systems.primary.domain.pastoral.transport.transport import (
    ARRANGEMENT_STATUSES,
    Arrangement,
    DAYS,
    DEFAULT_ARRANGEMENT_STATUS,
    DEFAULT_FEE_STATUS,
    DEFAULT_MODE,
    DEFAULT_ROUTE_STATUS,
    DEFAULT_ROUTE_TYPE,
    FEE_STATUSES,
    MODES,
    ROUTE_STATUSES,
    ROUTE_TYPES,
    Route,
    ValidationError,
)
from education_system.systems.primary.domain import _pupils_bridge as student_data
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_ROUTE_TAGS = {
    "Active":    ("#e6f7e6", "#0d6b2a"),
    "Suspended": ("#fff0d6", "#7a5800"),
    "Withdrawn": ("#dddddd", "#444444"),
}
_ARR_TAGS = {
    "Active":    ("#e6f7e6", "#0d6b2a"),
    "Pending":   ("#fff7e6", "#7a5800"),
    "Suspended": ("#fff0d6", "#7a5800"),
    "Cancelled": ("#ffd1d1", "#8c0d0d"),
    "Ended":     ("#eeeeee", "#444444"),
}


def open_transport_window(parent=None) -> None:
    data.init_db()
    if parent is None:
        win = tk.Tk()
        win.title(f"Transport — {branding.SYSTEM_NAME}")
        win.geometry(WIN_GEOMETRY)
        win.minsize(*WIN_MINSIZE)
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        _draw_transport(frame)
        return
    kit.show_page(parent, "Transport", _draw_transport)


def _draw_transport(page) -> None:
    kit.page_heading(page, "Transport",
                     "Routes, pupils' transport arrangements, fees and passes")
    nb = ttk.Notebook(page)
    nb.pack(fill="both", expand=True)

    RoutesTab(nb)
    ArrangementsTab(nb, scope="active",  label="Active")
    ArrangementsTab(nb, scope="unpaid",  label="Unpaid / Partial")
    ArrangementsTab(nb, scope="bursary", label="LA Funded")
    ArrangementsTab(nb, scope="expired", label="Pass Expired")
    ArrangementsTab(nb, scope="all",     label="All Arrangements")
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _route_options() -> list[tuple[int | None, str]]:
    routes = data.list_routes()
    opts: list[tuple[int | None, str]] = [(None, "(none)")]
    for r in routes:
        opts.append((r.route_id,
                       f"#{r.route_id} — {r.route_name}"))
    return opts


def _operator_names() -> list[str]:
    """Operators already on a route (the field is free text, so the
    drop-down stays editable for a new one)."""
    try:
        return sorted({r.operator for r in data.list_routes() if r.operator})
    except Exception:  # noqa: BLE001 - suggestions only
        logger.debug("operator list failed", exc_info=True)
        return []


# ── Days tick boxes ──────────────────────────────────────────

_SHORT = [d[:3] for d in DAYS]          # Mon … Sun
_WEEKDAYS = _SHORT[:5]


def _parse_days(text: str) -> list[str] | None:
    """Short day names in *text* ("Mon-Fri", "Mon, Wed, Fri",
    "Monday Tuesday"…), or None when it is not a list of days (an old
    free-text value such as "Term time only")."""
    t = (text or "").strip()
    if not t:
        return []
    picked: set[str] = set()
    for part in t.replace(";", ",").replace("/", ",").split(","):
        part = part.strip()
        if not part:
            continue
        rng = [x.strip() for x in part.replace("–", "-").split("-")]
        if len(rng) == 2 and all(x[:3].title() in _SHORT for x in rng):
            a, b = (_SHORT.index(x[:3].title()) for x in rng)
            if a <= b:
                picked.update(_SHORT[a:b + 1])
                continue
            return None
        for word in part.split():
            w = word.rstrip(".").title()
            if w in _SHORT or w in DAYS:
                picked.add(w[:3])
            else:
                return None
    return [d for d in _SHORT if d in picked]


def _format_days(days: list[str]) -> str:
    """"Mon-Fri" for the school week (as the old default), a range for any
    other unbroken run of 3+ days, otherwise "Mon, Wed, Fri"."""
    if not days:
        return ""
    idx = [_SHORT.index(d) for d in days]
    if len(idx) >= 3 and idx == list(range(idx[0], idx[-1] + 1)):
        return f"{_SHORT[idx[0]]}-{_SHORT[idx[-1]]}"
    return ", ".join(days)


class _DaysField(ttk.Frame):
    """A tick box per weekday (from the domain's DAYS) bound to the
    ``days`` StringVar, which keeps the text form the domain stores
    ("Mon-Fri", "Mon, Wed, Fri"). A stored value that is not a list of
    days is kept as it is until a box is ticked."""

    def __init__(self, master, textvariable: tk.StringVar) -> None:
        super().__init__(master)
        self.var = textvariable
        self._syncing = False
        self.boxes: dict[str, tk.BooleanVar] = {}
        for d in _SHORT:
            bv = tk.BooleanVar(value=False)
            self.boxes[d] = bv
            ttk.Checkbutton(self, text=d, variable=bv,
                            command=self._picked).pack(side="left")
        ttk.Button(self, text="Mon–Fri", width=8,
                   command=self._weekdays).pack(side="left", padx=(6, 0))
        self.note = ttk.Label(self, text="", foreground="#7a5800")
        self.note.pack(side="left", padx=(6, 0))
        self._trace = self.var.trace_add("write", lambda *_: self._show())
        self._show()

    def _weekdays(self) -> None:
        for d, bv in self.boxes.items():
            bv.set(d in _WEEKDAYS)
        self._picked()

    def _picked(self) -> None:
        chosen = [d for d in _SHORT if self.boxes[d].get()]
        self._syncing = True
        try:
            self.var.set(_format_days(chosen))
        finally:
            self._syncing = False
        self.note.config(text="")

    def _show(self) -> None:
        if self._syncing:
            return
        parsed = _parse_days(self.var.get())
        for d, bv in self.boxes.items():
            bv.set(bool(parsed) and d in parsed)
        self.note.config(text="" if parsed is not None
                         else f"(kept: {self.var.get()!r})")

    def destroy(self) -> None:
        try:
            self.var.trace_remove("write", self._trace)
        except (tk.TclError, ValueError):
            pass
        super().destroy()


# ── Routes tab ───────────────────────────────────────────────

class RoutesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Routes")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + ROUTE_TYPES,
                                     state="readonly", width=14)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + ROUTE_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Operator:").pack(side="left")
        self.f_op = tk.StringVar()
        kit.ChoiceField(bar, self.f_op, choices=_operator_names(), blank=True,
                        editable=True, width=16).pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=14)
        self.f_name.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "type", "operator", "days",
                "am", "pm", "cost_term", "cost_year",
                "seats", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "name": 220, "type": 110,
                   "operator": 140, "days": 90, "am": 60,
                   "pm": 60, "cost_term": 90, "cost_year": 90,
                   "seats": 90, "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "seats")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _ROUTE_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",          self._edit),
                ("Change status", self._set_status),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["route_type"] = self.f_type.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_op.get().strip():
            f["operator_like"] = self.f_op.get().strip()
        if self.f_name.get().strip():
            f["name_like"] = self.f_name.get().strip()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_routes(**self._filters())
        for r in rows:
            seats_used = data.route_seats_used(r.route_id)
            seats = (f"{seats_used}/{r.capacity}"
                      if r.capacity is not None
                      else str(seats_used))
            self.tree.insert(
                "", "end", iid=str(r.route_id),
                values=(r.route_id, r.route_name, r.route_type,
                         r.operator or "—", r.days,
                         r.am_pickup_time or "—",
                         r.pm_return_time or "—",
                         (f"£{r.cost_per_term:.0f}"
                            if r.cost_per_term is not None
                            else "—"),
                         (f"£{r.cost_per_year:.0f}"
                            if r.cost_per_year is not None
                            else "—"),
                         seats, r.status),
                tags=(r.status,))
        self.count.config(text=f"{len(rows)} route(s)")

    def _selected(self) -> Route | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Transport",
                                  "Select a route first.",
                                  parent=self.frame)
            return None
        return data.get_route(int(sel[0]))

    def _new(self) -> None:
        if RouteEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        r = self._selected()
        if r and RouteEditor(self.frame,
                                  route=r).result is not None:
            self.refresh()

    def _set_status(self) -> None:
        r = self._selected()
        if not r:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(ROUTE_STATUSES),
                                default=r.status)
        if not new:
            return
        try:
            data.set_route_status(r.route_id, new)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        r = self._selected()
        if not r:
            return
        if not messagebox.askyesno(
                "Transport", f"Delete route #{r.route_id}?",
                parent=self.frame):
            return
        data.delete_route(r.route_id)
        self.refresh()


# ── Arrangements tabs ────────────────────────────────────────

class ArrangementsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Pupil:").pack(side="left")
        self.f_student = tk.StringVar()
        kit.PupilPicker(bar, self.f_student, include_off_roll=True, width=34,
                        on_change=lambda _v: self.refresh()).pack(
            side="left", padx=(2, 8))
        ttk.Label(bar, text="Mode:").pack(side="left")
        self.f_mode = ttk.Combobox(bar, values=("",) + MODES,
                                     state="readonly", width=14)
        self.f_mode.current(0)
        self.f_mode.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + ARRANGEMENT_STATUSES,
                                           state="readonly", width=12)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Fee:").pack(side="left")
        self.f_fee = ttk.Combobox(bar, values=("",) + FEE_STATUSES,
                                    state="readonly", width=14)
        self.f_fee.current(0)
        self.f_fee.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "mode", "route", "days",
                "start", "end", "fee", "amount", "flags",
                "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "student": 100, "mode": 130,
                   "route": 200, "days": 90, "start": 90,
                   "end": 90, "fee": 130, "amount": 80,
                   "flags": 90, "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "amount")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _ARR_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("expired", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("unpaid", background="#ffe6cc",
                                  foreground="#a04400")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",         self._edit),
                ("Activate",     self._activate),
                ("Suspend",      self._suspend),
                ("End",          self._end),
                ("Cancel",       self._cancel),
                ("Fee status",   self._set_fee),
                ("Change status", self._set_status),
                ("Delete",       self._delete),
                ("Refresh",      self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        if self.f_mode.get():
            f["mode"] = self.f_mode.get()
        if self.f_fee.get():
            f["fee_status"] = self.f_fee.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "unpaid":
            f["unpaid_only"] = True
        elif self.scope == "bursary":
            f["bursary_only"] = True
        elif self.scope == "expired":
            f["pass_expired"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_arrangements(**self._filters())
        for a in rows:
            flags = []
            if a.bursary_supported:
                flags.append("BURS")
            if a.pass_expired:
                flags.append("EXP")
            if a.pass_expired:
                tag = "expired"
            elif a.is_overdue_unpaid:
                tag = "unpaid"
            else:
                tag = a.status
            amt = (f"£{a.fee_amount:.0f}"
                    if a.fee_amount is not None else "—")
            self.tree.insert(
                "", "end", iid=str(a.arrangement_id),
                values=(a.arrangement_id, a.student_id,
                         a.mode, a.route_name_cache or "—",
                         a.days, a.start_date,
                         a.end_date or "—", a.fee_status,
                         amt, ",".join(flags), a.status),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} arrangement(s)")

    def _selected(self) -> Arrangement | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Transport",
                                  "Select an arrangement first.",
                                  parent=self.frame)
            return None
        return data.get_arrangement(int(sel[0]))

    def _new(self) -> None:
        if ArrangementEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and ArrangementEditor(
                self.frame, arrangement=a).result is not None:
            self.refresh()

    def _activate(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.activate(a.arrangement_id)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _suspend(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.suspend(a.arrangement_id)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _end(self) -> None:
        a = self._selected()
        if not a:
            return
        when = _prompt_date(self.frame, "End date",
                              initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.end_arrangement(a.arrangement_id,
                                       end_date=when)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _cancel(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.cancel(a.arrangement_id)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_fee(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New fee status",
                                list(FEE_STATUSES),
                                default=a.fee_status)
        if not new:
            return
        try:
            data.set_fee_status(a.arrangement_id, new)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(ARRANGEMENT_STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_arrangement_status(a.arrangement_id, new)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Transport",
                f"Delete arrangement #{a.arrangement_id}?",
                parent=self.frame):
            return
        data.delete_arrangement(a.arrangement_id)
        self.refresh()


class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Student")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Pupil:").pack(side="left")
        self.student_var = tk.StringVar()
        kit.PupilPicker(bar, self.student_var, include_off_roll=True,
                        on_change=lambda _v: self._show()).pack(
            side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        sid = self.student_var.get().strip()
        if not sid:
            return
        rows = data.arrangements_for_student(sid)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"Transport history for {sid}\n"
                            f"{'=' * 60}\n\n"
                            f"Total arrangements: "
                            f"{len(rows)}\n\n")
        for a in rows:
            flags = []
            if a.bursary_supported:
                flags.append("BURS")
            if a.pass_expired:
                flags.append("EXPIRED")
            self.text.insert("end",
                                f"#{a.arrangement_id}  "
                                f"{a.start_date} → "
                                f"{a.end_date or '—'}  "
                                f"{a.mode}  "
                                f"route: {a.route_name_cache or '—'}  "
                                f"[{a.status}]  "
                                f"fee: {a.fee_status}"
                                + (f"  {' '.join(flags)}"
                                    if flags else "") + "\n")
            if a.pickup_point or a.drop_point:
                self.text.insert("end",
                                    f"  {a.pickup_point or '—'}"
                                    f" → "
                                    f"{a.drop_point or '—'}\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Transport Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total routes        : {s.total_routes}\n"
                            f"Active routes       : {s.active_routes}\n"
                            f"Total arrangements  : {s.total_arrangements}\n"
                            f"Active arrangements : {s.active_arrangements}\n"
                            f"Suspended           : {s.suspended}\n"
                            f"Pending             : {s.pending}\n"
                            f"Unpaid / partial    : {s.unpaid_or_partial}\n"
                            f"LA-funded           : {s.bursary_supported}\n"
                            f"Pass expired        : {s.pass_expired}\n"
                            f"Distinct students   : {s.distinct_students}\n\n")
        self.text.insert("end", "By mode:\n")
        for k in MODES:
            n = s.by_mode.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy fee status:\n")
        for k in FEE_STATUSES:
            n = s.by_fee_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in ARRANGEMENT_STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        if s.by_route:
            self.text.insert("end", "\nBy route:\n")
            for k, v in s.by_route.items():
                self.text.insert("end", f"  {k:<28}: {v}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class RouteEditor:
    def __init__(self, parent, *,
                 route: Route | None = None) -> None:
        self.route = route
        self.result: Route | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit route #{route.route_id}"
                          if route else "New route")
        self.win.geometry("820x640")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if route:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body, footer = kit.scrolled_form(self.win)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def picker(row, col, label, key, make, span=1):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            make(v).grid(row=row, column=col + 1, columnspan=span,
                         sticky="w", padx=4, pady=2)

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Route name*", "route_name", width=48)
        combo(1, 0, "Route type*", "route_type", ROUTE_TYPES)
        combo(1, 2, "Status*", "status", ROUTE_STATUSES)
        picker(2, 0, "Operator", "operator",
               lambda v: kit.ChoiceField(body, v, choices=_operator_names(),
                                         blank=True, editable=True, width=22))
        picker(2, 2, "Capacity", "capacity",
               lambda v: kit.NumberField(body, v, from_=0, to=999))
        entry(3, 0, "Contact phone", "contact_phone")
        entry(3, 2, "Contact email", "contact_email")
        picker(4, 0, "Days*", "days", lambda v: _DaysField(body, v), span=3)
        picker(5, 0, "AM pickup", "am_pickup_time",
               lambda v: kit.TimeField(body, v, hours=range(6, 20)))
        picker(5, 2, "PM return", "pm_return_time",
               lambda v: kit.TimeField(body, v, hours=range(6, 20)))
        picker(6, 0, "Cost / term (£)", "cost_per_term",
               lambda v: kit.NumberField(body, v, increment=0.01, to=99999))
        picker(6, 2, "Cost / year (£)", "cost_per_year",
               lambda v: kit.NumberField(body, v, increment=0.01, to=99999))

        row = 7
        for key, label in (
                ("pickup_points", "Pickup points"),
                ("notes",         "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, width=70, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        ttk.Button(footer, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(footer, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["route_type"].set(DEFAULT_ROUTE_TYPE)
        self.vars["status"].set(DEFAULT_ROUTE_STATUS)
        self.vars["days"].set("Mon-Fri")

    def _load(self) -> None:
        r = self.route
        assert r is not None
        for key in ("route_name", "route_type", "status",
                     "operator", "contact_phone",
                     "contact_email", "days",
                     "am_pickup_time", "pm_return_time"):
            self.vars[key].set(getattr(r, key) or "")
        self.vars["cost_per_term"].set(
            str(r.cost_per_term)
            if r.cost_per_term is not None else "")
        self.vars["cost_per_year"].set(
            str(r.cost_per_year)
            if r.cost_per_year is not None else "")
        self.vars["capacity"].set(
            str(r.capacity)
            if r.capacity is not None else "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(r, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.route:
                self.result = data.update_route(
                    self.route.route_id, payload)
            else:
                self.result = data.create_route(payload)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ArrangementEditor:
    def __init__(self, parent, *,
                 arrangement: Arrangement | None = None) -> None:
        self.arrangement = arrangement
        self.result: Arrangement | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit arrangement #{arrangement.arrangement_id}"
            if arrangement else "New arrangement")
        self.win.geometry("860x680")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if arrangement:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body, footer = kit.scrolled_form(self.win)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}
        self.bools: dict[str, tk.BooleanVar] = {}

        ttk.Label(body, text="Pupil*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.student_var = tk.StringVar()
        kit.PupilPicker(body, self.student_var).grid(
            row=0, column=1, columnspan=3, sticky="w", padx=4, pady=2)

        ttk.Label(body, text="Route").grid(
            row=1, column=0, sticky="w", padx=4, pady=2)
        self.route_var = tk.StringVar()
        kit.ChoiceField(
            body, self.route_var,
            choices=[(str(rid), lbl) for rid, lbl in _route_options()
                     if rid is not None],
            blank=True, width=44).grid(
            row=1, column=1, columnspan=3, sticky="w", padx=4, pady=2)

        def picker(row, col, label, key, make, span=1):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            make(v).grid(row=row, column=col + 1, columnspan=span,
                         sticky="w", padx=4, pady=2)

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        combo(2, 0, "Mode*", "mode", MODES)
        combo(2, 2, "Status*", "status", ARRANGEMENT_STATUSES)
        entry(3, 0, "Pickup point", "pickup_point")
        entry(3, 2, "Drop point", "drop_point")
        picker(4, 0, "Days*", "days", lambda v: _DaysField(body, v), span=3)
        picker(5, 0, "Start date*", "start_date", lambda v: kit.DateField(body, v))
        picker(5, 2, "End date", "end_date", lambda v: kit.DateField(body, v))
        combo(6, 0, "Fee status*", "fee_status", FEE_STATUSES)
        picker(6, 2, "Fee amount (£)", "fee_amount",
               lambda v: kit.NumberField(body, v, increment=0.01, to=99999))
        picker(7, 0, "Pass expires", "pass_expires_on",
               lambda v: kit.DateField(body, v))
        entry(7, 2, "Pass number", "pass_number")
        self.bools["bursary_supported"] = tk.BooleanVar()
        ttk.Checkbutton(body, text="LA-funded (free home-to-school transport)",
                         variable=self.bools["bursary_supported"]
                         ).grid(row=8, column=0, columnspan=4,
                                  sticky="w", padx=4, pady=2)
        entry(9, 0, "Emergency contact", "emergency_contact")
        entry(9, 2, "Emergency phone", "emergency_phone")

        row = 10
        for key, label in (
                ("medical_notes", "Medical notes"),
                ("notes",         "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        ttk.Button(footer, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(footer, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["mode"].set(DEFAULT_MODE)
        self.vars["status"].set(DEFAULT_ARRANGEMENT_STATUS)
        self.vars["days"].set("Mon-Fri")
        self.vars["start_date"].set(_dt.date.today().isoformat())
        self.vars["fee_status"].set(DEFAULT_FEE_STATUS)

    def _load(self) -> None:
        a = self.arrangement
        assert a is not None
        self.student_var.set(a.student_id or "")
        self.route_var.set("" if a.route_id is None else str(a.route_id))
        for key in ("mode", "status", "pickup_point",
                     "drop_point", "days", "start_date",
                     "end_date", "fee_status",
                     "pass_number", "pass_expires_on",
                     "emergency_contact", "emergency_phone"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["fee_amount"].set(
            str(a.fee_amount)
            if a.fee_amount is not None else "")
        self.bools["bursary_supported"].set(a.bursary_supported)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        student_id = self.student_var.get().strip()
        if not student_id:
            messagebox.showerror("Transport",
                                    "Pick a pupil.",
                                    parent=self.win)
            return
        rv = self.route_var.get().strip()
        route_id = int(rv) if rv.isdigit() else None
        payload: dict = {
            "student_id": student_id,
            "route_id": route_id,
            "bursary_supported":
                self.bools["bursary_supported"].get(),
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.arrangement:
                self.result = data.update_arrangement(
                    self.arrangement.arrangement_id, payload)
            else:
                self.result = data.create_arrangement(payload)
        except ValidationError as exc:
            messagebox.showerror("Transport", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_date(parent, title: str, *,
                 initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("400x150")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    kit.DateField(win, var).pack(anchor="w", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_transport_window"]
