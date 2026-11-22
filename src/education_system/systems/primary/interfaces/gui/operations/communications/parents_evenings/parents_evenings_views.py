"""Tkinter views for Primary School Parents' Evenings."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from typing import Callable
from education_system.systems.primary.domain.operations.communications.parents_evenings import parents_evenings
from education_system.systems.primary.domain.staff import staff
from education_system.systems.primary.domain.operations.communications.parents_evenings import parents_evenings as data
from education_system.systems.primary.domain.staff import staff as staff_data
from education_system.systems.primary.domain import _pupils_bridge as student_data
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.primary.interfaces.gui import kit
from education_system.systems.primary.domain.operations.communications.parents_evenings.parents_evenings import (
    BOOKING_STATUSES,
    Booking,
    DEFAULT_BOOKING_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_YEAR_GROUP,
    EVENT_STATUSES,
    Event,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_parents_evenings_window(parent=None) -> None:
    data.init_db()
    kit.show_page(parent, "Parents' Evenings",
                  lambda frame: _draw_parents_evenings(frame, parent))


def _draw_parents_evenings(parent: ttk.Frame, host=None) -> None:
    kit.page_heading(parent, "Parents' Evenings",
                     "Set up evenings, book pupils' parents into staff slots and see "
                     "each teacher's or pupil's schedule.")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    events_tab = EventsTab(nb)
    bookings_tab = BookingsTab(nb, events_tab)
    ScheduleTab(nb)
    SummaryTab(nb)
    events_tab.on_change = bookings_tab.refresh_events


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _staff_options(active_only: bool = True) -> list[tuple[str, str]]:
    rows = sorted(
        staff_data.list_staff(active_only=active_only),
        key=lambda s: (s.last_name, s.first_name))
    return [(t.staff_id,
              f"{t.staff_id} — {t.full_name} ({t.role})")
            for t in rows]


# An event's year group ("Year 3") → the pupil year group ("3"), so a
# booking for a one-year evening lists that year's pupils first.
_EVENT_YEAR_TO_PUPIL = {label: code for code, label in kit.YEAR_GROUP_LABELS.items()}

_EVENING_HOURS = range(7, 22)


def _parent_name_choices(student_id: str) -> list[str]:
    """The pupil's parent contacts' names (primary contact first)."""
    if not student_id:
        return []
    try:
        from education_system.systems.primary.domain.operations.communications.parent_contacts import (
            parent_contacts as pc,
        )
        return [c.full_name for c in pc.contacts_for_student(student_id)]
    except Exception:  # noqa: BLE001 - the name can still be typed
        logger.debug("parent contacts lookup failed", exc_info=True)
        return []


def _student_names() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def _staff_names() -> dict[str, str]:
    return {t.staff_id: t.full_name for t in staff_data.list_staff()}


# ══ Events tab ═════════════════════════════════════════════════════

class EventsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Events")
        self.on_change: Callable[[], None] | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = kit.ChoiceField(bar, tk.StringVar(), choices=YEAR_GROUPS, blank=True,
                                      width=12)
        self.f_year.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = kit.ChoiceField(bar, tk.StringVar(), choices=EVENT_STATUSES,
                                        blank=True, width=20)
        self.f_status.pack(side="left", padx=(2, 10))
        self.f_open = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Open only", variable=self.f_open,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "time", "name", "year", "location",
                "slot", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "date": 100, "time": 110, "name": 280,
                  "year": 80, "location": 180, "slot": 70, "status": 160}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())
        self.tree.tag_configure("Cancelled", foreground="#888")
        self.tree.tag_configure("Open", background="#e6f7e0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_year.set("")
        self.f_status.set("")
        self.f_open.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_events(
                year_group=self.f_year.get() or None,
                status=self.f_status.get() or None,
                open_only=self.f_open.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for e in rows:
            tags = []
            if e.status == "Cancelled":
                tags.append("Cancelled")
            elif e.status == "Open for Booking":
                tags.append("Open")
            self.tree.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, e.event_date,
                f"{e.start_time}-{e.end_time}", e.name, e.year_group,
                e.location or "—", e.slot_minutes, e.status,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} event(s).")
        self._build_actions()
        if self.on_change:
            self.on_change()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("View", "Select an event first.")
            return
        event = data.get_event(eid)
        if event is None:
            return
        summ = data.summarize_event(eid)
        lines = [
            f"Event       : #{event.event_id}",
            f"Name        : {event.name}",
            f"Date        : {event.event_date}",
            f"Time        : {event.start_time} – {event.end_time}",
            f"Slot length : {event.slot_minutes} min "
            f"({summ.total_slots} slots/staff)",
            f"Year group  : {event.year_group}",
            f"Location    : {event.location or '—'}",
            f"Status      : {event.status}",
            "",
            f"Booked      : {summ.booked}",
            f"Attended    : {summ.attended}",
            f"No-Show     : {summ.no_shows}",
            f"Cancelled   : {summ.cancelled}",
            f"Students    : {summ.distinct_students}",
            f"Staff       : {summ.distinct_staff}",
            f"Fill rate   : "
            f"{summ.fill_rate if summ.fill_rate is not None else '—'}%",
            "",
            "Notes:",
            event.notes or "  —",
        ]
        messagebox.showinfo(f"Event #{event.event_id}", "\n".join(lines))

    def _new(self) -> None:
        EventDialog(self.frame.winfo_toplevel(), existing=None,
                     on_save=self.refresh)

    def _edit_selected(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("Edit", "Select an event first.")
            return
        event = data.get_event(eid)
        if event is None:
            return
        EventDialog(self.frame.winfo_toplevel(), existing=event,
                     on_save=self.refresh)

    def _status_selected(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("Status", "Select an event first.")
            return
        event = data.get_event(eid)
        if event is None:
            return
        StatusDialog(self.frame.winfo_toplevel(),
                      title=f"Event #{eid} status",
                      current=event.status, options=list(EVENT_STATUSES),
                      on_save=lambda s:
                          self._save_status(eid, s))

    def _save_status(self, eid: int, status: str) -> None:
        try:
            data.set_event_status(eid, status)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("Delete", "Select an event first.")
            return
        event = data.get_event(eid)
        if event is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete event #{eid} ({event.name})?\n\n"
                f"This will delete all bookings for the event."):
            return
        try:
            data.delete_event(eid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class EventDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Event | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title("Edit Event" if existing else "New Event")
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form, footer = kit.scrolled_form(self.win)
        r = 0
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.name_e = ttk.Entry(form, width=40)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Date:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.date_e = kit.DateField(
            form, tk.StringVar(value=self.existing.event_date if self.existing
                               else _date.today().isoformat()))
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Year group:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.year_cb = kit.ChoiceField(
            form, tk.StringVar(value=self.existing.year_group if self.existing
                               else DEFAULT_YEAR_GROUP),
            choices=YEAR_GROUPS, width=14)
        self.year_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Location:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.loc_e = ttk.Entry(form, width=40)
        self.loc_e.insert(0, (self.existing.location or "")
                              if self.existing else "Main Hall")
        self.loc_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Start time:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        self.start_e = kit.TimeField(
            form, tk.StringVar(value=self.existing.start_time if self.existing
                               else "17:00"), hours=_EVENING_HOURS)
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="End time:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.end_e = kit.TimeField(
            form, tk.StringVar(value=self.existing.end_time if self.existing
                               else "20:00"), hours=_EVENING_HOURS)
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Slot length (min):").grid(row=r, column=0,
                                                          sticky="e", pady=3)
        self.slot_e = kit.NumberField(
            form, tk.StringVar(value=str(self.existing.slot_minutes
                                         if self.existing else 10)),
            from_=5, to=60, increment=5, width=6)
        self.slot_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = kit.ChoiceField(
            form, tk.StringVar(value=self.existing.status if self.existing
                               else DEFAULT_EVENT_STATUS),
            choices=EVENT_STATUSES, width=22)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.notes_text = tk.Text(form, width=50, height=4, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Button(footer, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save", command=self._save).pack(side="right")

    def _save(self) -> None:
        payload = {
            "name":         self.name_e.get().strip(),
            "event_date":   self.date_e.get().strip(),
            "year_group":   self.year_cb.get(),
            "location":     self.loc_e.get().strip(),
            "start_time":   self.start_e.get().strip(),
            "end_time":     self.end_e.get().strip(),
            "slot_minutes": self.slot_e.get().strip(),
            "status":       self.status_cb.get(),
            "notes":        self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_event(self.existing.event_id, payload)
            else:
                data.create_event(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e), parent=self.win)
            return
        except Exception as e:
            logger.exception("save event failed")
            messagebox.showerror("Save failed", str(e), parent=self.win)
            return
        self.win.destroy()
        self.on_save()


class StatusDialog:
    def __init__(self, parent: tk.Misc, *,
                 title: str, current: str, options: list[str],
                 on_save: Callable[[str], None]) -> None:
        self.on_save = on_save
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title(title)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = kit.ChoiceField(form, tk.StringVar(value=current), choices=options,
                                  width=22)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.cb.get()
        self.win.destroy()
        self.on_save(v)


# ══ Bookings tab ═══════════════════════════════════════════════════

class BookingsTab:
    def __init__(self, nb: ttk.Notebook, events_tab: EventsTab) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Bookings")
        self._build()
        self.refresh_events()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Event:").pack(side="left")
        self.event_cb = ttk.Combobox(bar, state="readonly", width=60)
        self.event_cb.pack(side="left", padx=(2, 10))
        self.event_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self.refresh())
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = kit.ChoiceField(bar, tk.StringVar(), choices=BOOKING_STATUSES,
                                        blank=True, width=14,
                                        on_change=lambda _v: self.refresh())
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "slot", "student", "student_name", "staff",
                "staff_name", "parent", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "slot": 70, "student": 90,
                  "student_name": 180, "staff": 90,
                  "staff_name": 180, "parent": 160, "status": 100}
        headings = {"id": "#", "slot": "Slot", "student": "Student",
                    "student_name": "Student name",
                    "staff": "Staff", "staff_name": "Staff name",
                    "parent": "Parent", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Cancelled", foreground="#888")
        self.tree.tag_configure("No-Show", background="#ffe0e0")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def refresh_events(self) -> None:
        events = data.list_events()
        self._event_ids = [e.event_id for e in events]
        labels = [f"#{e.event_id}  {e.event_date}  {e.name}  "
                   f"({e.status})" for e in events]
        cur_id = self._selected_event_id()
        self.event_cb["values"] = labels
        if labels:
            if cur_id is not None and cur_id in self._event_ids:
                self.event_cb.current(self._event_ids.index(cur_id))
            else:
                self.event_cb.current(0)
        else:
            self.event_cb.set("")
        self.refresh()

    def _selected_event_id(self) -> int | None:
        idx = self.event_cb.current()
        if idx < 0 or idx >= len(self._event_ids):
            return None
        return self._event_ids[idx]

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        eid = self._selected_event_id()
        if eid is None:
            self.count_var.set("(no events)")
            self._build_actions()
            return
        try:
            rows = data.list_bookings(
                event_id=eid,
                status=self.f_status.get() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        sn = _student_names()
        tn = _staff_names()
        for b in rows:
            tags = (b.status,) if b.status in (
                "Cancelled", "No-Show") else ()
            self.tree.insert("", "end", iid=str(b.booking_id), values=(
                b.booking_id, b.slot_time, b.student_id,
                sn.get(b.student_id, "?"),
                b.staff_id, tn.get(b.staff_id, "?"),
                b.parent_name or "—", b.status,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} booking(s) for event #{eid}.")
        self._build_actions()

    def _selected_booking(self) -> Booking | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return data.get_booking(int(sel[0]))

    def _new(self) -> None:
        eid = self._selected_event_id()
        if eid is None:
            messagebox.showinfo("New", "Pick an event first.")
            return
        event = data.get_event(eid)
        if event is None:
            return
        BookingDialog(self.frame.winfo_toplevel(),
                       event=event, existing=None,
                       on_save=self.refresh)

    def _edit_selected(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("Edit", "Select a booking first.")
            return
        event = data.get_event(b.event_id)
        if event is None:
            return
        BookingDialog(self.frame.winfo_toplevel(),
                       event=event, existing=b,
                       on_save=self.refresh)

    def _status_selected(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("Status", "Select a booking first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                      title=f"Booking #{b.booking_id} status",
                      current=b.status, options=list(BOOKING_STATUSES),
                      on_save=lambda s:
                          self._save_status(b.booking_id, s))

    def _save_status(self, bid: int, status: str) -> None:
        try:
            data.set_booking_status(bid, status)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("Delete", "Select a booking first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete booking #{b.booking_id}?"):
            return
        try:
            data.delete_booking(b.booking_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class BookingDialog:
    def __init__(self, parent: tk.Misc, *,
                 event: Event, existing: Booking | None,
                 on_save: Callable[[], None]) -> None:
        self.event = event
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title("Edit Booking" if existing else "New Booking")
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form, footer = kit.scrolled_form(self.win)
        r = 0
        ttk.Label(form,
                   text=f"Event #{self.event.event_id}  {self.event.name}  "
                        f"({self.event.event_date} "
                        f"{self.event.start_time}-{self.event.end_time})"
                   ).grid(row=r, column=0, columnspan=2,
                            sticky="w", pady=(0, 8))
        r += 1

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        if self.existing:
            self.student_cb = None
            self._student_id = self.existing.student_id
            names = _student_names()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                            f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            self.student_var = tk.StringVar()
            self.student_cb = kit.PupilPicker(
                form, self.student_var,
                year_group=_EVENT_YEAR_TO_PUPIL.get(self.event.year_group))
            self.student_cb.bind_change(lambda _v: self._refresh_parents())
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Staff:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        if self.existing:
            self.staff_cb = None
            self._staff_id = self.existing.staff_id
            tnames = _staff_names()
            ttk.Label(form,
                       text=f"{self._staff_id} — "
                            f"{tnames.get(self._staff_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            self.staff_var = tk.StringVar()
            self.staff_cb = kit.StaffPicker(form, self.staff_var)
            self.staff_cb.bind_change(lambda _v: self._refresh_slots())
            self.staff_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Slot:").grid(row=r, column=0,
                                             sticky="e", pady=3)
        self.slot_var = tk.StringVar()
        self.slot_cb = kit.ChoiceField(form, self.slot_var, width=10)
        self.slot_cb.grid(row=r, column=1, sticky="w", padx=6)
        self.slot_note = ttk.Label(form, text="", foreground="#888")
        self.slot_note.grid(row=r, column=2, sticky="w")
        r += 1
        self._refresh_slots()

        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = kit.ChoiceField(
            form, tk.StringVar(value=self.existing.status if self.existing
                               else DEFAULT_BOOKING_STATUS),
            choices=BOOKING_STATUSES, width=14)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Parent name:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        # The pupil's parent contacts to pick from; still typeable.
        self.parent_e = kit.ChoiceField(
            form, tk.StringVar(value=(self.existing.parent_name or "")
                               if self.existing else ""),
            choices=_parent_name_choices(self.existing.student_id
                                         if self.existing else ""),
            blank=True, editable=True, width=40)
        self.parent_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.notes_text = tk.Text(form, width=50, height=4, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Button(footer, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save", command=self._save).pack(side="right")

    def _refresh_parents(self) -> None:
        names = _parent_name_choices(self.student_var.get())
        self.parent_e.set_choices(names)
        if names and not self.parent_e.get():
            self.parent_e.set(names[0])

    def _refresh_slots(self) -> None:
        if self.existing:
            slots = data.event_slots(self.event)
            self.slot_cb.set_choices(slots)
            if self.existing.slot_time in slots:
                self.slot_cb.set(self.existing.slot_time)
            elif slots:
                self.slot_cb.set(slots[0])
            return
        stid = self.staff_var.get() if self.staff_cb else ""
        if not stid:
            self.slot_cb.set_choices([])
            self.slot_cb.set("")
            self.slot_note.configure(text="pick a member of staff first")
            return
        free = data.free_slots_for_staff(self.event.event_id, stid)
        self.slot_cb.set_choices(free)
        self.slot_cb.set(free[0] if free else "")
        self.slot_note.configure(
            text=f"{len(free)} free slot(s)" if free else "no free slots for this teacher")

    def _save(self) -> None:
        if self.student_cb is not None:
            sid = self.student_var.get()
            if not sid:
                messagebox.showerror("Validation", "Pick a student.", parent=self.win)
                return
        else:
            sid = self._student_id
        if self.staff_cb is not None:
            stid = self.staff_var.get()
            if not stid:
                messagebox.showerror("Validation", "Pick a staff member.", parent=self.win)
                return
        else:
            stid = self._staff_id
        slot = self.slot_cb.get().strip()
        if not slot:
            messagebox.showerror("Validation", "Pick a slot.", parent=self.win)
            return
        payload = {
            "student_id":  sid,
            "staff_id":    stid,
            "slot_time":   slot,
            "status":      self.status_cb.get(),
            "parent_name": self.parent_e.get().strip(),
            "notes":       self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_booking(self.existing.booking_id, payload)
            else:
                data.create_booking(self.event.event_id, payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e), parent=self.win)
            return
        except Exception as e:
            logger.exception("save booking failed")
            messagebox.showerror("Save failed", str(e), parent=self.win)
            return
        self.win.destroy()
        self.on_save()


# ══ Schedule tab ═══════════════════════════════════════════════════

class ScheduleTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Schedules")
        self._build()
        self.refresh_events()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Event:").pack(side="left")
        self.event_cb = ttk.Combobox(bar, state="readonly", width=60)
        self.event_cb.pack(side="left", padx=6)
        ttk.Label(bar, text="View:").pack(side="left", padx=(10, 2))
        self.mode_cb = ttk.Combobox(bar,
                                       values=("Staff", "Student"),
                                       state="readonly", width=10)
        self.mode_cb.current(0)
        self.mode_cb.pack(side="left", padx=2)
        self.mode_cb.bind("<<ComboboxSelected>>",
                            lambda _e: self._switch_mode())
        ttk.Label(bar, text="Pick:").pack(side="left", padx=(10, 2))
        self.target_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.target_cb.pack(side="left", padx=2)
        ttk.Button(bar, text="Load",
                    command=self._load).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh_events).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("slot", "with_id", "with_name", "parent", "status", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for c, w in zip(cols, (80, 100, 220, 180, 110, 400)):
            self.tree.heading(c, text=c.replace("_", " ").capitalize())
            self.tree.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("FREE", foreground="#888888",
                                  background="#f5f5f5")
        self.tree.tag_configure("Cancelled", foreground="#888")

        self.info_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.info_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh_events(self) -> None:
        events = data.list_events()
        self._event_ids = [e.event_id for e in events]
        labels = [f"#{e.event_id}  {e.event_date}  {e.name}"
                   for e in events]
        self.event_cb["values"] = labels
        if labels:
            self.event_cb.current(0)
        self._switch_mode()

    def _switch_mode(self) -> None:
        mode = self.mode_cb.get()
        if mode == "Staff":
            opts = _staff_options(active_only=True)
        else:
            opts = _student_options()
        self._target_ids = [s for s, _ in opts]
        self.target_cb["values"] = [l for _, l in opts]
        if opts:
            self.target_cb.current(0)

    def _selected_event(self) -> Event | None:
        idx = self.event_cb.current()
        if idx < 0 or idx >= len(self._event_ids):
            return None
        return data.get_event(self._event_ids[idx])

    def _load(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        event = self._selected_event()
        if event is None:
            self.info_var.set("(no events)")
            return
        i = self.target_cb.current()
        if i < 0:
            return
        target_id = self._target_ids[i]
        mode = self.mode_cb.get()
        sn = _student_names()
        tn = _staff_names()
        if mode == "Staff":
            bookings = {b.slot_time: b
                         for b in data.staff_schedule(event.event_id,
                                                        target_id)}
            self.info_var.set(
                f"Staff {target_id} — {tn.get(target_id, '?')}  "
                f"({event.name}, {event.event_date})")
            for slot in data.event_slots(event):
                b = bookings.get(slot)
                if b:
                    self.tree.insert("", "end", values=(
                        slot, b.student_id,
                        sn.get(b.student_id, "?"),
                        b.parent_name or "—", b.status,
                        (b.notes or "").replace("\n", " ⏎ "),
                    ), tags=(b.status,) if b.status == "Cancelled" else ())
                else:
                    self.tree.insert("", "end", values=(
                        slot, "—", "(free)", "", "", ""
                    ), tags=("FREE",))
        else:
            bookings = data.student_schedule(event.event_id, target_id)
            self.info_var.set(
                f"Student {target_id} — {sn.get(target_id, '?')}  "
                f"({event.name}, {event.event_date})")
            for b in sorted(bookings, key=lambda x: x.slot_time):
                self.tree.insert("", "end", values=(
                    b.slot_time, b.staff_id,
                    tn.get(b.staff_id, "?"),
                    b.parent_name or "—", b.status,
                    (b.notes or "").replace("\n", " ⏎ "),
                ), tags=(b.status,) if b.status == "Cancelled" else ())


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def refresh(self) -> None:
        summ = data.summary()
        L: list[str] = []
        L.append("Events")
        L.append("------")
        L.append(f"  Total events     : {summ.total_events}")
        L.append(f"  Upcoming events  : {summ.upcoming_events}")
        L.append(f"  Open for booking : {summ.open_for_booking}")
        L.append(f"  Completed        : {summ.completed}")
        if summ.next_event:
            e = summ.next_event
            L.append("")
            L.append(f"  Next: #{e.event_id}  {e.event_date} "
                      f"{e.start_time}-{e.end_time}  {e.name} "
                      f"({e.status})")
        L.append("")
        L.append("Bookings")
        L.append("--------")
        L.append(f"  Total : {summ.total_bookings}")
        L.append("")
        L.append("By event status")
        L.append("---------------")
        for s in EVENT_STATUSES:
            n = summ.by_event_status.get(s, 0)
            if n:
                L.append(f"  {s:<22} : {n}")
        L.append("")
        L.append("By booking status")
        L.append("-----------------")
        for s in BOOKING_STATUSES:
            n = summ.by_booking_status.get(s, 0)
            if n:
                L.append(f"  {s:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
