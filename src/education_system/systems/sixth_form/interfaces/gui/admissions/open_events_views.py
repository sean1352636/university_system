"""Open Events tab: events, bookings, attendance, follow-up, applications."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.admissions import (
    open_events as oe,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

from . import applicant_actions as act

logger = logging.getLogger(__name__)

_EVENT_FIELDS = [
    ("title", "Title", "entry", None),
    ("event_type", "Type", "readonly", oe.EVENT_TYPES),
    ("event_date", "Date (YYYY-MM-DD)", "entry", None),
    ("start_time", "Start (HH:MM)", "entry", None),
    ("end_time", "End (HH:MM)", "entry", None),
    ("venue", "Venue", "entry", None),
    ("capacity", "Capacity (people)", "entry", None),
    ("status", "Status", "readonly", oe.EVENT_STATUSES),
    ("description", "Description", "text", None),
]
_BOOKING_FIELDS = [
    ("attendee_name", "Booked by (name)", "entry", None),
    ("is_parent", "Parent / carer booking", "check", None),
    ("student_name", "Student's name (parent booking)", "entry", None),
    ("email", "Email", "entry", None),
    ("phone", "Phone", "entry", None),
    ("current_school", "Current school", "entry", None),
    ("year_group", "Year group", "combo", ("Year 10", "Year 11", "Year 12",
                                           "Other")),
    ("interests", "Interests (comma-separated subjects)", "entry", None),
    ("party_size", "Party size", "entry", None),
    ("notes", "Notes", "text", None),
]


class OpenEventsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Open Events")
        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)

        ebar = ttk.Frame(left)
        ebar.pack(fill="x", pady=(0, 4))
        ttk.Button(ebar, text="New event…", command=self._new_event).pack(
            side="left")
        ttk.Button(ebar, text="Edit…", command=self._edit_event).pack(
            side="left", padx=4)
        ttk.Button(ebar, text="Cancel event",
                   command=self._cancel_event).pack(side="left")
        ttk.Button(ebar, text="Delete", command=self._delete_event).pack(
            side="left", padx=4)
        self.upcoming = tk.BooleanVar(value=False)
        ttk.Checkbutton(ebar, text="Upcoming only", variable=self.upcoming,
                        command=self.refresh).pack(side="left", padx=6)
        ebar2 = ttk.Frame(left)
        ebar2.pack(fill="x", pady=(0, 4))
        ttk.Button(ebar2, text="Interests report",
                   command=self._interests).pack(side="left")
        ttk.Button(ebar2, text="Schools report",
                   command=self._schools).pack(side="left", padx=4)
        ttk.Button(ebar2, text="Refresh", command=self.refresh).pack(
            side="right")
        self.etree = ui.make_tree(left, [
            ("date", "Date", 90), ("title", "Event", 200),
            ("status", "Status", 80), ("booked", "Booked", 60),
            ("attended", "Came", 50), ("applied", "Applied", 60),
            ("conv", "Conv %", 60)], height=18)
        self.etree.bind("<<TreeviewSelect>>", lambda _e: self._load_bookings())

        self.event_info = tk.StringVar(value="Select an event.")
        ttk.Label(right, textvariable=self.event_info,
                  font=("", 11, "bold")).pack(fill="x", pady=(0, 4))
        bbar = ttk.Frame(right)
        bbar.pack(fill="x", pady=(0, 2))
        ttk.Button(bbar, text="Book…", command=self._book).pack(side="left")
        ttk.Button(bbar, text="Edit…", command=self._edit_booking).pack(
            side="left", padx=4)
        ttk.Button(bbar, text="Cancel booking",
                   command=self._cancel_booking).pack(side="left")
        ttk.Button(bbar, text="Attended",
                   command=lambda: self._attend(True)).pack(side="left",
                                                            padx=(12, 4))
        ttk.Button(bbar, text="No-show",
                   command=lambda: self._attend(False)).pack(side="left")
        ttk.Button(bbar, text="Unmark",
                   command=lambda: self._attend(None)).pack(side="left",
                                                            padx=4)
        bbar2 = ttk.Frame(right)
        bbar2.pack(fill="x", pady=(0, 4))
        ttk.Button(bbar2, text="Follow-up email…",
                   command=self._follow_up).pack(side="left")
        ttk.Button(bbar2, text="Follow-ups due",
                   command=self._follow_ups_due).pack(side="left", padx=4)
        ttk.Button(bbar2, text="Create application…",
                   command=self._create_application).pack(side="left",
                                                          padx=(12, 4))
        ttk.Button(bbar2, text="Link to applicant…",
                   command=self._link).pack(side="left")
        self.btree = ui.make_tree(right, [
            ("name", "Booked by", 150), ("student", "Student", 130),
            ("school", "School", 130), ("interests", "Interests", 180),
            ("n", "Party", 45), ("attended", "Attended", 70),
            ("follow", "Follow-up", 80), ("applicant", "Applicant", 85)],
            height=18)
        self.btree.tag_configure("came", background="#d8f4d8")
        self.btree.tag_configure("noshow", background="#ffd6d6")
        self.refresh()

    # ── Events ──
    def _event_id(self) -> int | None:
        iid = ui.selected_iid(self.etree)
        return int(iid) if iid else None

    def refresh(self) -> None:
        keep = self._event_id()
        ui.clear(self.etree)
        try:
            events = oe.list_events(upcoming_only=self.upcoming.get())
        except Exception as e:  # noqa: BLE001
            logger.exception("Open events failed to load")
            self.event_info.set(f"Error: {e}")
            return
        for e in events:
            s = oe.event_stats(e.event_id)
            self.etree.insert("", "end", iid=str(e.event_id), values=(
                e.event_date, e.title, e.status, s.people, s.attended,
                s.applied, f"{s.conversion:g}"))
        if keep and self.etree.exists(str(keep)):
            self.etree.selection_set(str(keep))
        self._load_bookings()

    def _new_event(self) -> None:
        if ui.ask_form(self.frame, "New open event", _EVENT_FIELDS,
                       {"event_type": "Open Evening", "status": "Scheduled",
                        "event_date": _dt.date.today().isoformat()},
                       on_submit=lambda v: oe.create_event(
                           v, created_by=ui.current_username())):
            self.refresh()

    def _edit_event(self) -> None:
        eid = self._event_id()
        e = oe.get_event(eid) if eid else None
        if e is None:
            messagebox.showinfo("Open events", "Select an event first.",
                                parent=self.frame)
            return
        if ui.ask_form(self.frame, "Edit open event", _EVENT_FIELDS,
                       vars(e), on_submit=lambda v: oe.update_event(eid, v)):
            self.refresh()

    def _cancel_event(self) -> None:
        eid = self._event_id()
        if eid and messagebox.askyesno("Open events", "Cancel this event?",
                                       parent=self.frame):
            try:
                oe.cancel_event(eid)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Open events", str(e), parent=self.frame)
            self.refresh()

    def _delete_event(self) -> None:
        eid = self._event_id()
        if eid and messagebox.askyesno(
                "Open events", "Delete this event AND all its bookings?",
                parent=self.frame):
            ok, _ = act.attempt(self.frame, "Open events", oe.delete_event, eid)
            if ok:
                self.refresh()

    def _interests(self) -> None:
        rows = oe.interest_counts(self._event_id())
        ui.show_text(self.frame, "Subject interests", "\n".join(
            f"{n:>4}  {s}" for s, n in rows) or "(no bookings)")

    def _schools(self) -> None:
        rows = oe.school_counts(self._event_id())
        ui.show_text(self.frame, "Schools", "\n".join(
            f"{n:>4}  {s}" for s, n in rows) or "(no bookings)")

    # ── Bookings ──
    def _load_bookings(self) -> None:
        ui.clear(self.btree)
        eid = self._event_id()
        if not eid:
            self.event_info.set("Select an event.")
            return
        e = oe.get_event(eid)
        if e is None:
            return
        left = oe.places_left(eid)
        self.event_info.set(
            f"{e.label} · {e.venue or 'venue TBC'} · "
            f"{oe.places_taken(eid)} booked"
            + (f" · {left} left" if left is not None else ""))
        for b in oe.list_bookings(eid):
            tag = ("came",) if b.attended else (
                ("noshow",) if b.attended is False else ())
            self.btree.insert("", "end", iid=str(b.booking_id), values=(
                b.attendee_name + (" (parent)" if b.is_parent else ""),
                b.student_name or "", b.current_school or "",
                b.interests or "", b.party_size,
                {True: "Yes", False: "No", None: ""}[b.attended],
                b.follow_up_status, b.applicant_id or ""), tags=tag)

    def _bid(self) -> int | None:
        iid = ui.require_iid(self.btree, "Bookings")
        return int(iid) if iid else None

    def _book(self) -> None:
        eid = self._event_id()
        if not eid:
            messagebox.showinfo("Bookings", "Select an event first.",
                                parent=self.frame)
            return
        if ui.ask_form(self.frame, "New booking", _BOOKING_FIELDS,
                       {"party_size": 1, "year_group": "Year 11"},
                       on_submit=lambda v: oe.book(eid, v)):
            self.refresh()

    def _edit_booking(self) -> None:
        bid = self._bid()
        b = oe.get_booking(bid) if bid else None
        if b and ui.ask_form(self.frame, "Edit booking", _BOOKING_FIELDS,
                             vars(b),
                             on_submit=lambda v: oe.update_booking(bid, v)):
            self.refresh()

    def _cancel_booking(self) -> None:
        bid = self._bid()
        if bid and messagebox.askyesno("Bookings", "Cancel this booking?",
                                       parent=self.frame):
            ok, _ = act.attempt(self.frame, "Bookings", oe.cancel_booking, bid)
            if ok:
                self.refresh()

    def _attend(self, attended: bool | None) -> None:
        sel = self.btree.selection()
        if not sel:
            messagebox.showinfo("Bookings", "Select booking(s) first.",
                                parent=self.frame)
            return
        problems = []
        for iid in sel:
            try:
                oe.mark_attendance(int(iid), attended)
            except Exception as e:  # noqa: BLE001 — reported per booking
                problems.append(f"#{iid}: {act.describe(e)}")
        if problems:
            messagebox.showerror("Bookings", "Not updated:\n"
                                 + "\n".join(problems), parent=self.frame)
        self.refresh()

    def _follow_up(self) -> None:
        bid = self._bid()
        if not bid:
            return
        subject, body = oe.render_follow_up(bid)
        ui.show_text(self.frame, subject, f"Subject: {subject}\n\n{body}")
        if messagebox.askyesno("Follow-up", "Mark the follow-up as sent?",
                               parent=self.frame):
            ok, _ = act.attempt(self.frame, "Follow-up", oe.mark_follow_up,
                                bid, "Sent")
            if ok:
                self.refresh()

    def _follow_ups_due(self) -> None:
        rows = oe.follow_up_due(self._event_id())
        ui.show_text(self.frame, "Follow-ups due", "\n".join(
            f"#{b.booking_id}  {b.attendee_name}  {b.email or b.phone or ''}"
            f"  ({'attended' if b.attended else 'no-show'})"
            for b in rows) or "Nobody is waiting for a follow-up.")

    def _create_application(self) -> None:
        bid = self._bid()
        if not bid:
            return
        pre = oe.application_payload(bid)
        fields = [
            ("first_name", "First name", "entry", None),
            ("last_name", "Last name", "entry", None),
            ("dob", "Date of birth (YYYY-MM-DD)", "entry", None),
            ("email", "Applicant email", "entry", None),
            ("phone", "Phone", "entry", None),
            ("previous_school", "Current school", "entry", None),
            ("predicted_gcses", "Predicted GCSEs", "entry", None),
            ("subject_1", "Subject 1", "entry", None),
            ("subject_2", "Subject 2", "entry", None),
            ("subject_3", "Subject 3", "entry", None),
        ]
        result: dict = {}

        def save(v: dict) -> None:
            a, created = oe.create_application(bid, v)
            result.update(a=a, created=created)

        if ui.ask_form(self.frame, "Create application from booking",
                       fields, pre, on_submit=save):
            a = result["a"]
            messagebox.showinfo(
                "Application", (f"Created applicant {a.applicant_id}."
                                if result["created"] else
                                f"Already an applicant — linked to "
                                f"{a.applicant_id} ({a.full_name})."),
                parent=self.frame)
            self.refresh()

    def _link(self) -> None:
        bid = self._bid()
        if not bid:
            return
        aid = ui.pick_applicant(self.frame, "Link booking to applicant")
        if aid:
            ok, _ = act.attempt(self.frame, "Link booking",
                                oe.link_to_applicant, bid, aid)
            if ok:
                self.refresh()


def open_open_events_window(parent=None) -> None:
    win = ui.new_window(parent, "Open events")
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    OpenEventsTab(nb)
