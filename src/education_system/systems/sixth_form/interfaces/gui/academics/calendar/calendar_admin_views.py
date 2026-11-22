"""Admin tabs for the Sixth Form Calendar GUI: bookings, trips,
series, the notification queue, the audit trail and the archive.

Sibling to :mod:`calendar_views`, which mounts these. Each tab fronts
one of the calendar's data modules; none of them re-implements a rule
that lives in a module. The import graph stays one-way — this module
never imports the main view.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as data,
    calendar_bookings as bookings,
    calendar_governance as governance,
    calendar_notifications as notifications,
    calendar_recurrence as recurrence,
    calendar_trips as trips,
)
from education_system.systems.sixth_form.domain.academics.calendar.calendar import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def add_tabs(nb: ttk.Notebook, *, actor: str | None = None,
             role: str | None = None) -> None:
    BookingsTab(nb, actor=actor)
    TripsTab(nb)
    SeriesTab(nb, actor=actor)
    QueueTab(nb)
    AuditTab(nb)
    ArchiveTab(nb, actor=actor, role=role)


def _pick_event_bar(parent: ttk.Frame, on_apply) -> ttk.Entry:
    """The 'Event #' entry every per-event tab starts with."""
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(bar, text="Event #:").pack(side="left")
    entry = ttk.Entry(bar, width=8)
    entry.pack(side="left", padx=(2, 8))
    ttk.Button(bar, text="Load", command=on_apply).pack(side="left")
    entry.bind("<Return>", lambda _e: on_apply())
    return entry


# ══ Bookings tab ═══════════════════════════════════════════════════

class BookingsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 actor: str | None = None) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Bookings")
        self.actor = actor
        self.event_e = _pick_event_bar(self.frame, self.refresh)

        self.summary_var = tk.StringVar(
            value="Enter an event number.")
        ttk.Label(self.frame, textvariable=self.summary_var,
                  font=("", 10, "bold"),
                  anchor="w").pack(fill="x", padx=8)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("person", "name", "state", "booked_at")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, text, width in (("person", "ID", 110),
                               ("name", "Name", 220),
                               ("state", "State", 110),
                               ("booked_at", "Booked", 170)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, anchor="w")
        self.tree.tag_configure("Waitlisted", background="#fff7d0")
        self.tree.tag_configure("Cancelled", background="#eeeeee")
        self.tree.tag_configure("Attended", background="#e2f2e2")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="Book…",
                   command=self._book).pack(side="left")
        ttk.Button(actions, text="Cancel booking",
                   command=self._cancel).pack(side="left", padx=4)
        ttk.Button(actions, text="Check in",
                   command=self._check_in).pack(side="left", padx=4)
        ttk.Button(actions, text="Promote waitlist",
                   command=self._promote).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                   command=self.refresh).pack(side="right")

    def _event_id(self) -> int | None:
        raw = self.event_e.get().strip().lstrip("#")
        if not raw.isdigit():
            messagebox.showinfo("Bookings",
                                "Enter an event number first.")
            return None
        return int(raw)

    def _selected_person(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Bookings", "Select a booking first.")
            return None
        return str(self.tree.item(sel[0], "values")[0])

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        event_id = self._event_id()
        if event_id is None:
            return
        event = data.get_event(event_id)
        if event is None:
            self.summary_var.set(f"No event #{event_id}.")
            return
        try:
            summ = bookings.booking_summary(event_id)
        except ValidationError as e:
            self.summary_var.set(str(e))
            return
        self.summary_var.set(
            f"#{event_id} {event.title} — {summ.label}")
        for b in bookings.attendance_list(event_id):
            self.tree.insert("", "end", values=(
                b.person, b.person_name or "—", b.state,
                b.booked_at or "—"),
                tags=(b.state,))

    def _book(self) -> None:
        event_id = self._event_id()
        if event_id is None:
            return
        person = simpledialog.askstring(
            "Book", "Person ID (student id or username):",
            parent=self.frame.winfo_toplevel())
        if not person:
            return
        name = simpledialog.askstring(
            "Book", "Display name (optional):",
            parent=self.frame.winfo_toplevel())
        try:
            got = bookings.book(event_id, person, person_name=name)
        except ValidationError as e:
            messagebox.showerror("Book", str(e))
            return
        if got.state == bookings.WAITLISTED:
            messagebox.showinfo(
                "Book", f"{person} is on the waiting list — the "
                        "event is full.")
        self.refresh()

    def _cancel(self) -> None:
        event_id = self._event_id()
        person = self._selected_person()
        if event_id is None or person is None:
            return
        try:
            bookings.cancel(event_id, person)
        except ValidationError as e:
            messagebox.showerror("Cancel", str(e))
            return
        self.refresh()

    def _check_in(self) -> None:
        event_id = self._event_id()
        person = self._selected_person()
        if event_id is None or person is None:
            return
        try:
            bookings.check_in(event_id, person)
        except ValidationError as e:
            messagebox.showerror("Check in", str(e))
            return
        self.refresh()

    def _promote(self) -> None:
        event_id = self._event_id()
        if event_id is None:
            return
        try:
            got = bookings.promote_waitlist(event_id)
        except ValidationError as e:
            messagebox.showerror("Promote", str(e))
            return
        messagebox.showinfo("Promote",
                            f"{len(got)} promoted from the waitlist.")
        self.refresh()


# ══ Trips tab ══════════════════════════════════════════════════════

class TripsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Trips")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Edit record…",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Readiness",
                   command=self._readiness).pack(side="left", padx=4)
        ttk.Button(bar, text="Publish to finance…",
                   command=self._publish).pack(side="left", padx=4)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("id", "date", "title", "ra", "staff", "transport",
                "finance")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, text, width in (
                ("id", "ID", 50), ("date", "Date", 170),
                ("title", "Trip", 280), ("ra", "Risk assessment", 140),
                ("staff", "Staff", 60), ("transport", "Transport", 110),
                ("finance", "Finance", 80)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for e in data.list_events(event_type="Trip",
                                  upcoming_only=True):
            detail = trips.get_detail(e.event_id)
            if detail is None:
                ra, staff, transport, fin = "— none —", "—", "—", "—"
            else:
                ra = (detail.risk_assessment_ref or "(missing)") + \
                    (" ✓" if detail.risk_assessment_ok else " ✗")
                staff = str(detail.staff_count)
                transport = detail.transport
                fin = (f"#{detail.finance_trip_id}"
                       if detail.finance_trip_id else "—")
            date = (e.start_date if not e.is_multiday
                    else f"{e.start_date} → {e.end_date}")
            self.tree.insert("", "end", iid=str(e.event_id),
                             values=(e.event_id, date, e.title, ra,
                                     staff, transport, fin))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Trips", "Select a trip first.")
            return None
        return int(sel[0])

    def _edit(self) -> None:
        event_id = self._selected()
        if event_id is None:
            return
        TripDetailDialog(self.frame.winfo_toplevel(), event_id,
                         on_save=self.refresh)

    def _readiness(self) -> None:
        event_id = self._selected()
        if event_id is None:
            return
        try:
            report = trips.readiness(event_id)
        except ValidationError as e:
            messagebox.showerror("Readiness", str(e))
            return
        icon = "✓ " if report.ready else ""
        messagebox.showinfo("Readiness",
                            icon + report.summary)

    def _publish(self) -> None:
        event_id = self._selected()
        if event_id is None:
            return
        deposit = simpledialog.askfloat(
            "Publish", "Deposit per place (0 for none):",
            parent=self.frame.winfo_toplevel(), minvalue=0.0)
        if deposit is None:
            return
        try:
            detail = trips.publish_to_finance(event_id,
                                              deposit=deposit)
        except ValidationError as e:
            messagebox.showerror("Publish", str(e))
            return
        messagebox.showinfo(
            "Publish", f"Linked to finance trip "
                       f"#{detail.finance_trip_id}.")
        self.refresh()


class TripDetailDialog:
    def __init__(self, parent: tk.Misc, event_id: int,
                 on_save) -> None:
        self.event_id = event_id
        self.on_save = on_save
        self.existing = trips.get_detail(event_id)
        self.win = tk.Toplevel(parent)
        self.win.title(f"Trip record — event #{event_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ex = self.existing

        r = 0
        ttk.Label(form, text="Risk assessment ref:").grid(
            row=r, column=0, sticky="e", pady=3)
        self.ra_e = ttk.Entry(form, width=24)
        if ex and ex.risk_assessment_ref:
            self.ra_e.insert(0, ex.risk_assessment_ref)
        self.ra_e.grid(row=r, column=1, sticky="w", padx=6)
        self.ra_ok_var = tk.BooleanVar(
            value=bool(ex and ex.risk_assessment_ok))
        ttk.Checkbutton(form, text="Signed off",
                        variable=self.ra_ok_var).grid(
            row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="Students per staff:").grid(
            row=r, column=0, sticky="e", pady=3)
        self.ratio_e = ttk.Entry(form, width=6)
        self.ratio_e.insert(0, str(ex.ratio_students if ex
                                   else trips.DEFAULT_RATIO))
        self.ratio_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Staff going:").grid(
            row=r, column=2, sticky="e")
        self.staff_e = ttk.Entry(form, width=6)
        self.staff_e.insert(0, str(ex.staff_count if ex else 0))
        self.staff_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Transport:").grid(
            row=r, column=0, sticky="e", pady=3)
        self.transport_cb = ttk.Combobox(
            form, values=trips.TRANSPORT_MODES, state="readonly",
            width=18)
        self.transport_cb.set(ex.transport if ex
                              else trips.DEFAULT_TRANSPORT)
        self.transport_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Emergency contact:").grid(
            row=r, column=0, sticky="e", pady=3)
        self.contact_e = ttk.Entry(form, width=34)
        if ex and ex.emergency_contact:
            self.contact_e.insert(0, ex.emergency_contact)
        self.contact_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="First aider:").grid(
            row=r, column=0, sticky="e", pady=3)
        self.aider_e = ttk.Entry(form, width=24)
        if ex and ex.first_aider:
            self.aider_e.insert(0, ex.first_aider)
        self.aider_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                            sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=44, height=3)
        if ex and ex.notes:
            self.notes_t.insert("1.0", ex.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                          sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(10, 0))
        ttk.Button(bar, text="Save",
                   command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                   command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            trips.set_detail(self.event_id, {
                "risk_assessment_ref": self.ra_e.get(),
                "risk_assessment_ok": self.ra_ok_var.get(),
                "ratio_students": self.ratio_e.get(),
                "staff_count": self.staff_e.get(),
                "transport": self.transport_cb.get(),
                "emergency_contact": self.contact_e.get(),
                "first_aider": self.aider_e.get(),
                "notes": self.notes_t.get("1.0", "end").strip(),
            })
        except ValidationError as e:
            messagebox.showerror("Trip record", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Series tab ═════════════════════════════════════════════════════

class SeriesTab:
    def __init__(self, nb: ttk.Notebook, *,
                 actor: str | None = None) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Series")
        self.actor = actor
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Sync selected",
                   command=self._sync).pack(side="left", padx=4)
        ttk.Button(bar, text="Sweep all",
                   command=self._sweep).pack(side="left", padx=4)
        ttk.Button(bar, text="Skip a date…",
                   command=self._add_exception).pack(side="left",
                                                     padx=4)
        ttk.Button(bar, text="Deactivate",
                   command=self._deactivate).pack(side="left", padx=4)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("id", "title", "rule", "from", "until", "active")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, text, width in (
                ("id", "ID", 50), ("title", "Title", 260),
                ("rule", "Rule", 240), ("from", "From", 100),
                ("until", "Until", 100), ("active", "Active", 60)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for s in recurrence.list_series(active_only=False):
            self.tree.insert("", "end", iid=str(s.series_id),
                             values=(s.series_id, s.title,
                                     s.rule_label, s.start_date,
                                     s.until_date or "—",
                                     "yes" if s.active else "no"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Series", "Select a series first.")
            return None
        return int(sel[0])

    def _sync(self) -> None:
        series_id = self._selected()
        if series_id is None:
            return
        try:
            got = recurrence.sync(series_id, actor=self.actor)
        except ValidationError as e:
            messagebox.showerror("Sync", str(e))
            return
        messagebox.showinfo("Sync", got.summary)
        self.refresh()

    def _sweep(self) -> None:
        got = recurrence.sweep(actor=self.actor)
        messagebox.showinfo("Sweep", got.summary)
        self.refresh()

    def _add_exception(self) -> None:
        series_id = self._selected()
        if series_id is None:
            return
        date = simpledialog.askstring(
            "Skip a date", "Date to skip (YYYY-MM-DD):",
            parent=self.frame.winfo_toplevel())
        if not date:
            return
        reason = simpledialog.askstring(
            "Skip a date", "Reason (optional):",
            parent=self.frame.winfo_toplevel())
        try:
            recurrence.add_exception(series_id, date.strip(),
                                     reason=reason,
                                     actor=self.actor)
        except ValidationError as e:
            messagebox.showerror("Skip a date", str(e))
            return
        self.refresh()

    def _deactivate(self) -> None:
        series_id = self._selected()
        if series_id is None:
            return
        if not messagebox.askyesno(
                "Deactivate",
                "Retire this series and archive its future "
                "occurrences?"):
            return
        try:
            n = recurrence.deactivate_series(series_id,
                                             actor=self.actor)
        except ValidationError as e:
            messagebox.showerror("Deactivate", str(e))
            return
        messagebox.showinfo("Deactivate",
                            f"{n} future occurrence(s) archived.")
        self.refresh()


# ══ Queue tab ══════════════════════════════════════════════════════

class QueueTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Messages")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="State:").pack(side="left")
        self.state_cb = ttk.Combobox(
            bar, values=("",) + notifications.STATES,
            state="readonly", width=10)
        self.state_cb.set(notifications.QUEUED)
        self.state_cb.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Sweep reminders",
                   command=self._sweep).pack(side="left", padx=(12, 2))
        ttk.Button(bar, text="Queue week ahead",
                   command=self._digest).pack(side="left", padx=2)
        ttk.Button(bar, text="Send queued",
                   command=self._drain).pack(side="left", padx=2)
        ttk.Button(bar, text="Cancel message",
                   command=self._cancel).pack(side="left", padx=2)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("id", "kind", "recipient", "subject", "state",
                "queued")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, text, width in (
                ("id", "ID", 50), ("kind", "Kind", 130),
                ("recipient", "To", 180), ("subject", "Subject", 300),
                ("state", "State", 80), ("queued", "Queued", 150)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, anchor="w")
        self.tree.tag_configure("Failed", background="#ffd0d0")
        self.tree.tag_configure("Sent", background="#e2f2e2")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._preview)

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = notifications.list_notifications(
            state=self.state_cb.get() or None)
        for n in rows:
            self.tree.insert("", "end", iid=str(n.notification_id),
                             values=(n.notification_id, n.kind,
                                     n.recipient, n.subject,
                                     n.state, n.queued_at or "—"),
                             tags=(n.state,))

    def _preview(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        n = notifications.get_notification(int(sel[0]))
        if n is None:
            return
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(f"Message #{n.notification_id}")
        win.transient(self.frame.winfo_toplevel())
        box = ttk.Frame(win, padding=12)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text=n.subject,
                  font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(box, text=f"To: {n.recipient}   ({n.state})",
                  foreground="#555").pack(anchor="w", pady=(0, 6))
        t = tk.Text(box, width=64, height=14, wrap="word")
        t.insert("1.0", n.body)
        if n.detail:
            t.insert("end", f"\n\n--- {n.detail}")
        t.configure(state="disabled")
        t.pack(fill="both", expand=True)
        ttk.Button(box, text="Close",
                   command=win.destroy).pack(pady=(8, 0))

    def _sweep(self) -> None:
        n = notifications.sweep_reminders()
        messagebox.showinfo("Reminders", f"{n} reminder(s) queued.")
        self.refresh()

    def _digest(self) -> None:
        n = notifications.queue_week_ahead()
        messagebox.showinfo("Week ahead", f"{n} digest(s) queued.")
        self.refresh()

    def _drain(self) -> None:
        sent, failed = notifications.send_queued()
        messagebox.showinfo(
            "Send", f"{sent} sent, {failed} failed. Broadcast "
                    "(audience:…) rows stay queued.")
        self.refresh()

    def _cancel(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Cancel", "Select a message first.")
            return
        if notifications.cancel_notification(int(sel[0])):
            self.refresh()
        else:
            messagebox.showinfo("Cancel",
                                "Only queued messages can be "
                                "cancelled.")


# ══ Audit tab ══════════════════════════════════════════════════════

class AuditTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Audit")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Event # (blank = all):").pack(
            side="left")
        self.event_e = ttk.Entry(bar, width=8)
        self.event_e.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="By:").pack(side="left")
        self.actor_e = ttk.Entry(bar, width=14)
        self.actor_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left")

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("when", "event", "action", "change", "by", "reason")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, text, width in (
                ("when", "When", 150), ("event", "Event", 60),
                ("action", "Action", 80), ("change", "Change", 340),
                ("by", "By", 100), ("reason", "Reason", 160)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        raw = self.event_e.get().strip().lstrip("#")
        if raw.isdigit():
            rows = governance.trail(int(raw))
        else:
            rows = governance.recent_activity(
                actor=self.actor_e.get().strip() or None)
        for a in rows:
            change = (f"{a.field}: {a.old_value or '—'} → "
                      f"{a.new_value or '—'}" if a.field
                      else (a.new_value or a.old_value or "—"))
            self.tree.insert("", "end", values=(
                a.amended_at or "—", f"#{a.event_id}", a.action,
                change, a.amended_by or "—", a.reason or ""))


# ══ Archive tab ════════════════════════════════════════════════════

class ArchiveTab:
    def __init__(self, nb: ttk.Notebook, *,
                 actor: str | None = None,
                 role: str | None = None) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Archive")
        self.actor = actor
        self.role = role
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Restore",
                   command=self._restore).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete forever",
                   command=self._purge).pack(side="left", padx=4)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        cols = ("id", "date", "type", "title", "archived")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, text, width in (
                ("id", "ID", 50), ("date", "Date", 170),
                ("type", "Type", 130), ("title", "Title", 320),
                ("archived", "Archived", 160)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, anchor="w")
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
        rows = governance.list_archived()
        for e in rows:
            date = (e.start_date if not e.is_multiday
                    else f"{e.start_date} → {e.end_date}")
            self.tree.insert("", "end", iid=str(e.event_id),
                             values=(e.event_id, date, e.event_type,
                                     e.title, e.deleted_at or "—"))
        self.count_var.set(f"{len(rows)} archived event(s).")

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Archive", "Select an event first.")
            return None
        return int(sel[0])

    def _restore(self) -> None:
        event_id = self._selected()
        if event_id is None:
            return
        try:
            governance.audited_restore(event_id, actor=self.actor,
                                       role=self.role)
        except ValidationError as e:
            messagebox.showerror("Restore", str(e))
            return
        self.refresh()

    def _purge(self) -> None:
        event_id = self._selected()
        if event_id is None:
            return
        if not messagebox.askyesno(
                "Delete forever",
                f"Permanently delete event #{event_id}? There is "
                "no undo."):
            return
        reason = simpledialog.askstring(
            "Delete forever", "Reason (for the audit trail):",
            parent=self.frame.winfo_toplevel())
        try:
            governance.audited_purge(event_id, actor=self.actor,
                                     role=self.role, reason=reason)
        except ValidationError as e:
            messagebox.showerror("Delete forever", str(e))
            return
        self.refresh()
