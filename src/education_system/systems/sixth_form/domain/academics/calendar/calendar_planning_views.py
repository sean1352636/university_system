"""Room, organiser and year-group planning tabs for the Calendar GUI.

Sibling to :mod:`calendar_views`, which mounts these. Three views for
the people who *plan* rather than attend:

* **Rooms** — a swimlane per location for one day: who has the hall,
  when it frees up, where the double-booking is about to happen.
* **My events** — one organiser's events, defaulting to whoever is
  logged in. What a head of year actually opens the calendar for.
* **Y12 / Y13** — the two year groups side by side, because half of
  sixth-form planning is keeping their weeks from colliding.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as data,
    calendar_taxonomy as taxonomy,
)

logger = logging.getLogger(__name__)

_HIDDEN_STATUSES: tuple[str, ...] = ("Draft", "Cancelled")


def add_tabs(nb: ttk.Notebook, *, actor: str | None = None) -> None:
    """Mount the three tabs. ``actor`` pre-fills the organiser view
    with the logged-in user, when the caller knows one."""
    RoomsTab(nb)
    OrganiserTab(nb, actor=actor)
    YearSplitTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


# ══ Rooms tab ══════════════════════════════════════════════════════

class RoomsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Rooms")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Date:").pack(side="left")
        self.date_e = ttk.Entry(bar, width=12)
        self.date_e.insert(0, _today())
        self.date_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left")
        ttk.Button(bar, text="◀", width=3,
                   command=lambda: self._shift(-1)
                   ).pack(side="left", padx=(8, 2))
        ttk.Button(bar, text="▶", width=3,
                   command=lambda: self._shift(1)).pack(side="left")
        ttk.Button(bar, text="Today",
                   command=self._today_btn).pack(side="left", padx=8)

        # Swimlanes scroll horizontally when the college has a lot
        # of rooms in play on one day.
        self.canvas = tk.Canvas(self.frame, highlightthickness=0)
        hs = ttk.Scrollbar(self.frame, orient="horizontal",
                           command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=hs.set)
        self.lanes = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.lanes,
                                  anchor="nw")
        self.lanes.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(fill="both", expand=True, padx=8)
        hs.pack(fill="x", padx=8, pady=(0, 8))

    def _shift(self, days: int) -> None:
        try:
            day = _dt.date.fromisoformat(self.date_e.get().strip())
        except ValueError:
            day = _dt.date.today()
        day += _dt.timedelta(days=days)
        self.date_e.delete(0, "end")
        self.date_e.insert(0, day.isoformat())
        self.refresh()

    def _today_btn(self) -> None:
        self.date_e.delete(0, "end")
        self.date_e.insert(0, _today())
        self.refresh()

    def refresh(self) -> None:
        for child in self.lanes.winfo_children():
            child.destroy()
        try:
            rows = data.events_on(self.date_e.get().strip())
        except data.ValidationError:
            return
        rows = [e for e in rows if e.status not in _HIDDEN_STATUSES]
        by_room: dict[str, list[data.Event]] = {}
        homeless: list[data.Event] = []
        for e in rows:
            if e.location:
                by_room.setdefault(e.location, []).append(e)
            else:
                homeless.append(e)

        lanes = sorted(by_room.items())
        if homeless:
            lanes.append(("(no location)", homeless))
        if not lanes:
            ttk.Label(self.lanes, text="Nothing scheduled.",
                      padding=20).grid(row=0, column=0)
            return
        for col, (room, events) in enumerate(lanes):
            lane = ttk.Frame(self.lanes, relief="groove",
                             borderwidth=1, padding=4)
            lane.grid(row=0, column=col, sticky="ns", padx=3)
            ttk.Label(lane, text=room, font=("", 10, "bold"),
                      anchor="center").pack(fill="x", pady=(0, 4))
            events.sort(key=lambda e: e.start_time or "00")
            for e in events:
                colour = taxonomy.colour_for(e.event_type)
                block = tk.Frame(lane, bg=colour, padx=4, pady=3)
                block.pack(fill="x", pady=2)
                tk.Label(block, text=e.time_label, bg=colour,
                         fg="white",
                         font=("TkDefaultFont", 8, "bold")
                         ).pack(anchor="w")
                title = (e.title if len(e.title) <= 26
                         else e.title[:25] + "…")
                tk.Label(block, text=title, bg=colour, fg="white",
                         font=("TkDefaultFont", 8),
                         wraplength=150, justify="left"
                         ).pack(anchor="w")


# ══ Organiser tab ══════════════════════════════════════════════════

class OrganiserTab:
    def __init__(self, nb: ttk.Notebook, *,
                 actor: str | None = None) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="My Events")
        self.actor = (actor or "").strip()
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Organiser:").pack(side="left")
        self.who_e = ttk.Entry(bar, width=22)
        if self.actor:
            self.who_e.insert(0, self.actor)
        self.who_e.pack(side="left", padx=(2, 8))
        self.upcoming_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Upcoming only",
                        variable=self.upcoming_var,
                        command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=8)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        cols = ("date", "time", "type", "title", "where", "status")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        widths = {"date": 170, "time": 100, "type": 130,
                  "title": 300, "where": 160, "status": 90}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        self.count_var = tk.StringVar()
        ttk.Label(self.frame, textvariable=self.count_var,
                  anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        who = self.who_e.get().strip()
        if not who:
            self.count_var.set("Enter an organiser name.")
            return
        rows = data.list_events(
            organiser_like=who,
            upcoming_only=self.upcoming_var.get())
        for e in rows:
            date = (e.start_date if not e.is_multiday
                    else f"{e.start_date} → {e.end_date}")
            self.tree.insert("", "end", values=(
                date, e.time_label, e.event_type, e.title,
                e.location or "—", e.status))
        self.count_var.set(f"{len(rows)} event(s) for '{who}'.")


# ══ Year 12 / Year 13 tab ══════════════════════════════════════════

class YearSplitTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Y12 / Y13")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.insert(0, _today())
        self.from_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Days:").pack(side="left")
        self.days_e = ttk.Entry(bar, width=5)
        self.days_e.insert(0, "28")
        self.days_e.pack(side="left", padx=(2, 8))
        self.include_all_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Include whole-college events",
                        variable=self.include_all_var,
                        command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=8)

        split = ttk.Frame(self.frame)
        split.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        split.columnconfigure(0, weight=1, uniform="yr")
        split.columnconfigure(1, weight=1, uniform="yr")
        split.rowconfigure(1, weight=1)

        self.trees: dict[str, ttk.Treeview] = {}
        for col, year in enumerate(("Year 12", "Year 13")):
            ttk.Label(split, text=year, font=("", 11, "bold"),
                      anchor="center").grid(row=0, column=col,
                                            sticky="ew", pady=(0, 2))
            wrap = ttk.Frame(split)
            wrap.grid(row=1, column=col, sticky="nsew", padx=3)
            tree = ttk.Treeview(
                wrap, columns=("date", "time", "title"),
                show="headings")
            for c, text, width in (("date", "Date", 100),
                                   ("time", "Time", 90),
                                   ("title", "Title", 260)):
                tree.heading(c, text=text)
                tree.column(c, width=width, anchor="w")
            vs = ttk.Scrollbar(wrap, orient="vertical",
                               command=tree.yview)
            tree.configure(yscrollcommand=vs.set)
            tree.pack(side="left", fill="both", expand=True)
            vs.pack(side="right", fill="y")
            self.trees[year] = tree

    def refresh(self) -> None:
        try:
            start = _dt.date.fromisoformat(self.from_e.get().strip())
            days = max(1, int(self.days_e.get().strip() or "28"))
        except ValueError:
            return
        date_from = start.isoformat()
        date_to = (start + _dt.timedelta(days=days)).isoformat()
        include_all = self.include_all_var.get()
        for year, tree in self.trees.items():
            for item in tree.get_children():
                tree.delete(item)
            wanted = {year} | ({"All", "Students"}
                               if include_all else set())
            rows = [e for e in data.list_events(date_from=date_from,
                                                date_to=date_to)
                    if e.audience in wanted
                    and e.status not in _HIDDEN_STATUSES]
            for e in rows:
                tree.insert("", "end", values=(
                    e.start_date, e.time_label, e.title))
