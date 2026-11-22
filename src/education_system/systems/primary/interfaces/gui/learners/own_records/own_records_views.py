"""Student and parent screens for the Primary School System (Tk).

Each screen is drawn in the content area. All data comes from
``domain/learners/own_records``, which takes identity from ``host.auth`` and
re-checks it on every read; nothing here holds a pupil id it did not get from
that layer.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.platform.cross_system.own_record_access import (
    NoRecordLink,
    OwnRecordError,
)
from education_system.platform.delivery.gui.own_record_page import (
    LOAD_FAILED,
    child_picker,
    show_message,
    show_table,
)
from education_system.systems.primary.domain.learners.own_records import own_records as data
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)


def guarded_page(host: Any, title: str, draw: Callable[[ttk.Frame], None]) -> None:
    """Show an own-record page in the content area (or a pop-out window).

    As the platform's ``guarded_page``: a refused or unlinked record shows its
    message and nothing else. Every time the page is drawn - including when it
    is popped out - the read layer re-checks the signed-in user."""
    def page(parent: ttk.Frame) -> None:
        kit.page_heading(parent, title)
        body = ttk.Frame(parent)
        body.pack(fill="both", expand=True)
        try:
            draw(body)
        except OwnRecordError as refused:
            for widget in body.winfo_children():
                widget.destroy()
            show_message(body, str(refused))
        except Exception:
            logger.exception("Own-record page %s failed", title)
            for widget in body.winfo_children():
                widget.destroy()
            show_message(body, LOAD_FAILED)
    kit.show_page(host, title, page)


def _redraw_child(area: ttk.Frame, draw_child: Callable[[ttk.Frame, str], None],
                  pupil_id: str) -> None:
    """Draw one child's part of a page again in place (after a save)."""
    for widget in area.winfo_children():
        widget.destroy()
    try:
        draw_child(area, pupil_id)
    except OwnRecordError as refused:
        for widget in area.winfo_children():
            widget.destroy()
        show_message(area, str(refused))
    except Exception:
        logger.exception("Own-record redraw failed")
        for widget in area.winfo_children():
            widget.destroy()
        show_message(area, LOAD_FAILED)


# ── Students ───────────────────────────────────────────────────────

def open_timetable(host: Any) -> None:
    def draw(body: ttk.Frame) -> None:
        pupil = data.my_pupil(host.auth)
        ttk.Label(body, text=f"{pupil.name}, Year {pupil.year_group}").pack(anchor="w")
        show_table(body, [("Day", 70), ("Period", 60), ("Start", 70), ("End", 70),
                          ("Subject", 240), ("Room", 120), ("Teacher", 200)],
                   [(r.day, r.period, r.start_time, r.end_time, r.subject, r.room, r.teacher)
                    for r in data.timetable(host.auth)],
                   empty="No timetable has been set for your year or class yet.")
    guarded_page(host, "My Timetable", draw)


def open_homework(host: Any) -> None:
    def draw(body: ttk.Frame) -> None:
        rows = data.homework(host.auth)
        tree = show_table(
            body, [("Due", 90), ("Set", 90), ("Subject", 150), ("Title", 300),
                   ("Status", 90), ("Grade", 60), ("Mark %", 60)],
            [(r.due_date, r.set_date, r.subject, r.title, r.status, r.grade, r.mark_pct)
             for r in rows],
            empty="No homework has been set for your year or class.", height=12)
        if tree is None:
            return
        detail = tk.Text(body, height=8, wrap="word", state="disabled")
        detail.pack(fill="x")

        def show(_event=None) -> None:
            selected = tree.selection()
            if not selected:
                return
            row = rows[int(selected[0])]
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", f"What to do:\n{row.instructions or 'No instructions given.'}"
                                 f"\n\nFeedback:\n{row.feedback or 'None yet.'}")
            detail.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", show)
    guarded_page(host, "My Homework", draw)


def open_reading_log(host: Any) -> None:
    def draw(body: ttk.Frame) -> None:
        current, history = data.reading_log(host.auth)
        if current is not None:
            ttk.Label(body, text=f"Current book band: {current.band} ({current.status})",
                      font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))
        show_table(body, [("Date", 110), ("Band", 150), ("Status", 110), ("Book", 400)],
                   [(h.assessed_on, h.band, h.status, h.book_title) for h in history],
                   empty="No reading has been logged for you yet.")
    guarded_page(host, "My Reading Log", draw)


# ── Parents ────────────────────────────────────────────────────────

def _child_page(host: Any, title: str, draw_child: Callable[[ttk.Frame, str], None],
                pupil_id: str | None = None) -> None:
    """A page for one of this parent's own children, with a choice between them."""
    def draw(body: ttk.Frame) -> None:
        children = data.my_children(host.auth)
        if not children:
            raise NoRecordLink(
                "Your login is not linked to a child at this school, so no records can "
                "be shown. Please ask the school office to link your account.")
        chosen: list[str] = [pupil_id or children[0].pupil_id]
        area = ttk.Frame(body)

        def redraw(new_id: str | None = None) -> None:
            if new_id is not None:
                chosen[0] = new_id
            for widget in area.winfo_children():
                widget.destroy()
            try:
                draw_child(area, chosen[0])
            except OwnRecordError as refused:
                for widget in area.winfo_children():
                    widget.destroy()
                show_message(area, str(refused))

        child_picker(body, children, redraw)
        area.pack(fill="both", expand=True)
        redraw()
    guarded_page(host, title, draw)


def open_attendance(host: Any) -> None:
    def draw(area: ttk.Frame, pupil_id: str) -> None:
        s = data.attendance(host.auth, pupil_id)
        ttk.Label(area, font=("", 11, "bold"), text=(
            f"Attendance {s.attendance_pct}% of {s.total_sessions} sessions: "
            f"{s.present} present, {s.authorised_absent} authorised absence, "
            f"{s.unauthorised_absent} unauthorised absence")).pack(anchor="w", pady=(0, 6))
        show_table(area, [("Date", 110), ("Session", 80), ("Mark", 240)],
                   [(m.date, m.session, m.mark) for m in s.marks],
                   empty="No attendance has been recorded yet.")
    _child_page(host, "Child Attendance", draw)


def open_assessment(host: Any) -> None:
    def draw(area: ttk.Frame, pupil_id: str) -> None:
        show_table(area, [("Year", 90), ("Term", 90), ("Subject", 220), ("Grade", 70),
                          ("Score", 70), ("Assessed", 100)],
                   [(r.academic_year, r.term, r.subject, r.grade, r.score, r.assessed_on)
                    for r in data.assessment(host.auth, pupil_id)],
                   empty="No assessment has been recorded yet.")
    _child_page(host, "Child Assessment", draw)


def open_reports(host: Any) -> None:
    def draw(area: ttk.Frame, pupil_id: str) -> None:
        rows = data.reports(host.auth, pupil_id)
        tree = show_table(area, [("Year", 90), ("Term", 90), ("Published", 100),
                                 ("Headline", 460)],
                          [(r.academic_year, r.term, r.published_on, r.headline) for r in rows],
                          empty="No reports have been published yet.", height=6)
        if tree is None:
            return
        detail = tk.Text(area, height=16, wrap="word", state="disabled")
        detail.pack(fill="both", expand=True)

        def show(_event=None) -> None:
            selected = tree.selection()
            if not selected:
                return
            r = rows[int(selected[0])]
            parts = [("Summary", r.summary), ("Strengths", r.strengths),
                     ("Next steps", r.next_steps), ("Behaviour", r.behaviour),
                     ("Attendance", f"{r.attendance_pct}%" if r.attendance_pct is not None
                      else None)]
            text = "\n\n".join(f"{name}:\n{value}" for name, value in parts if value)
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", text or "This report has no detail.")
            detail.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", show)
        tree.selection_set("0")
    _child_page(host, "Child Reports", draw)


def _do_write(owner: tk.Misc, write: Callable[[], Any], then: Callable[[], None]) -> None:
    """Run a parent's write and report any refusal to them (over *owner*'s window)."""
    win = owner.winfo_toplevel()
    try:
        write()
    except (OwnRecordError, ValueError) as refused:
        messagebox.showerror("Not saved", str(refused), parent=win)
    except Exception:
        logger.exception("Own-record write failed")
        messagebox.showerror(
            "Not saved", "That could not be saved. Please try again, or contact the "
            "school office.", parent=win)
    then()


def open_consent(host: Any) -> None:
    def draw(area: ttk.Frame, pupil_id: str) -> None:
        win = area.winfo_toplevel()

        def redraw() -> None:
            _redraw_child(area, draw, pupil_id)

        ttk.Label(area, text="School consent forms", font=("", 11, "bold")).pack(anchor="w")
        answers = data.consent_answers(host.auth, pupil_id)
        tree = show_table(area, [("Form", 240), ("Your answer", 120), ("Date", 110)],
                          [(a.purpose, a.answer, a.answered_on) for a in answers],
                          empty="There are no consent forms.", height=5)

        def answer(give: bool) -> None:
            selected = tree.selection() if tree is not None else ()
            if not selected:
                messagebox.showinfo("Consent", "Please select a form first.", parent=win)
                return
            purpose = answers[int(selected[0])].purpose
            word = "give" if give else "not give"
            if messagebox.askyesno("Consent", f"{word.capitalize()} consent for {purpose}?",
                                   parent=win):
                _do_write(area, lambda: data.answer_consent(host.auth, pupil_id, purpose, give),
                          redraw)

        bar = ttk.Frame(area)
        bar.pack(fill="x", pady=(0, 12))
        ttk.Button(bar, text="Give consent", command=lambda: answer(True)).pack(side="left")
        ttk.Button(bar, text="Do not give consent",
                   command=lambda: answer(False)).pack(side="left", padx=6)

        ttk.Label(area, text="Trips", font=("", 11, "bold")).pack(anchor="w")
        trips = data.trip_consents(host.auth, pupil_id)
        trip_tree = show_table(
            area, [("Trip", 240), ("Destination", 200), ("Starts", 100), ("Ends", 100),
                   ("Consent", 90)],
            [(t.trip, t.destination, t.start_date, t.end_date,
              "Given" if t.consent_received else "Not given") for t in trips],
            empty="Your child is not booked on any upcoming trips.", height=5)
        if trip_tree is None:
            return

        def answer_trip(give: bool) -> None:
            selected = trip_tree.selection()
            if not selected:
                messagebox.showinfo("Consent", "Please select a trip first.", parent=win)
                return
            trip = trips[int(selected[0])]
            word = "give" if give else "not give"
            if messagebox.askyesno("Consent", f"{word.capitalize()} consent for {trip.trip}?",
                                   parent=win):
                _do_write(area, lambda: data.answer_trip_consent(
                    host.auth, pupil_id, trip.booking_id, give), redraw)

        trip_bar = ttk.Frame(area)
        trip_bar.pack(fill="x")
        ttk.Button(trip_bar, text="Give trip consent",
                   command=lambda: answer_trip(True)).pack(side="left")
        ttk.Button(trip_bar, text="Do not give trip consent",
                   command=lambda: answer_trip(False)).pack(side="left", padx=6)

    _child_page(host, "Consent Forms", draw)


def open_evening(host: Any) -> None:
    def draw(area: ttk.Frame, pupil_id: str) -> None:
        win = area.winfo_toplevel()

        def redraw() -> None:
            _redraw_child(area, draw, pupil_id)

        ttk.Label(area, text="Your bookings", font=("", 11, "bold")).pack(anchor="w")
        show_table(area, [("Evening", 240), ("Date", 110), ("Time", 70), ("Teacher", 220),
                          ("Status", 90)],
                   [(b.event, b.event_date, b.slot_time, b.teacher, b.status)
                    for b in data.evening_bookings(host.auth, pupil_id)],
                   empty="You have no bookings for this child.", height=5)

        ttk.Label(area, text="Book a slot", font=("", 11, "bold")).pack(anchor="w")
        events = data.evening_options(host.auth, pupil_id)
        teachers = data.evening_teachers(host.auth, pupil_id)
        if not events:
            show_message(area, "No parents' evening is open for booking at the moment.")
            return
        if not teachers:
            show_message(area, "No class teacher is recorded for your child's class yet, so "
                               "there is nobody to book with. Please contact the school office.")
            return
        form = ttk.Frame(area)
        form.pack(fill="x")
        ttk.Label(form, text="Evening:").grid(row=0, column=0, sticky="w", pady=2)
        event_box = ttk.Combobox(form, state="readonly", width=50, values=[
            f"{e.name}, {e.event_date} {e.start_time}-{e.end_time}" for e in events])
        event_box.grid(row=0, column=1, sticky="w", pady=2)
        event_box.current(0)
        ttk.Label(form, text="Teacher:").grid(row=1, column=0, sticky="w", pady=2)
        teacher_box = ttk.Combobox(form, state="readonly", width=50,
                                   values=[t.name for t in teachers])
        teacher_box.grid(row=1, column=1, sticky="w", pady=2)
        teacher_box.current(0)
        ttk.Label(form, text="Time:").grid(row=2, column=0, sticky="w", pady=2)
        slot_box = ttk.Combobox(form, state="readonly", width=12)
        slot_box.grid(row=2, column=1, sticky="w", pady=2)

        def load_slots(_event=None) -> None:
            try:
                slots = data.evening_slots(host.auth, pupil_id,
                                           events[event_box.current()].event_id,
                                           teachers[teacher_box.current()].staff_id)
            except OwnRecordError as refused:
                messagebox.showerror("Booking", str(refused), parent=win)
                slots = []
            slot_box.configure(values=slots)
            slot_box.set(slots[0] if slots else "")

        event_box.bind("<<ComboboxSelected>>", load_slots)
        teacher_box.bind("<<ComboboxSelected>>", load_slots)
        load_slots()

        def book() -> None:
            slot = slot_box.get()
            if not slot:
                messagebox.showinfo("Booking", "There are no free times for this teacher.",
                                    parent=win)
                return
            event = events[event_box.current()]
            teacher = teachers[teacher_box.current()]
            if messagebox.askyesno(
                    "Booking", f"Book {slot} with {teacher.name} at {event.name}?\n\n"
                    "To change a booking afterwards, please contact the school office.",
                    parent=win):
                _do_write(area, lambda: data.book_evening(
                    host.auth, pupil_id, event.event_id, teacher.staff_id, slot), redraw)

        ttk.Button(area, text="Book this slot", command=book).pack(anchor="w", pady=8)

    _child_page(host, "Parents' Evening Booking", draw)
