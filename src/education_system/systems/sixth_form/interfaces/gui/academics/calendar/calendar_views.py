"""Tkinter views for Sixth Form Calendar.

The notebook's flat tabs live here — Upcoming, All Events, Day and
Summary — along with the event dialogs. The richer shapes mount from
siblings: :mod:`calendar_grid_views` (Month / Week / Agenda),
:mod:`calendar_planning_views` (Rooms / My Events / Y12-Y13) and
:mod:`calendar_admin_views` (Bookings / Trips / Series / Messages /
Audit / Archive). The import graph is one-way: this module imports
the siblings, never the reverse.

Saves run the clash check (:mod:`calendar_clashes`) and the term
check (:mod:`calendar_terms`) and put what they find in front of the
user — a warning with a "save anyway", never a silent veto. Deleting
from here is an *archive* (recoverable from the Archive tab);
permanent deletion lives only there.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as data,
    calendar_admin_views as admin_views,
    calendar_governance as governance,
    calendar_grid_views as grid_views,
    calendar_notifications as notifications,
    calendar_planning_views as planning_views,
    calendar_taxonomy as taxonomy,
)
from education_system.systems.sixth_form.domain.academics.calendar.calendar import (
    AUDIENCES,
    DEFAULT_AUDIENCE,
    DEFAULT_EVENT_TYPE,
    DEFAULT_STATUS,
    EVENT_TYPES,
    VISIBILITIES,
    DEFAULT_VISIBILITY,
    Event,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def _actor(gui) -> str | None:
    auth = getattr(gui, "auth", None)
    return ((getattr(auth, "current_user", None) or {}).get("username")
            if auth else None)


def _role(gui) -> str | None:
    """The launcher's sixth-form role for the logged-in user, when
    the window was opened from the main GUI."""
    auth = getattr(gui, "auth", None)
    cu = (getattr(auth, "current_user", None) or {}) if auth else {}
    for s in cu.get("systems", []) or []:
        if s.get("system_key") == "sixth_form":
            return s.get("role")
    return None


def add_tabs(nb: ttk.Notebook, *, actor: str | None = None,
             role: str | None = None) -> None:
    """Append the calendar's tabs to an existing notebook.

    Split out of :func:`open_calendar_window` so the merged
    "Academic Year & Calendar" window can host these tabs
    alongside the year-structure ones. The standalone window is
    now just this plus a Toplevel.
    """
    data.init_db()
    EventsTab(nb, upcoming_only=True, label="Upcoming", actor=actor)
    EventsTab(nb, upcoming_only=False, label="All Events",
              actor=actor)
    DayTab(nb)
    grid_views.add_tabs(nb)
    planning_views.add_tabs(nb, actor=actor)
    admin_views.add_tabs(nb, actor=actor, role=role)
    SummaryTab(nb)


def open_calendar_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Calendar — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    add_tabs(nb, actor=_actor(parent), role=_role(parent))


def _today() -> str:
    return _dt.date.today().isoformat()


# ══ Events tab ════════════════════════════════════════════════════

class EventsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 upcoming_only: bool, label: str,
                 actor: str | None = None) -> None:
        self.upcoming_only = upcoming_only
        self.actor = actor
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

        # Quick add: "Title, 2026-09-14[, 14:00-15:30][, Hall]" —
        # three fields for a three-fact event instead of the twelve-
        # field dialog.
        quick = ttk.Frame(self.frame)
        quick.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(quick, text="Quick add:").pack(side="left")
        self.quick_e = ttk.Entry(quick)
        self.quick_e.pack(side="left", fill="x", expand=True,
                           padx=(4, 4))
        self.quick_e.bind("<Return>", lambda _e: self._quick_add())
        ttk.Button(quick, text="Add",
                    command=self._quick_add).pack(side="left")

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
        # One foreground tag per event type; background (status) and
        # foreground (type) tags don't fight over options.
        for etype, colour in taxonomy.palette().items():
            self.tree.tag_configure(f"type:{etype}",
                                     foreground=colour)
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
        ttk.Button(actions, text="Duplicate",
                    command=self._duplicate_selected).pack(side="left",
                                                             padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Cancel",
                    command=lambda: self._quick_status(
                        "Cancelled")).pack(side="left", padx=2)
        ttk.Button(actions, text="Complete",
                    command=lambda: self._quick_status(
                        "Completed")).pack(side="left", padx=2)
        ttk.Button(actions, text="Archive",
                    command=self._archive_selected).pack(side="left",
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
            tags = [f"type:{e.event_type}"]
            if e.status in STATUSES:
                tags.append(e.status)
            self.tree.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, date, e.time_label,
                e.event_type, e.audience,
                e.title, e.location or "—", e.status,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} event(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected_ids(self) -> list[int]:
        return [int(i) for i in self.tree.selection()]

    def _selected(self) -> Event | None:
        eid = self._selected_id()
        if eid is None:
            return None
        return data.get_event(eid)

    def _quick_add(self) -> None:
        """Parse 'Title, date[, HH:MM[-HH:MM]][, location]'."""
        raw = self.quick_e.get().strip()
        if not raw:
            return
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 2:
            messagebox.showinfo(
                "Quick add",
                "Format: Title, YYYY-MM-DD[, HH:MM[-HH:MM]]"
                "[, location]")
            return
        payload: dict = {"title": parts[0],
                          "start_date": parts[1]}
        rest = parts[2:]
        if rest and rest[0][:1].isdigit() and ":" in rest[0]:
            start, _, end = rest[0].partition("-")
            payload["start_time"] = start.strip()
            if end.strip():
                payload["end_time"] = end.strip()
            rest = rest[1:]
        if rest:
            payload["location"] = ", ".join(rest)
        try:
            event = governance.audited_create(payload,
                                                actor=self.actor)
        except ValidationError as e:
            messagebox.showerror("Quick add", str(e))
            return
        self.quick_e.delete(0, "end")
        logger.info("Quick-added event #%d", event.event_id)
        self.refresh()

    def _view_selected(self) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo("View", "Select an event first.")
            return
        EventDetailDialog(self.frame.winfo_toplevel(), e)

    def _new(self) -> None:
        EventDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh,
                     actor=self.actor)

    def _edit_selected(self) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo("Edit", "Select an event first.")
            return
        EventDialog(self.frame.winfo_toplevel(),
                     existing=e, on_save=self.refresh,
                     actor=self.actor)

    def _duplicate_selected(self) -> None:
        """Open the New Event dialog pre-filled from the selected
        event — how next year's version of anything starts."""
        e = self._selected()
        if e is None:
            messagebox.showinfo("Duplicate", "Select an event first.")
            return
        EventDialog(self.frame.winfo_toplevel(),
                     existing=None, template=e,
                     on_save=self.refresh, actor=self.actor)

    def _status_selected(self) -> None:
        e = self._selected()
        if e is None:
            messagebox.showinfo("Status", "Select an event first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), e,
                       on_save=self.refresh)

    def _quick_status(self, new_status: str) -> None:
        """Set the selected event(s) — plural: a snow day is twenty
        cancellations, not twenty dialogs."""
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo(new_status,
                                  "Select at least one event.")
            return
        what = (f"#{ids[0]}" if len(ids) == 1
                else f"{len(ids)} events")
        if not messagebox.askyesno(new_status,
                                     f"Set {what} → {new_status}?"):
            return
        errors: list[str] = []
        for eid in ids:
            before = data.get_event(eid)
            try:
                after = governance.audited_set_status(
                    eid, new_status, actor=self.actor)
            except ValidationError as ex:
                errors.append(f"#{eid}: {ex}")
                continue
            if (new_status == "Cancelled" and before is not None
                    and before.status != "Cancelled"):
                try:
                    notifications.notify_cancellation(after)
                except Exception:       # pragma: no cover - defensive
                    logger.debug("Cancellation notice failed",
                                  exc_info=True)
        if errors:
            messagebox.showerror(new_status, "\n".join(errors))
        self.refresh()

    def _archive_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Archive",
                                  "Select at least one event.")
            return
        what = (f"event #{ids[0]}" if len(ids) == 1
                else f"{len(ids)} events")
        if not messagebox.askyesno(
                "Archive",
                f"Archive {what}? Recoverable from the Archive "
                "tab."):
            return
        for eid in ids:
            try:
                governance.audited_archive(eid, actor=self.actor)
            except Exception as ex:
                messagebox.showerror("Archive failed",
                                       f"#{eid}: {ex}")
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
            f"Archived           : {summ.archived}",
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
        if summ.by_department:
            lines.append("")
            lines.append("By department:")
            for dept in sorted(summ.by_department):
                lines.append(
                    f"  {dept:<20} : {summ.by_department[dept]}")
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
        grab_when_viewable(self.win)
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
                 on_save: Callable[[], None],
                 template: Event | None = None,
                 actor: str | None = None) -> None:
        self.existing = existing
        # A template pre-fills a *new* event from an old one
        # (Duplicate); saving creates rather than updates.
        self.template = template if existing is None else None
        self.on_save = on_save
        self.actor = actor
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Event" if existing else "New Event")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    @property
    def _fill(self) -> Event | None:
        """What pre-fills the fields: the row being edited, or the
        row being duplicated."""
        return self.existing or self.template

    def _build(self) -> None:
        ex = self._fill
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.title_e = ttk.Entry(form, width=44)
        if ex:
            self.title_e.insert(0, ex.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=EVENT_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(ex.event_type if ex else DEFAULT_EVENT_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Audience:").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.audience_cb = ttk.Combobox(form, values=AUDIENCES,
                                           state="readonly", width=14)
        self.audience_cb.set(ex.audience if ex else DEFAULT_AUDIENCE)
        self.audience_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (ex.start_date if ex else _today()))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="End date:").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (ex.end_date if ex else ""))
        self.end_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        self.allday_var = tk.BooleanVar(
            value=(ex.all_day if ex else False))
        ttk.Checkbutton(form, text="All day",
                          variable=self.allday_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=4)

        r += 1
        ttk.Label(form, text="Start time:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.stime_e = ttk.Entry(form, width=10)
        if ex and ex.start_time:
            self.stime_e.insert(0, ex.start_time[:5])
        self.stime_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="End time:").grid(row=r, column=2,
                                                  sticky="e", pady=4)
        self.etime_e = ttk.Entry(form, width=10)
        if ex and ex.end_time:
            self.etime_e.insert(0, ex.end_time[:5])
        self.etime_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Location:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.location_e = ttk.Entry(form, width=44)
        if ex and ex.location:
            self.location_e.insert(0, ex.location)
        self.location_e.grid(row=r, column=1, columnspan=3,
                                sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Organiser:").grid(row=r, column=0,
                                                   sticky="e", pady=4)
        self.organiser_e = ttk.Entry(form, width=30)
        if ex and ex.organiser:
            self.organiser_e.insert(0, ex.organiser)
        self.organiser_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Status:").grid(row=r, column=2,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        # A duplicate starts life Scheduled regardless of what the
        # original had got to.
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Department:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.dept_cb = ttk.Combobox(
            form, values=[""] + taxonomy.list_departments(),
            width=18)
        if ex and ex.department:
            self.dept_cb.set(ex.department)
        self.dept_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Visibility:").grid(row=r, column=2,
                                                    sticky="e", pady=4)
        self.vis_cb = ttk.Combobox(form, values=VISIBILITIES,
                                      state="readonly", width=14)
        self.vis_cb.set(ex.visibility if ex else DEFAULT_VISIBILITY)
        self.vis_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Capacity:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.cap_e = ttk.Entry(form, width=10)
        if ex and ex.capacity is not None:
            self.cap_e.insert(0, str(ex.capacity))
        self.cap_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Cost:").grid(row=r, column=2,
                                              sticky="e", pady=4)
        self.cost_e = ttk.Entry(form, width=10)
        if ex and ex.cost is not None:
            self.cost_e.insert(0, f"{ex.cost:.2f}")
        self.cost_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        self.rsvp_var = tk.BooleanVar(
            value=(ex.rsvp_required if ex else False))
        ttk.Checkbutton(form, text="RSVP required",
                          variable=self.rsvp_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=4)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=4)
        self.desc_t = tk.Text(form, width=60, height=4)
        if ex and ex.description:
            self.desc_t.insert("1.0", ex.description)
        self.desc_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=60, height=3)
        if ex and ex.notes:
            self.notes_t.insert("1.0", ex.notes)
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
            "department":    self.dept_cb.get().strip() or None,
            "visibility":    self.vis_cb.get(),
            "capacity":      self.cap_e.get().strip() or None,
            "cost":          self.cost_e.get().strip() or None,
            "rsvp_required": self.rsvp_var.get(),
            "description":   self.desc_t.get("1.0", "end").strip()
                              or None,
            "notes":         self.notes_t.get("1.0", "end").strip()
                              or None,
        }

    def _warnings(self, payload: dict) -> list[str]:
        """What the clash and term checks have to say. A checker
        blowing up must never block a save — it reports nothing."""
        out: list[str] = []
        exclude = (self.existing.event_id if self.existing else None)
        try:
            from education_system.systems.sixth_form.domain.academics.calendar import (  # noqa: E501
                calendar_clashes as clashes,
            )
            out.extend(c.label for c in
                        clashes.check(payload,
                                       exclude_event_id=exclude
                                       ).clashes)
        except ValidationError:
            raise
        except Exception:                   # pragma: no cover - defensive
            logger.debug("Clash check unavailable", exc_info=True)
        try:
            from education_system.systems.sixth_form.domain.academics.calendar import (  # noqa: E501
                calendar_terms as terms,
            )
            out.extend(w.label for w in
                        terms.check(payload,
                                     exclude_event_id=exclude
                                     ).warnings)
        except ValidationError:
            raise
        except Exception:                   # pragma: no cover - defensive
            logger.debug("Term check unavailable", exc_info=True)
        return out

    def _save(self) -> None:
        try:
            payload = self._collect()
            warnings = self._warnings(payload)
            if warnings:
                listing = "\n".join(f"• {w}" for w in warnings[:8])
                if len(warnings) > 8:
                    listing += f"\n… and {len(warnings) - 8} more"
                if not messagebox.askyesno(
                        "Check before saving",
                        f"{listing}\n\nSave anyway?",
                        parent=self.win):
                    return
            if self.existing:
                before = data.get_event(self.existing.event_id)
                after = governance.audited_update(
                    self.existing.event_id, payload,
                    actor=self.actor)
                if before is not None:
                    try:
                        notifications.notify_change(before, after)
                    except Exception:   # pragma: no cover - defensive
                        logger.debug("Change notice failed",
                                      exc_info=True)
            else:
                governance.audited_create(payload, actor=self.actor)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
