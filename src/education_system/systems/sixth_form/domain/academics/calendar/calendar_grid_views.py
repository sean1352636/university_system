"""Month, week and agenda tabs for the Sixth Form Calendar GUI.

Sibling to :mod:`calendar_views`, which mounts these; the import
graph stays one-way (this module never imports the main view). Every
tab here is a *shape* of the same data the flat tables already show:

* **Month** — the wall-planner grid, seven columns, colour chips per
  event type from :mod:`calendar_taxonomy`.
* **Week** — :func:`calendar.events_in_week` finally gets a caller;
  seven day columns plus the college's own week label ("Week 6 of
  Autumn Term") in the header.
* **Agenda** — events under date headings, the way a briefing reads
  them out.

Double-clicking any event chip or row opens a small read-only detail
popup local to this module.
"""

from __future__ import annotations

import calendar as _pycal
import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as data,
    calendar_taxonomy as taxonomy,
    calendar_terms as terms,
)

logger = logging.getLogger(__name__)

# Statuses the grids leave out — a Draft is not on anybody's wall.
_HIDDEN_STATUSES: tuple[str, ...] = ("Draft",)

_CHIPS_PER_DAY: int = 3           # then "+N more"


def add_tabs(nb: ttk.Notebook) -> None:
    """Mount the three tabs on the calendar notebook."""
    MonthTab(nb)
    WeekTab(nb)
    AgendaTab(nb)


def _detail_popup(parent: tk.Misc, event: data.Event) -> None:
    win = tk.Toplevel(parent.winfo_toplevel())
    win.title(f"Event #{event.event_id}")
    win.transient(parent.winfo_toplevel())
    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=event.title,
              font=("", 11, "bold")).pack(anchor="w")
    when = (event.start_date if not event.is_multiday
            else f"{event.start_date} → {event.end_date}")
    week = terms.week_label(event.start_date)
    bits = [f"{when}  ·  {event.time_label}"]
    if week:
        bits.append(week)
    ttk.Label(frame, text="  ·  ".join(bits),
              foreground="#555").pack(anchor="w", pady=(0, 6))
    for line in (
        f"Type      : {event.event_type}",
        f"Status    : {event.status}",
        f"Audience  : {event.audience}",
        f"Location  : {event.location or '—'}",
        f"Organiser : {event.organiser or '—'}",
    ):
        ttk.Label(frame, text=line,
                  foreground="#333").pack(anchor="w")
    if event.description:
        t = tk.Text(frame, height=4, wrap="word", width=52)
        t.insert("1.0", event.description)
        t.configure(state="disabled")
        t.pack(fill="x", pady=(6, 0))
    ttk.Button(frame, text="Close",
               command=win.destroy).pack(pady=(10, 0))


def _visible(events: list[data.Event]) -> list[data.Event]:
    return [e for e in events if e.status not in _HIDDEN_STATUSES]


def _chip(parent: tk.Misc, event: data.Event) -> tk.Label:
    colour = taxonomy.colour_for(event.event_type)
    prefix = ("" if event.all_day or not event.start_time
              else f"{event.start_time[:5]} ")
    text = f"{prefix}{event.title}"
    if len(text) > 24:
        text = text[:23] + "…"
    if event.status == "Cancelled":
        text = f"✗ {text}"
    chip = tk.Label(parent, text=text, anchor="w", padx=3,
                    bg=colour, fg="white",
                    font=("TkDefaultFont", 8))
    chip.bind("<Double-1>",
              lambda _e, ev=event: _detail_popup(parent, ev))
    return chip


# ══ Month tab ══════════════════════════════════════════════════════

class MonthTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Month")
        today = _dt.date.today()
        self.year, self.month = today.year, today.month
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="◀", width=3,
                   command=lambda: self._shift(-1)).pack(side="left")
        self.title_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.title_var,
                  font=("", 11, "bold"), width=18,
                  anchor="center").pack(side="left", padx=6)
        ttk.Button(bar, text="▶", width=3,
                   command=lambda: self._shift(1)).pack(side="left")
        ttk.Button(bar, text="Today",
                   command=self._today).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="right")

        self.grid_frame = ttk.Frame(self.frame)
        self.grid_frame.pack(fill="both", expand=True, padx=8,
                             pady=(0, 8))
        for col in range(7):
            self.grid_frame.columnconfigure(col, weight=1,
                                            uniform="dow")

    def _shift(self, months: int) -> None:
        m = self.month + months
        self.year += (m - 1) // 12
        self.month = (m - 1) % 12 + 1
        self.refresh()

    def _today(self) -> None:
        today = _dt.date.today()
        self.year, self.month = today.year, today.month
        self.refresh()

    def refresh(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        first = _dt.date(self.year, self.month, 1)
        self.title_var.set(first.strftime("%B %Y"))

        month_from = first.isoformat()
        last_day = _pycal.monthrange(self.year, self.month)[1]
        month_to = _dt.date(self.year, self.month,
                            last_day).isoformat()
        by_day: dict[str, list[data.Event]] = {}
        for e in _visible(data.list_events(date_from=month_from,
                                           date_to=month_to)):
            sd = max(_dt.date.fromisoformat(e.start_date), first)
            ed = min(_dt.date.fromisoformat(e.end_date),
                     _dt.date(self.year, self.month, last_day))
            for i in range((ed - sd).days + 1):
                by_day.setdefault(
                    (sd + _dt.timedelta(days=i)).isoformat(),
                    []).append(e)

        for col, name in enumerate(
                ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            ttk.Label(self.grid_frame, text=name, anchor="center",
                      font=("", 9, "bold")).grid(
                row=0, column=col, sticky="ew", pady=(0, 2))

        today_iso = _dt.date.today().isoformat()
        weeks = _pycal.Calendar().monthdatescalendar(self.year,
                                                    self.month)
        for r, week in enumerate(weeks, start=1):
            self.grid_frame.rowconfigure(r, weight=1, uniform="wk")
            for c, day in enumerate(week):
                in_month = day.month == self.month
                cell = tk.Frame(
                    self.grid_frame, bd=1, relief="solid",
                    bg=("white" if in_month else "#f2f2f2"))
                cell.grid(row=r, column=c, sticky="nsew")
                head_bg = ("#dbeafe" if day.isoformat() == today_iso
                           else cell["bg"])
                tk.Label(cell, text=str(day.day), anchor="ne",
                         bg=head_bg,
                         fg=("#222" if in_month else "#999"),
                         font=("TkDefaultFont", 8)).pack(fill="x")
                if not in_month:
                    continue
                todays = by_day.get(day.isoformat(), [])
                for e in todays[:_CHIPS_PER_DAY]:
                    _chip(cell, e).pack(fill="x", padx=1, pady=1)
                if len(todays) > _CHIPS_PER_DAY:
                    more = tk.Label(
                        cell,
                        text=f"+{len(todays) - _CHIPS_PER_DAY} more",
                        anchor="w", fg="#666", bg=cell["bg"],
                        font=("TkDefaultFont", 8, "italic"))
                    more.bind(
                        "<Double-1>",
                        lambda _e, d=day.isoformat():
                            self._day_popup(d))
                    more.pack(fill="x", padx=2)

    def _day_popup(self, date_iso: str) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(date_iso)
        win.transient(self.frame.winfo_toplevel())
        box = ttk.Frame(win, padding=10)
        box.pack(fill="both", expand=True)
        for e in _visible(data.events_on(date_iso)):
            _chip(box, e).pack(fill="x", pady=1)
        ttk.Button(box, text="Close",
                   command=win.destroy).pack(pady=(8, 0))


# ══ Week tab ═══════════════════════════════════════════════════════

class WeekTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Week")
        self.anchor = _dt.date.today()
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="◀", width=3,
                   command=lambda: self._shift(-7)).pack(side="left")
        self.title_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.title_var,
                  font=("", 11, "bold"),
                  anchor="center").pack(side="left", padx=8)
        ttk.Button(bar, text="▶", width=3,
                   command=lambda: self._shift(7)).pack(side="left")
        ttk.Button(bar, text="This week",
                   command=self._this_week).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="right")

        self.grid_frame = ttk.Frame(self.frame)
        self.grid_frame.pack(fill="both", expand=True, padx=8,
                             pady=(0, 8))
        for col in range(7):
            self.grid_frame.columnconfigure(col, weight=1,
                                            uniform="dow")
        self.grid_frame.rowconfigure(1, weight=1)

    def _shift(self, days: int) -> None:
        self.anchor += _dt.timedelta(days=days)
        self.refresh()

    def _this_week(self) -> None:
        self.anchor = _dt.date.today()
        self.refresh()

    def refresh(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        monday = self.anchor - _dt.timedelta(
            days=self.anchor.weekday())
        head = f"w/c {monday.isoformat()}"
        week = terms.week_label(monday.isoformat())
        if week:
            head += f"  ·  {week}"
        self.title_var.set(head)

        rows = _visible(data.events_in_week(monday.isoformat()))
        today_iso = _dt.date.today().isoformat()
        for c in range(7):
            day = monday + _dt.timedelta(days=c)
            iso = day.isoformat()
            head_bg = "#dbeafe" if iso == today_iso else "#f4f4f4"
            tk.Label(self.grid_frame,
                     text=day.strftime("%a %d %b"), bg=head_bg,
                     font=("", 9, "bold")).grid(
                row=0, column=c, sticky="ew", padx=1)
            cell = tk.Frame(self.grid_frame, bd=1, relief="solid",
                            bg="white")
            cell.grid(row=1, column=c, sticky="nsew", padx=1)
            for e in rows:
                if e.occurs_on(iso):
                    _chip(cell, e).pack(fill="x", padx=1, pady=1)


# ══ Agenda tab ═════════════════════════════════════════════════════

class AgendaTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Agenda")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.insert(0, _dt.date.today().isoformat())
        self.from_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Days:").pack(side="left")
        self.days_e = ttk.Entry(bar, width=5)
        self.days_e.insert(0, "14")
        self.days_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left")
        for label, days in (("Fortnight", 14), ("Month", 31),
                            ("Term", 92)):
            ttk.Button(bar, text=label,
                       command=lambda d=days: self._preset(d)
                       ).pack(side="left", padx=2)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ttk.Treeview(
            wrap, columns=("time", "type", "title", "where"),
            show="tree headings")
        self.tree.heading("#0", text="Date")
        self.tree.column("#0", width=170)
        for col, text, width in (("time", "Time", 100),
                                 ("type", "Type", 120),
                                 ("title", "Title", 330),
                                 ("where", "Location", 160)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected)

    def _preset(self, days: int) -> None:
        self.days_e.delete(0, "end")
        self.days_e.insert(0, str(days))
        self.refresh()

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            start = _dt.date.fromisoformat(
                self.from_e.get().strip())
            days = max(1, int(self.days_e.get().strip() or "14"))
        except ValueError:
            return
        rows = _visible(data.list_events(
            date_from=start.isoformat(),
            date_to=(start + _dt.timedelta(days=days)).isoformat()))
        by_day: dict[str, list[data.Event]] = {}
        for e in rows:
            by_day.setdefault(e.start_date, []).append(e)
        for date in sorted(by_day):
            day = _dt.date.fromisoformat(date)
            week = terms.week_label(date)
            label = day.strftime("%a %d %b")
            if week:
                label += f"  ({week})"
            parent = self.tree.insert("", "end", text=label,
                                      open=True)
            for e in by_day[date]:
                span = (f"→ {e.end_date}" if e.is_multiday else "")
                self.tree.insert(
                    parent, "end", iid=f"e{e.event_id}-{date}",
                    values=(e.time_label, e.event_type,
                            f"{e.title} {span}".strip(),
                            e.location or "—"))

    def _open_selected(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel or not sel[0].startswith("e"):
            return
        event_id = int(sel[0][1:].split("-")[0])
        event = data.get_event(event_id)
        if event is not None:
            _detail_popup(self.frame, event)
