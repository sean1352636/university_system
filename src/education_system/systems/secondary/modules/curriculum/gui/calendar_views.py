"""Academic Year & Calendar: one notebook holding what used to be two windows.

Tabs: Overview · Years · Terms · Breaks (old Academic Year window) · Month ·
Day (also the old year window's date look-up) · Events · Summary (old
Calendar window). Rules live in :mod:`modules.curriculum.domain.academic_year` and
:mod:`modules.curriculum.domain.calendar_events`.
"""

from __future__ import annotations

import calendar as _cal
import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.date_picker import DatePicker, recent_years
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
from education_system.systems.secondary.modules.curriculum.domain import calendar_events as CE
from education_system.systems.secondary.core.permissions.access import CALENDAR_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W
from education_system.systems.secondary.ui.gui.layouts.scroll import scrolled_form

logger = logging.getLogger(__name__)

_ERRORS = (AY.ValidationError, AY.PermissionDenied, AY.NotFound)
_ALL = "All"
_YEARS = recent_years(ahead=2, back=6)
_COLOURS = {"school": "#ffffff", "weekend": "#e6e6e6", "closure": "#f8d7d7",
            "inset": "#fde9c4", "holiday": "#dbe9f7", "none": "#f4f4f4"}


_problems = W.problems


def _tree(parent, columns, height: int = 12) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"name", "title", "notes"})


def _selected(tree: ttk.Treeview, owner, what: str) -> int | None:
    sel = tree.selection()
    if not sel:
        messagebox.showinfo(what, f"Select a {what.lower()} first.", parent=owner)
        return None
    return int(sel[0])


def _parse(text: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(text.strip())
    except ValueError:
        return None


# ── Page ─────────────────────────────────────────────────────────────

class CalendarPage:
    TABS = ("Overview", "Years", "Terms", "Breaks", "Month", "Day", "Events", "Summary")

    def __init__(self, parent: ttk.Frame, principal: Principal, state: dict):
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = principal.role in CALENDAR_EDITORS
        self.today = _dt.date.today()
        state.setdefault("day", self.today.isoformat())
        state.setdefault("month", (self.today.year, self.today.month))
        cy = AY.current_year(self.today)
        state.setdefault("year_id", cy.year_id if cy else None)
        ttk.Label(parent, text="Academic Year & Calendar", font=("", 16, "bold")).pack(
            anchor="w")
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True, pady=(6, 0))
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        try:
            self.book.select(self.TABS.index(state.get("tab", "Overview")))
        except (ValueError, tk.TclError):
            pass
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.book.tab(self.book.select(), "text")
        self.state["tab"] = name
        activity_log.record("calendar.tab", target=name)
        self.redraw(name)

    def redraw(self, name: str | None = None) -> None:
        name = name or self.state.get("tab", "Overview")
        frame = self.tabs[name]
        for child in frame.winfo_children():
            child.destroy()
        try:
            getattr(self, "_draw_" + name.lower())(frame)
        except Exception as e:  # noqa: BLE001
            logger.exception("Calendar tab %s failed", name)
            ttk.Label(frame, text=f"Couldn't show {name}: {e}", foreground="#a00").pack()

    def show_day(self, day: _dt.date) -> None:
        self.state["day"] = day.isoformat()
        self.book.select(self.TABS.index("Day"))

    def _year_picker(self, bar: ttk.Frame, on_change: Callable[[], None]) -> AY.AcademicYear | None:
        years = AY.list_years()
        ttk.Label(bar, text="Year:").pack(side="left")
        cb = ttk.Combobox(bar, values=[y.name for y in years], state="readonly", width=9)
        cb.pack(side="left", padx=(4, 12))
        chosen = next((y for y in years if y.year_id == self.state.get("year_id")), None) \
            or (years[0] if years else None)
        if chosen:
            cb.set(chosen.name)

        def pick(_e=None) -> None:
            y = next((y for y in years if y.name == cb.get()), None)
            self.state["year_id"] = y.year_id if y else None
            on_change()

        cb.bind("<<ComboboxSelected>>", pick)
        return chosen

    # ── Overview ──
    def _draw_overview(self, f: ttk.Frame) -> None:
        y = AY.current_year(self.today)
        info = AY.day_info(self.today)
        if y is None:
            ttk.Label(f, text="No academic year is set up yet. Add one on the Years tab, then "
                              "its terms and breaks.", foreground="#a60").pack(anchor="w")
            return
        check = AY.check_year(y.year_id)
        left = AY.school_days_between(self.today, AY._d(y.end_date))
        tiles = ttk.Frame(f)
        tiles.pack(fill="x")
        for i, (label, value, hint) in enumerate((
                ("Academic year", y.name, y.status),
                ("Today", info.label, f"{self.today:%A %d %B %Y}"),
                ("Pupil days this year", str(check.pupil_days),
                 f"{left} still to go · {check.inset_days} INSET"),
                ("Events next 14 days", str(len(CE.summary(days=14).upcoming)), "not cancelled"))):
            tiles.columnconfigure(i, weight=1, uniform="t")
            box = ttk.LabelFrame(tiles, padding=10)
            box.grid(row=0, column=i, sticky="nsew", padx=4)
            ttk.Label(box, text=label, foreground="#666").pack(anchor="w")
            ttk.Label(box, text=value, font=("", 15, "bold"), wraplength=230).pack(anchor="w")
            ttk.Label(box, text=hint, foreground="#888", font=("", 9)).pack(anchor="w")
        cols = ttk.Frame(f)
        cols.pack(fill="both", expand=True, pady=(10, 0))
        cols.columnconfigure(0, weight=1, uniform="c")
        cols.columnconfigure(1, weight=1, uniform="c")
        terms = ttk.LabelFrame(cols, text=f"{y.name} terms", padding=8)
        terms.grid(row=0, column=0, sticky="nsew", padx=4)
        for t in AY.list_terms(y.year_id):
            now = " ← now" if t.start_date <= self.today.isoformat() <= t.end_date else ""
            ttk.Label(terms, text=f"{t.name:<10} {t.start_date} to {t.end_date}{now}").pack(
                anchor="w")
        nxt = ttk.LabelFrame(cols, text="Coming up: holidays and closures", padding=8)
        nxt.grid(row=0, column=1, sticky="nsew", padx=4)
        for b in AY.upcoming_breaks(self.today):
            ttk.Label(nxt, text=f"{b.start_date}  {b.type}: {b.name}"
                                + ("" if b.start_date == b.end_date else f" (to {b.end_date})")
                      ).pack(anchor="w")
        if check.errors or check.warnings:
            box = ttk.LabelFrame(f, text="Checks", padding=8)
            box.pack(fill="x", pady=(10, 0))
            for p in check.errors:
                ttk.Label(box, text=f"✗ {p}", foreground="#a00").pack(anchor="w")
            for p in check.warnings:
                ttk.Label(box, text=f"⚠ {p}", foreground="#a60").pack(anchor="w")

    # ── Years ──
    def _draw_years(self, f: ttk.Frame) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        tree = _tree(f, (("name", "Year", 90), ("start", "Starts", 100), ("end", "Ends", 100),
                         ("status", "Status", 90), ("terms", "Terms", 60),
                         ("days", "Pupil days", 80), ("notes", "Notes", 300)))
        for y in AY.list_years():
            check = AY.check_year(y.year_id)
            tree.insert("", "end", iid=str(y.year_id), values=(
                y.name, y.start_date, y.end_date, y.status, len(AY.list_terms(y.year_id)),
                check.pupil_days, y.notes or ""))
        ttk.Label(f, text="A year always runs 1 September to 31 August. 'Set current' makes it "
                          "the Active year and archives the old one.",
                  foreground="#888").pack(anchor="w", pady=(4, 0))

        def new() -> None:
            year_form(f, self.principal, None, self.redraw)

        def edit() -> None:
            yid = _selected(tree, f, "Year")
            if yid:
                year_form(f, self.principal, AY.get_year(yid), self.redraw)

        def set_current() -> None:
            yid = _selected(tree, f, "Year")
            if yid is None:
                return
            try:
                y = AY.set_current(yid, actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Set current", _problems(e), parent=f)
                return
            self.state["year_id"] = y.year_id
            messagebox.showinfo("Set current", f"{y.name} is now the current year.", parent=f)
            self.redraw()

        def delete() -> None:
            yid = _selected(tree, f, "Year")
            if yid is None:
                return
            y = AY.get_year(yid)
            if not messagebox.askyesno("Delete", f"Delete {y.name} and all its terms and "
                                       "breaks? Events are kept.", parent=f):
                return
            try:
                AY.delete_year(yid, actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete", _problems(e), parent=f)
                return
            self.redraw()

        tree.bind("<Double-1>", lambda _e: edit())
        for text, cmd in (("New", new), ("Edit", edit), ("Set current", set_current),
                          ("Delete", delete)):
            ttk.Button(bar, text=text, command=cmd,
                       state="normal" if self.editor else "disabled").pack(side="left",
                                                                            padx=(0, 6))
        ttk.Button(bar, text="Refresh", command=self.redraw).pack(side="right")

    # ── Terms ──
    def _draw_terms(self, f: ttk.Frame) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        y = self._year_picker(bar, self.redraw)
        ttk.Button(bar, text="Refresh", command=self.redraw).pack(side="right")
        tree = _tree(f, (("name", "Term", 100), ("start", "Starts", 100), ("end", "Ends", 100),
                         ("weeks", "Weeks", 60), ("notes", "Notes", 400)))
        if y:
            for t in AY.list_terms(y.year_id):
                weeks = AY.week_of_term(AY._d(t.end_date), t)
                tree.insert("", "end", iid=str(t.term_id), values=(
                    t.name, t.start_date, t.end_date, weeks, t.notes or ""))
            if y.locked:
                ttk.Label(f, text=f"{y.name} is archived - read only.", foreground="#888").pack(
                    anchor="w")
        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=(6, 0))

        def new() -> None:
            if y:
                term_form(f, self.principal, y, None, self.redraw)

        def edit() -> None:
            tid = _selected(tree, f, "Term")
            if tid and y:
                term_form(f, self.principal, y, AY.get_term(tid), self.redraw)

        def delete() -> None:
            tid = _selected(tree, f, "Term")
            if tid and messagebox.askyesno("Delete", "Delete this term?", parent=f):
                try:
                    AY.delete_term(tid, actor=self.principal)
                except _ERRORS as e:
                    messagebox.showerror("Delete", _problems(e), parent=f)
                self.redraw()

        def copy() -> None:
            if y:
                copy_dialog(f, self.principal, y, self.redraw)

        tree.bind("<Double-1>", lambda _e: edit())
        state = "normal" if self.editor and y and not y.locked else "disabled"
        for text, cmd in (("New", new), ("Edit", edit), ("Delete", delete),
                          ("Copy from another year…", copy)):
            ttk.Button(actions, text=text, command=cmd, state=state).pack(side="left",
                                                                          padx=(0, 6))

    # ── Breaks ──
    def _draw_breaks(self, f: ttk.Frame) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        y = self._year_picker(bar, self.redraw)
        ttk.Label(bar, text="Type:").pack(side="left")
        type_var = tk.StringVar(value=self.state.get("break_type", _ALL))
        tcb = ttk.Combobox(bar, textvariable=type_var, values=[_ALL, *AY.BREAK_TYPES],
                           state="readonly", width=14)
        tcb.pack(side="left", padx=4)
        tcb.bind("<<ComboboxSelected>>", lambda _e: (self.state.update(
            break_type=type_var.get()), self.redraw()))
        ttk.Button(bar, text="Refresh", command=self.redraw).pack(side="right")
        tree = _tree(f, (("name", "Name", 220), ("type", "Type", 100), ("start", "Starts", 100),
                         ("end", "Ends", 100), ("days", "Weekdays", 70),
                         ("notes", "Notes", 280)))
        if y:
            for b in AY.list_breaks(y.year_id, type_=None if type_var.get() == _ALL
                                    else type_var.get()):
                n = sum(1 for d in AY._days(b.start_date, b.end_date) if d.weekday() < 5)
                tree.insert("", "end", iid=str(b.break_id), values=(
                    b.name, b.type, b.start_date, b.end_date, n, b.notes or ""))
        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=(6, 0))

        def new() -> None:
            if y:
                break_form(f, self.principal, y, None, self.redraw)

        def edit() -> None:
            bid = _selected(tree, f, "Break")
            if bid and y:
                break_form(f, self.principal, y, AY.get_break(bid), self.redraw)

        def delete() -> None:
            bid = _selected(tree, f, "Break")
            if bid and messagebox.askyesno("Delete", "Delete this break?", parent=f):
                try:
                    AY.delete_break(bid, actor=self.principal)
                except _ERRORS as e:
                    messagebox.showerror("Delete", _problems(e), parent=f)
                self.redraw()

        def bank() -> None:
            if not y:
                return
            try:
                added = AY.add_bank_holidays(y.year_id, actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Bank holidays", _problems(e), parent=f)
                return
            messagebox.showinfo("Bank holidays", f"{len(added)} added" + (
                ":\n" + "\n".join(f"• {b.start_date} {b.name}" for b in added) if added else
                " - the rest fall in holidays or are already recorded. Add the terms first if "
                "you haven't."), parent=f)
            self.redraw()

        tree.bind("<Double-1>", lambda _e: edit())
        state = "normal" if self.editor and y and not y.locked else "disabled"
        for text, cmd in (("New", new), ("Edit", edit), ("Delete", delete),
                          ("Add bank holidays", bank)):
            ttk.Button(actions, text=text, command=cmd, state=state).pack(side="left",
                                                                          padx=(0, 6))

    # ── Month ──
    def _draw_month(self, f: ttk.Frame) -> None:
        year, month = self.state["month"]
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))

        def go(delta: int) -> None:
            m = year * 12 + month - 1 + delta
            self.state["month"] = (m // 12, m % 12 + 1)
            self.redraw()

        ttk.Button(bar, text="◀", width=3, command=lambda: go(-1)).pack(side="left")
        ttk.Label(bar, text=f"{_cal.month_name[month]} {year}", font=("", 13, "bold"),
                  width=16, anchor="center").pack(side="left", padx=6)
        ttk.Button(bar, text="▶", width=3, command=lambda: go(1)).pack(side="left")
        ttk.Button(bar, text="Today", command=lambda: (self.state.update(
            month=(self.today.year, self.today.month)), self.redraw())).pack(side="left",
                                                                             padx=8)
        key = ttk.Frame(bar)
        key.pack(side="right")
        for name, colour in (("School day", "school"), ("Holiday", "holiday"),
                             ("Closure", "closure"), ("INSET", "inset"), ("Weekend", "weekend")):
            tk.Label(key, text=name, bg=_COLOURS[colour], relief="solid", bd=1,
                     padx=4).pack(side="left", padx=2)
        days = AY.month_info(year, month)
        first, last = min(days), max(days)
        counts = CE.counts_by_day(first, last)
        grid = ttk.Frame(f)
        grid.pack(fill="both", expand=True)
        for c, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            grid.columnconfigure(c, weight=1, uniform="d")
            ttk.Label(grid, text=name, anchor="center").grid(row=0, column=c, sticky="ew")
        row = 1
        for d, info in sorted(days.items()):
            col = d.weekday()
            if info.is_weekend:
                kind = "weekend"
            elif info.year is None:
                kind = "none"
            elif info.closure:
                kind = "inset" if info.closure.type == "INSET" else "closure"
            elif info.term is None:
                kind = "holiday"
            else:
                kind = "school"
            note = ""
            if info.closure and not info.is_weekend:
                note = info.closure.name
            elif info.term and not info.is_weekend:
                note = f"{info.term.name} wk {info.week}"
            text = f"{d.day}{'  •' if d == self.today else ''}\n{note[:18]}"
            if counts.get(d):
                text += f"\n{counts[d]} event{'s' if counts[d] != 1 else ''}"
            cell = tk.Label(grid, text=text, bg=_COLOURS[kind], anchor="nw", justify="left",
                            relief="solid", bd=1, height=4, padx=4, cursor="hand2",
                            font=("", 9, "bold" if d == self.today else "normal"))
            cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
            cell.bind("<Button-1>", lambda _e, day=d: self.show_day(day))
            if col == 6:
                row += 1
        ttk.Label(f, text="Click a day to see it on the Day tab.", foreground="#888").pack(
            anchor="w", pady=(4, 0))

    # ── Day (also the old date look-up) ──
    def _draw_day(self, f: ttk.Frame) -> None:
        day = _parse(self.state["day"]) or self.today
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Date:").pack(side="left")
        entry = ttk.Entry(bar, width=12)
        entry.insert(0, day.isoformat())
        entry.pack(side="left", padx=4)

        def show(d: _dt.date | None) -> None:
            if d is None:
                messagebox.showinfo("Day", "Enter a date as YYYY-MM-DD.", parent=f)
                return
            self.state["day"] = d.isoformat()
            self.redraw()

        ttk.Button(bar, text="Apply", command=lambda: show(_parse(entry.get()))).pack(
            side="left")
        entry.bind("<Return>", lambda _e: show(_parse(entry.get())))
        ttk.Button(bar, text="Today", command=lambda: show(self.today)).pack(side="left",
                                                                             padx=4)
        ttk.Button(bar, text="◀", width=3,
                   command=lambda: show(day - _dt.timedelta(days=1))).pack(side="left")
        ttk.Button(bar, text="▶", width=3,
                   command=lambda: show(day + _dt.timedelta(days=1))).pack(side="left")
        info = AY.day_info(day)
        box = ttk.LabelFrame(f, text=f"{day:%A %d %B %Y}", padding=8)
        box.pack(fill="x")
        ttk.Label(box, text=info.label, font=("", 12, "bold")).pack(anchor="w")
        facts = [f"Academic year: {info.year.name if info.year else '— (not set up)'}",
                 "Pupils in school: " + ("yes" if info.is_school_day else "no"),
                 "Staff working day: " + ("yes" if info.is_staff_day else "no")]
        if info.term:
            facts.append(f"Term: {info.term.name} ({info.term.start_date} to "
                         f"{info.term.end_date}), week {info.week}")
        for b in info.breaks:
            facts.append(f"{b.type}: {b.name} ({b.start_date} to {b.end_date})")
        for line in facts:
            ttk.Label(box, text=line).pack(anchor="w")
        events = CE.events_on(day)
        ttk.Label(f, text=f"Events ({len(events)})", font=("", 11, "bold")).pack(
            anchor="w", pady=(10, 4))
        tree = _tree(f, (("time", "Time", 110), ("title", "Title", 260), ("type", "Type", 120),
                         ("aud", "Audience", 80), ("where", "Location", 140),
                         ("status", "Status", 90)), height=8)
        for ev in events:
            tree.insert("", "end", iid=str(ev.event_id), values=(
                "All day" if ev.all_day else f"{ev.start_time or ''}-{ev.end_time or ''}",
                ev.title, ev.event_type, ev.audience, ev.location or "", ev.status))
        tree.bind("<Double-1>", lambda _e: tree.selection() and view_event(
            f, int(tree.selection()[0])))
        ttk.Button(f, text="New event on this day…", command=lambda: event_form(
            f, self.principal, None, self.redraw, day=day)).pack(anchor="w", pady=(6, 0))

    # ── Events (old Calendar window list) ──
    def _draw_events(self, f: ttk.Frame) -> None:
        flt = self.state.setdefault("events", {})
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 4))
        vars_ = {}

        def combo(label: str, key: str, values, width: int) -> None:
            ttk.Label(bar, text=f"{label}:").pack(side="left")
            v = tk.StringVar(value=flt.get(key, _ALL))
            ttk.Combobox(bar, textvariable=v, values=[_ALL, *values], state="readonly",
                         width=width).pack(side="left", padx=(2, 8))
            vars_[key] = v

        combo("Type", "type", CE.EVENT_TYPES, 14)
        combo("Audience", "audience", CE.AUDIENCES, 9)
        combo("Status", "status", CE.STATUSES, 10)
        ttk.Label(bar, text="Title:").pack(side="left")
        title = ttk.Entry(bar, width=14)
        title.insert(0, flt.get("title", ""))
        title.pack(side="left", padx=(2, 8))
        bar2 = ttk.Frame(f)
        bar2.pack(fill="x", pady=(0, 6))
        ttk.Label(bar2, text="From:").pack(side="left")
        frm = ttk.Entry(bar2, width=11)
        frm.insert(0, flt.get("from", self.today.isoformat()))
        frm.pack(side="left", padx=(2, 8))
        ttk.Label(bar2, text="To:").pack(side="left")
        to = ttk.Entry(bar2, width=11)
        to.insert(0, flt.get("to", ""))
        to.pack(side="left", padx=(2, 8))

        def apply() -> None:
            for key, v in vars_.items():
                flt[key] = v.get()
            flt.update(title=title.get(), **{"from": frm.get().strip(), "to": to.get().strip()})
            self.redraw()

        def preset(days: int | None, this_term: bool = False) -> None:
            frm.delete(0, "end")
            to.delete(0, "end")
            frm.insert(0, self.today.isoformat())
            if this_term:
                t = AY.term_for(self.today)
                if t is None:
                    messagebox.showinfo("This term", "Today isn't in a term.", parent=f)
                    return
                frm.delete(0, "end")
                frm.insert(0, t.start_date)
                to.insert(0, t.end_date)
            elif days:
                to.insert(0, (self.today + _dt.timedelta(days=days)).isoformat())
            apply()

        def clear() -> None:
            flt.clear()
            flt["from"] = ""
            self.redraw()

        for text, cmd in (("Apply", apply), ("Clear", clear), ("Next 7", lambda: preset(7)),
                          ("Next 30", lambda: preset(30)),
                          ("This term", lambda: preset(None, this_term=True))):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=(0, 4))
        problems = []
        for label, raw in (("From", flt.get("from", self.today.isoformat())),
                           ("To", flt.get("to", ""))):
            if raw and _parse(raw) is None:
                problems.append(f"{label} must be YYYY-MM-DD")
        tree = _tree(f, (("date", "Date", 160), ("time", "Time", 90), ("title", "Title", 240),
                         ("type", "Type", 110), ("aud", "Audience", 80),
                         ("where", "Location", 120), ("status", "Status", 85)))
        pick = lambda k: None if flt.get(k, _ALL) == _ALL else flt.get(k)  # noqa: E731
        rows = [] if problems else CE.list_events(
            start=flt.get("from", self.today.isoformat()) or None, end=flt.get("to") or None,
            event_type=pick("type"), audience=pick("audience"), status=pick("status"),
            search=flt.get("title") or None)
        for ev in rows:
            tree.insert("", "end", iid=str(ev.event_id), values=(
                ev.start_date if ev.start_date == ev.end_date else
                f"{ev.start_date} → {ev.end_date}",
                "All day" if ev.all_day else f"{ev.start_time or ''}-{ev.end_time or ''}",
                ev.title, ev.event_type, ev.audience, ev.location or "", ev.status))
        ttk.Label(f, text="; ".join(problems) or f"{len(rows)} event(s)",
                  foreground="#a00" if problems else "#666").pack(anchor="w")
        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=(6, 0))

        def sel() -> int | None:
            return _selected(tree, f, "Event")

        def status(new: str | None) -> None:
            eid = sel()
            if eid:
                status_dialog(f, self.principal, CE.get_event(eid), self.redraw, preset=new)

        def delete() -> None:
            eid = sel()
            if eid and messagebox.askyesno("Delete", "Delete this event? To call it off, "
                                           "Cancel it instead so the calendar still shows it.",
                                           parent=f):
                try:
                    CE.delete_event(eid, actor=self.principal)
                except _ERRORS as e:
                    messagebox.showerror("Delete", _problems(e), parent=f)
                self.redraw()

        tree.bind("<Double-1>", lambda _e: (eid := sel()) and view_event(f, eid))
        for text, cmd in (
                ("View", lambda: (eid := sel()) and view_event(f, eid)),
                ("New", lambda: event_form(f, self.principal, None, self.redraw)),
                ("Edit", lambda: (eid := sel()) and event_form(
                    f, self.principal, CE.get_event(eid), self.redraw)),
                ("Status", lambda: status(None)), ("Cancel", lambda: status("Cancelled")),
                ("Complete", lambda: status("Completed")), ("Delete", delete)):
            ttk.Button(actions, text=text, command=cmd).pack(side="left", padx=(0, 4))
        ttk.Button(actions, text="Refresh", command=self.redraw).pack(side="right")

    # ── Summary ──
    def _draw_summary(self, f: ttk.Frame) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
        days = ttk.Spinbox(bar, from_=1, to=365, width=5)
        days.set(str(self.state.get("summary_days", 14)))
        days.pack(side="left", padx=4)

        def apply() -> None:
            try:
                self.state["summary_days"] = max(1, min(365, int(days.get())))
            except ValueError:
                pass
            self.redraw()

        ttk.Button(bar, text="Apply", command=apply).pack(side="left")
        s = CE.summary(days=self.state.get("summary_days", 14))
        cols = ttk.Frame(f)
        cols.pack(fill="x")
        for i, (title, data) in enumerate((("By type", s.by_type), ("By status", s.by_status))):
            box = ttk.LabelFrame(cols, text=title, padding=8)
            box.grid(row=0, column=i, sticky="nw", padx=4)
            for k, n in data.items():
                ttk.Label(box, text=f"{n:>4}  {k}").pack(anchor="w")
        ttk.Label(f, text=f"{s.total} events in all · next {self.state.get('summary_days', 14)} "
                          f"days: {len(s.upcoming)}", font=("", 11, "bold")).pack(
            anchor="w", pady=(10, 4))
        tree = _tree(f, (("date", "When", 220), ("title", "Title", 280), ("type", "Type", 120),
                         ("aud", "Audience", 80)), height=10)
        for ev in s.upcoming:
            tree.insert("", "end", iid=str(ev.event_id), values=(
                ev.when, ev.title, ev.event_type, ev.audience))
        tree.bind("<Double-1>", lambda _e: tree.selection() and view_event(
            f, int(tree.selection()[0])))


def draw_academic_calendar(parent: ttk.Frame, *, principal: Principal,
                           state: dict | None = None) -> CalendarPage:
    return CalendarPage(parent, principal, state if state is not None else {})


# ── Dialogs ──────────────────────────────────────────────────────────

def _dialog(owner, title: str, size: str = "560x420"):
    win = make_toplevel(owner.winfo_toplevel())
    win.title(title)
    window_sizing.fit(win, size, (460, 300))
    body, footer = scrolled_form(win)
    error = tk.StringVar()
    ttk.Label(footer, textvariable=error, foreground="#a00", wraplength=520,
              justify="left").pack(anchor="w")
    bar = ttk.Frame(footer)
    bar.pack(anchor="e", pady=(4, 0))
    return win, body, error, bar


def _row(body, r: int, label: str, widget) -> None:
    ttk.Label(body, text=label).grid(row=r, column=0, sticky="nw", pady=2, padx=(0, 8))
    widget.grid(row=r, column=1, sticky="w", pady=2)


def _buttons(win, bar, save: Callable[[], None]) -> None:
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def _attempt(win, error: tk.StringVar, fn: Callable[[], object], after) -> None:
    try:
        fn()
    except AY.ValidationError as e:
        error.set(_problems(e))
        return
    except _ERRORS as e:
        messagebox.showerror("Calendar", str(e), parent=win)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("Calendar save failed")
        messagebox.showerror("Calendar", f"Something went wrong:\n{e}", parent=win)
        return
    win.destroy()
    after()


def year_form(owner, principal: Principal, year: AY.AcademicYear | None, after) -> None:
    win, body, error, bar = _dialog(owner, f"Edit {year.name}" if year else "New academic year")
    name = ttk.Combobox(body, width=10, values=[AY.year_name_for(
        _dt.date(_dt.date.today().year + k, 9, 1)) for k in (-1, 0, 1, 2)])
    if year:
        name.set(year.name)
        name.configure(state="disabled")
    _row(body, 0, "Name *", name)
    dates = ttk.Label(body, foreground="#666")
    _row(body, 1, "Dates", dates)

    def show_dates(*_a) -> None:
        try:
            s, e = AY.bounds(name.get().strip())
            dates.configure(text=f"{s} to {e}")
        except AY.ValidationError:
            dates.configure(text="1 September to 31 August")

    name.bind("<<ComboboxSelected>>", show_dates)
    name.bind("<KeyRelease>", show_dates)
    show_dates()
    status = ttk.Combobox(body, values=["Planning", "Archived"], state="readonly", width=10)
    if year:
        status.set(year.status)
        if year.status == "Active":
            status.configure(state="disabled")
        _row(body, 2, "Status", status)
    notes = tk.Text(body, width=44, height=4, wrap="word")
    notes.insert("1.0", (year.notes or "") if year else "")
    _row(body, 3, "Notes", notes)

    def save() -> None:
        text = notes.get("1.0", "end").strip()
        if year:
            st = status.get() if year.status != "Active" else None
            _attempt(win, error, lambda: AY.update_year(year.year_id, actor=principal,
                                                        notes=text, status=st), after)
        else:
            _attempt(win, error, lambda: AY.create_year(name.get(), actor=principal,
                                                        notes=text), after)

    _buttons(win, bar, save)


def term_form(owner, principal: Principal, year: AY.AcademicYear, term: AY.Term | None,
              after) -> None:
    win, body, error, bar = _dialog(owner, f"{'Edit' if term else 'New'} term - {year.name}")
    name = ttk.Combobox(body, values=list(AY.TERM_NAMES), state="readonly", width=12)
    name.set(term.name if term else "")
    _row(body, 0, "Name *", name)
    start = DatePicker(body, value=term.start_date if term else None, years=_YEARS)
    _row(body, 1, "Start date *", start)
    end = DatePicker(body, value=term.end_date if term else None, years=_YEARS)
    _row(body, 2, "End date *", end)
    notes = ttk.Entry(body, width=44)
    notes.insert(0, (term.notes or "") if term else "")
    _row(body, 3, "Notes", notes)
    data = lambda: {"name": name.get(), "start_date": start.get(),  # noqa: E731
                    "end_date": end.get(), "notes": notes.get()}
    _buttons(win, bar, lambda: _attempt(
        win, error, (lambda: AY.update_term(term.term_id, data(), actor=principal)) if term
        else (lambda: AY.add_term(year.year_id, data(), actor=principal)), after))


def break_form(owner, principal: Principal, year: AY.AcademicYear, brk: AY.Break | None,
               after) -> None:
    win, body, error, bar = _dialog(owner, f"{'Edit' if brk else 'New'} break - {year.name}")
    name = ttk.Entry(body, width=34)
    name.insert(0, brk.name if brk else "")
    _row(body, 0, "Name *", name)
    type_ = ttk.Combobox(body, values=list(AY.BREAK_TYPES), state="readonly", width=14)
    type_.set(brk.type if brk else "Holiday")
    _row(body, 1, "Type *", type_)
    start = DatePicker(body, value=brk.start_date if brk else None, years=_YEARS)
    _row(body, 2, "Start date *", start)
    end = DatePicker(body, value=brk.end_date if brk else None, years=_YEARS)
    _row(body, 3, "End date", end)
    ttk.Label(body, text="Leave the end date blank for a single day. Exam periods are "
                         "recorded but don't close the school.", foreground="#888",
              wraplength=420).grid(row=4, column=1, sticky="w")
    notes = ttk.Entry(body, width=44)
    notes.insert(0, (brk.notes or "") if brk else "")
    _row(body, 5, "Notes", notes)
    data = lambda: {"name": name.get(), "type": type_.get(),  # noqa: E731
                    "start_date": start.get(), "end_date": end.get(), "notes": notes.get()}
    _buttons(win, bar, lambda: _attempt(
        win, error, (lambda: AY.update_break(brk.break_id, data(), actor=principal)) if brk
        else (lambda: AY.add_break(year.year_id, data(), actor=principal)), after))


def copy_dialog(owner, principal: Principal, year: AY.AcademicYear, after) -> None:
    others = [y for y in AY.list_years() if y.year_id != year.year_id and AY.list_terms(y.year_id)]
    if not others:
        messagebox.showinfo("Copy", "No other year has terms to copy.", parent=owner)
        return
    win, body, error, bar = _dialog(owner, f"Copy into {year.name}", "520x260")
    src = ttk.Combobox(body, values=[y.name for y in others], state="readonly", width=10)
    src.set(others[0].name)
    _row(body, 0, "Copy from", src)
    ttk.Label(body, text="Terms and breaks are moved on by whole weeks so each date keeps its "
                         "weekday. Bank holidays aren't copied - use Add bank holidays on the "
                         "Breaks tab. Check every date afterwards.", wraplength=440,
              foreground="#666", justify="left").grid(row=1, column=0, columnspan=2, sticky="w")

    def save() -> None:
        source = next(y for y in others if y.name == src.get())

        def run():
            t, b = AY.copy_from(year.year_id, source.year_id, actor=principal)
            messagebox.showinfo("Copy", f"{t} terms and {b} breaks copied.", parent=owner)

        _attempt(win, error, run, after)

    _buttons(win, bar, save)


def view_event(owner, event_id: int) -> None:
    ev = CE.get_event(event_id)
    if ev is None:
        return
    activity_log.record("calendar.event.view", target=f"event:{event_id}")
    win = make_toplevel(owner.winfo_toplevel())
    win.title(ev.title)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    rows = [("Title", ev.title), ("Type", ev.event_type), ("When", ev.when),
            ("Location", ev.location), ("Organiser", ev.organiser), ("Audience", ev.audience),
            ("Status", ev.status + (f" - {ev.status_reason}" if ev.status_reason else "")),
            ("Capacity", ev.capacity), ("RSVP required", "Yes" if ev.rsvp_required else "No"),
            ("Cost", f"£{ev.cost:.2f}" if ev.cost is not None else None),
            ("Description", ev.description), ("Notes", ev.notes),
            ("Added", f"{ev.created_at} by {ev.created_by or '—'}"),
            ("Changed", f"{ev.updated_at} by {ev.updated_by or '—'}")]
    for r, (k, v) in enumerate(rows):
        ttk.Label(frm, text=f"{k}:", foreground="#555").grid(row=r, column=0, sticky="nw",
                                                              padx=(0, 8))
        ttk.Label(frm, text="—" if v in (None, "") else str(v), wraplength=420,
                  justify="left").grid(row=r, column=1, sticky="w")
    for r2, w in enumerate(CE.warnings_for(ev.start_date, ev.end_date), len(rows)):
        ttk.Label(frm, text=f"⚠ {w}", foreground="#a60").grid(row=r2, column=0, columnspan=2,
                                                              sticky="w")
    ttk.Button(frm, text="Close", command=win.destroy).grid(row=99, column=1, sticky="e",
                                                            pady=(8, 0))


def event_form(owner, principal: Principal, ev: CE.Event | None, after,
               day: _dt.date | None = None) -> None:
    if ev is not None and not CE.can_change(principal, ev):
        messagebox.showinfo("Edit event", "You can change events you added; ask an "
                            "administrator to change this one.", parent=owner)
        return
    win, body, error, bar = _dialog(owner, "Edit event" if ev else "New event", "760x700")
    w: dict = {}

    def entry(r, c, label, key, width=30):
        ttk.Label(body, text=label).grid(row=r, column=c, sticky="w", pady=2, padx=(0, 6))
        e = ttk.Entry(body, width=width)
        v = getattr(ev, key) if ev else None
        e.insert(0, "" if v is None else str(v))
        e.grid(row=r, column=c + 1, sticky="w", pady=2)
        w[key] = e

    def combo(r, c, label, key, values, default):
        ttk.Label(body, text=label).grid(row=r, column=c, sticky="w", pady=2, padx=(0, 6))
        cb = ttk.Combobox(body, values=list(values), state="readonly", width=16)
        cb.set(getattr(ev, key) if ev else default)
        cb.grid(row=r, column=c + 1, sticky="w", pady=2)
        w[key] = cb

    entry(0, 0, "Title *", "title", 40)
    combo(1, 0, "Type *", "event_type", CE.EVENT_TYPES, "Meeting")
    combo(1, 2, "Audience", "audience", CE.AUDIENCES, "All")
    for r, c, label, key in ((2, 0, "Start date *", "start_date"),
                             (2, 2, "End date", "end_date")):
        ttk.Label(body, text=label).grid(row=r, column=c, sticky="w", pady=2, padx=(0, 6))
        default = getattr(ev, key) if ev else (day.isoformat() if day else None)
        dp = DatePicker(body, value=default, years=_YEARS)
        dp.grid(row=r, column=c + 1, sticky="w", pady=2)
        w[key] = dp
    all_day = tk.BooleanVar(value=bool(ev.all_day) if ev else False)
    ttk.Checkbutton(body, text="All day", variable=all_day).grid(row=3, column=1, sticky="w")
    entry(4, 0, "Start time", "start_time", 8)
    entry(4, 2, "End time", "end_time", 8)
    entry(5, 0, "Location", "location")
    entry(6, 0, "Organiser", "organiser")
    if ev is None:
        combo(6, 2, "Status", "status", ("Scheduled", "Draft"), "Scheduled")
    else:
        ttk.Label(body, text=f"Status: {ev.status}").grid(row=6, column=2, columnspan=2,
                                                          sticky="w")
    entry(7, 0, "Capacity", "capacity", 8)
    entry(7, 2, "Cost (£)", "cost", 8)
    rsvp = tk.BooleanVar(value=bool(ev.rsvp_required) if ev else False)
    ttk.Checkbutton(body, text="RSVP required", variable=rsvp).grid(row=8, column=1,
                                                                    sticky="w")
    for r, key in ((9, "description"), (10, "notes")):
        ttk.Label(body, text=key.capitalize()).grid(row=r, column=0, sticky="nw", pady=2)
        t = tk.Text(body, width=60, height=4, wrap="word")
        t.insert("1.0", (getattr(ev, key) or "") if ev else "")
        t.grid(row=r, column=1, columnspan=3, sticky="w", pady=2)
        w[key] = t

    def time_state(*_a) -> None:
        for k in ("start_time", "end_time"):
            w[k].configure(state="disabled" if all_day.get() else "normal")

    all_day.trace_add("write", time_state)
    time_state()

    def values() -> dict:
        out = {}
        for k, widget in w.items():
            out[k] = widget.get("1.0", "end").strip() if isinstance(widget, tk.Text) \
                else widget.get()
        out["all_day"] = all_day.get()
        out["rsvp_required"] = rsvp.get()
        return out

    def save() -> None:
        data = values()
        notes = CE.warnings_for(data.get("start_date") or "", data.get("end_date") or None)
        if notes and not messagebox.askyesno(
                "Check the date", "The school isn't open on:\n• " + "\n• ".join(notes[:8])
                + "\n\nSave anyway?", parent=win):
            return
        if ev:
            _attempt(win, error, lambda: CE.update_event(ev.event_id, data, actor=principal),
                     after)
        else:
            _attempt(win, error, lambda: CE.create_event(data, actor=principal), after)

    _buttons(win, bar, save)


def status_dialog(owner, principal: Principal, ev: CE.Event | None, after,
                  preset: str | None = None) -> None:
    if ev is None:
        return
    win, body, error, bar = _dialog(owner, f"Status - {ev.title}", "480x240")
    ttk.Label(body, text=f"Now: {ev.status}").grid(row=0, column=0, columnspan=2, sticky="w")
    status = ttk.Combobox(body, values=[s for s in CE.STATUSES if s != ev.status],
                          state="readonly", width=12)
    if preset:
        status.set(preset)
    _row(body, 1, "New status", status)
    reason = ttk.Entry(body, width=40)
    _row(body, 2, "Reason", reason)
    ttk.Label(body, text="A reason is needed to cancel.", foreground="#888").grid(
        row=3, column=1, sticky="w")
    _buttons(win, bar, lambda: _attempt(win, error, lambda: CE.set_status(
        ev.event_id, status.get(), actor=principal, reason=reason.get()), after))
