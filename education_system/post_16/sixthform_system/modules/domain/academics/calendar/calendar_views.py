"""Tkinter views for Sixth Form Calendar.

Notebook with 4 tabs:
* Upcoming  — events from today onwards, with date-range presets.
* All       — every event, filterable by type/audience/status/title etc.
* Day       — single-day lookup.
* Summary   — counts and alerts.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.academics.calendar import (
    calendar as data,
)
from education_system.post_16.sixthform_system.modules.domain.academics.calendar.calendar import (
    AUDIENCES,
    DEFAULT_AUDIENCE,
    DEFAULT_EVENT_TYPE,
    DEFAULT_STATUS,
    EVENT_TYPES,
    Event,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_calendar_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Calendar — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    EventsTab(nb, upcoming_only=True, label="Upcoming")
    EventsTab(nb, upcoming_only=False, label="All Events")
    DayTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


# ══ Events tab ════════════════════════════════════════════════════

class EventsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 upcoming_only: bool, label: str) -> None:
        self.upcoming_only = upcoming_only
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + EVENT_TYPES,
                                     state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Audience:").pack(side="left")
        self.f_audience = ttk.Combobox(bar, values=("",) + AUDIENCES,
                                         state="readonly", width=12)
        self.f_audience.current(0)
        self.f_audience.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=16)
        self.f_title.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=12)
        if self.upcoming_only:
            self.f_from.insert(0, _today())
        self.f_from.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=12)
        self.f_to.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        if self.upcoming_only:
            ttk.Button(bar, text="Next 7",
                        command=lambda: self._preset(7)
                        ).pack(side="left", padx=(8, 2))
            ttk.Button(bar, text="Next 30",
                        command=lambda: self._preset(30)
                        ).pack(side="left", padx=2)
            ttk.Button(bar, text="This term",
                        command=lambda: self._preset(90)
                        ).pack(side="left", padx=2)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "time", "type", "audience",
                "title", "location", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "date": 180, "time": 100,
                  "type": 130, "audience": 90,
                  "title": 280, "location": 180, "status": 100}
        headings = {"id": "ID", "date": "Date", "time": "Time",
                    "type": "Type", "audience": "Audience",
                    "title": "Title", "location": "Location",
                    "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Cancelled", background="#ffd0d0")
        self.tree.tag_configure("Completed", background="#eeeeee")
        self.tree.tag_configure("Postponed", background="#fff7d0")
        self.tree.tag_configure("Draft",     background="#eef7ff")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Cancel",
                    command=lambda: self._quick_status(
                        "Cancelled")).pack(side="left", padx=2)
        ttk.Button(actions, text="Complete",
                    command=lambda: self._quick_status(
                        "Completed")).pack(side="left", padx=2)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _preset(self, days: int) -> None:
        today = _dt.date.today()
        self.f_from.delete(0, "end")
        self.f_from.insert(0, today.isoformat())
        self.f_to.delete(0, "end")
        self.f_to.insert(0,
                          (today + _dt.timedelta(days=days)).isoformat())
        self.refresh()

    def _clear(self) -> None:
        self.f_type.current(0)
        self.f_audience.current(0)
        self.f_status.current(0)
        self.f_title.delete(0, "end")
        self.f_from.delete(0, "end")
        if self.upcoming_only:
            self.f_from.insert(0, _today())
        self.f_to.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_events(
                event_type=self.f_type.get() or None,
                audience=self.f_audience.get() or None,
                status=self.f_status.get() or None,
                title_like=self.f_title.get().strip() or None,
                date_from=self.f_from.get().strip() or None,
                date_to=self.f_to.get().strip() or None,
                upcoming_only=self.upcoming_only,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for e in rows:
            date = (e.start_date if not e.is_multiday
                    else f"{e.start_date} → {e.end_date}")
            tags = (e.status,) if e.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, date, e.time_label,
                e.event_type, e.audience,
                e.title, e.location or "—", e.status,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} event(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> Event | None:
        eid = self._selected_id()
        if eid is None:
            return None
        return data.get_event(eid)

    def _view_selected(self) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo("View", "Select an event first.")
            return
        EventDetailDialog(self.frame.winfo_toplevel(), e)

    def _new(self) -> None:
        EventDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo("Edit", "Select an event first.")
            return
        EventDialog(self.frame.winfo_toplevel(),
                     existing=e, on_save=self.refresh)

    def _status_selected(self) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo("Status", "Select an event first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), e,
                       on_save=self.refresh)

    def _quick_status(self, new_status: str) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo(new_status,
                                  "Select an event first.")
            return
        if not messagebox.askyesno(
                new_status,
                f"Set #{e.event_id} ({e.title}) → {new_status}?"):
            return
        try:
            data.set_status(e.event_id, new_status)
        except ValidationError as ex:
            messagebox.showerror(new_status, str(ex))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo("Delete",
                                  "Select an event first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete event #{e.event_id} "
                                     f"({e.title})?"):
            return
        try:
            data.delete_event(e.event_id)
        except Exception as ex:
            messagebox.showerror("Delete failed", str(ex))
            return
        self.refresh()


# ══ Day tab ═══════════════════════════════════════════════════════

class DayTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Day")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Date:").pack(side="left")
        self.date_e = ttk.Entry(bar, width=14)
        self.date_e.insert(0, _today())
        self.date_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Today",
                    command=self._today).pack(side="left", padx=4)
        ttk.Button(bar, text="◀",
                    command=lambda: self._shift(-1)
                    ).pack(side="left", padx=2)
        ttk.Button(bar, text="▶",
                    command=lambda: self._shift(1)
                    ).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "time", "type", "audience",
                "title", "location", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "time": 130, "type": 140,
                  "audience": 90, "title": 320, "location": 180,
                  "status": 100}
        headings = {"id": "ID", "time": "Time", "type": "Type",
                    "audience": "Audience", "title": "Title",
                    "location": "Location", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Cancelled", background="#ffd0d0")
        self.tree.tag_configure("Completed", background="#eeeeee")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _today(self) -> None:
        self.date_e.delete(0, "end")
        self.date_e.insert(0, _today())
        self.refresh()

    def _shift(self, days: int) -> None:
        try:
            d = _dt.date.fromisoformat(self.date_e.get().strip())
        except ValueError:
            d = _dt.date.today()
        d = d + _dt.timedelta(days=days)
        self.date_e.delete(0, "end")
        self.date_e.insert(0, d.isoformat())
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        s = self.date_e.get().strip()
        try:
            rows = data.events_on(s)
        except ValidationError as e:
            messagebox.showerror("Lookup", str(e))
            return
        weekday = ""
        try:
            weekday = _dt.date.fromisoformat(s).strftime("%A")
        except ValueError:
            pass
        for e in rows:
            tags = (e.status,) if e.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, e.time_label, e.event_type,
                e.audience, e.title, e.location or "—",
                e.status,
            ), tags=tags)
        self.count_var.set(
            f"{len(rows)} event(s) on {s} "
            f"{'(' + weekday + ')' if weekday else ''}")

    def _view_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        e = data.get_event(int(sel[0]))
        if e is None:
            return
        EventDetailDialog(self.frame.winfo_toplevel(), e)


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary",
                                    "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total events       : {summ.total}",
            f"Today              : {summ.today_count}",
            f"This week          : {summ.this_week_count}",
            f"Upcoming ({win}d){' ' * (6 - len(str(win)))}: "
            f"{summ.upcoming}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By type:")
        for t in EVENT_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<20} : {n}")
        lines.append("")
        lines.append("By audience:")
        for a in AUDIENCES:
            n = summ.by_audience.get(a, 0)
            if n:
                lines.append(f"  {a:<14} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class EventDetailDialog:
    def __init__(self, parent: tk.Misc, event: Event) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title(f"Event #{event.event_id}")
        self.win.transient(parent)
        self.win.geometry("700x520")

        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text=event.title,
                   font=("", 12, "bold")).pack(anchor="w")
        when = (event.start_date if not event.is_multiday
                 else f"{event.start_date} → {event.end_date}  "
                       f"({event.day_count} days)")
        ttk.Label(form,
                   text=f"{when}  ·  {event.time_label}",
                   foreground="#555").pack(anchor="w", pady=(0, 8))

        lines = [
            f"Type        : {event.event_type}",
            f"Audience    : {event.audience}",
            f"Status      : {event.status}",
            f"Location    : {event.location or '—'}",
            f"Organiser   : {event.organiser or '—'}",
            f"Capacity    : "
            f"{event.capacity if event.capacity is not None else '—'}",
            f"RSVP        : "
            f"{'required' if event.rsvp_required else 'no'}",
            (f"Cost        : £{event.cost:.2f}"
             if event.cost is not None else "Cost        : —"),
        ]
        for line in lines:
            ttk.Label(form, text=line,
                       foreground="#333").pack(anchor="w")

        if event.description:
            ttk.Label(form, text="Description:",
                       font=("", 10, "bold")).pack(anchor="w",
                                                    pady=(8, 2))
            t = tk.Text(form, height=5, wrap="word")
            t.insert("1.0", event.description)
            t.configure(state="disabled")
            t.pack(fill="x")

        if event.notes:
            ttk.Label(form, text="Notes:",
                       font=("", 10, "bold")).pack(anchor="w",
                                                    pady=(8, 2))
            t = tk.Text(form, height=4, wrap="word")
            t.insert("1.0", event.notes)
            t.configure(state="disabled")
            t.pack(fill="x")

        ttk.Button(form, text="Close",
                    command=self.win.destroy).pack(pady=(10, 0))


class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Event,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — event #{existing.event_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.event_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class EventDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Event | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Event" if existing else "New Event")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.title_e = ttk.Entry(form, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=EVENT_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(self.existing.event_type if self.existing
                            else DEFAULT_EVENT_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Audience:").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.audience_cb = ttk.Combobox(form, values=AUDIENCES,
                                           state="readonly", width=14)
        self.audience_cb.set(self.existing.audience if self.existing
                                else DEFAULT_AUDIENCE)
        self.audience_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing else _today()))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="End date:").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (self.existing.end_date
                                if self.existing else ""))
        self.end_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        self.allday_var = tk.BooleanVar(
            value=(self.existing.all_day if self.existing else False))
        ttk.Checkbutton(form, text="All day",
                          variable=self.allday_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=4)

        r += 1
        ttk.Label(form, text="Start time:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.stime_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.start_time:
            self.stime_e.insert(0, self.existing.start_time[:5])
        self.stime_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="End time:").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.etime_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.end_time:
            self.etime_e.insert(0, self.existing.end_time[:5])
        self.etime_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Location:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.location_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.location:
            self.location_e.insert(0, self.existing.location)
        self.location_e.grid(row=r, column=1, columnspan=3,
                                sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Organiser:").grid(row=r, column=0,
                                                   sticky="e", pady=4)
        self.organiser_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.organiser:
            self.organiser_e.insert(0, self.existing.organiser)
        self.organiser_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Status:").grid(row=r, column=2,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Capacity:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.cap_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.capacity is not None:
            self.cap_e.insert(0, str(self.existing.capacity))
        self.cap_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Cost:").grid(row=r, column=2,
                                              sticky="e", pady=4)
        self.cost_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.cost is not None:
            self.cost_e.insert(0, f"{self.existing.cost:.2f}")
        self.cost_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        self.rsvp_var = tk.BooleanVar(
            value=(self.existing.rsvp_required
                   if self.existing else False))
        ttk.Checkbutton(form, text="RSVP required",
                          variable=self.rsvp_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=4)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=4)
        self.desc_t = tk.Text(form, width=60, height=4)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        return {
            "title":         self.title_e.get().strip(),
            "event_type":    self.type_cb.get(),
            "audience":      self.audience_cb.get(),
            "start_date":    self.start_e.get().strip(),
            "end_date":      self.end_e.get().strip() or None,
            "all_day":       self.allday_var.get(),
            "start_time":    self.stime_e.get().strip() or None,
            "end_time":      self.etime_e.get().strip() or None,
            "location":      self.location_e.get().strip() or None,
            "organiser":     self.organiser_e.get().strip() or None,
            "status":        self.status_cb.get(),
            "capacity":      self.cap_e.get().strip() or None,
            "cost":          self.cost_e.get().strip() or None,
            "rsvp_required": self.rsvp_var.get(),
            "description":   self.desc_t.get("1.0", "end").strip()
                              or None,
            "notes":         self.notes_t.get("1.0", "end").strip()
                              or None,
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_event(self.existing.event_id, payload)
            else:
                data.create_event(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
