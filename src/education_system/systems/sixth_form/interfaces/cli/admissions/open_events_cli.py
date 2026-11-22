"""CLI: open events — events, bookings, attendance, follow-up and turning
a booking into an application."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    open_events as oe,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _run_submenu,
    _UserAbort,
    _yes,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.entry_requirements_cli import (
    _user,
)


def _pick_event(include_cancelled: bool = False) -> oe.OpenEvent:
    rows = oe.list_events(include_cancelled=include_cancelled)
    if not rows:
        print("    No events.")
        raise _UserAbort
    label = _pick_from("Event", [f"{e.event_id}: {e.label}" for e in rows])
    return oe.get_event(int(label.split(":")[0]))


def _pick_booking(event_id: int | None = None, rows=None) -> oe.Booking:
    rows = rows if rows is not None else oe.list_bookings(event_id)
    if not rows:
        print("    No bookings.")
        raise _UserAbort
    label = _pick_from("Booking", [
        f"{b.booking_id}: {b.prospective_name} ({b.current_school or '—'}) "
        f"attended={'?' if b.attended is None else ('yes' if b.attended else 'no')}"
        f" follow-up={b.follow_up_status}"
        + (f" → {b.applicant_id}" if b.applicant_id else "") for b in rows])
    return oe.get_booking(int(label.split(":")[0]))


def _try(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except ValueError as e:
        print(f"  ✗ {e}")
        return None


def list_events_flow() -> None:
    print("\n═══ Open events ═══")
    for s in oe.all_event_stats():
        e = s.event
        print(f"  {e.event_id:>3}  {e.label:<48} [{e.status}] booked "
              f"{s.bookings} ({s.people} people), attended {s.attended}, "
              f"applied {s.applied}")
    _pause()


def _event_form(old: oe.OpenEvent | None = None) -> dict:
    g = (lambda k: str(getattr(old, k) or "")) if old else (lambda k: "")
    return {
        "title": _input("Title", default=g("title"), allow_empty=False),
        "event_type": _pick_from("Type", list(oe.EVENT_TYPES),
                                 default=g("event_type") or "Open Evening"),
        "event_date": _input("Date (YYYY-MM-DD)", default=g("event_date"),
                             allow_empty=False),
        "start_time": _input("Start (HH:MM)", default=g("start_time")),
        "end_time": _input("End (HH:MM)", default=g("end_time")),
        "venue": _input("Venue", default=g("venue")),
        "capacity": _input("Capacity (blank = unlimited)",
                           default=g("capacity")),
        "description": _input("Description", default=g("description")),
    }


def create_event_flow() -> None:
    e = _try(oe.create_event, _event_form(), created_by=_user())
    if e:
        print(f"  ✓ Created {e.label}")
    _pause()


def edit_event_flow() -> None:
    old = _pick_event()
    d = _event_form(old)
    d["status"] = _pick_from("Status", list(oe.EVENT_STATUSES),
                             default=old.status)
    if _try(oe.update_event, old.event_id, d):
        print("  ✓ Saved")
    _pause()


def cancel_event_flow() -> None:
    e = _pick_event()
    if _yes(f"Cancel {e.label}?") and _try(oe.cancel_event, e.event_id):
        print("  ✓ Cancelled")
    _pause()


def book_flow() -> None:
    e = _pick_event()
    left = oe.places_left(e.event_id)
    print(f"  Places left: {'unlimited' if left is None else left}")
    parent = _yes("Booked by a parent/carer?")
    d = {"attendee_name": _input("Name", allow_empty=False),
         "is_parent": parent,
         "student_name": _input("Student's name", allow_empty=not parent)
         if parent else "",
         "email": _input("Email"), "phone": _input("Phone"),
         "current_school": _input("Current school"),
         "year_group": _input("Year group", default="Year 11"),
         "interests": _input("Subjects of interest (comma separated)"),
         "party_size": _input("Party size", default="1"),
         "notes": _input("Notes")}
    b = _try(oe.book, e.event_id, d)
    if b:
        print(f"  ✓ Booking #{b.booking_id}")
    _pause()


def bookings_flow() -> None:
    e = _pick_event(include_cancelled=True)
    for b in oe.list_bookings(e.event_id):
        print(f"  #{b.booking_id:<4} {b.prospective_name:<26} "
              f"{(b.current_school or '')[:20]:<20} x{b.party_size} "
              f"attended={'?' if b.attended is None else b.attended} "
              f"{b.follow_up_status} {b.applicant_id or ''}")
    _pause()


def attendance_flow() -> None:
    e = _pick_event(include_cancelled=True)
    for b in oe.list_bookings(e.event_id):
        ans = _input(f"{b.prospective_name} attended? (y/n/blank = skip)",
                     default="").lower()
        if ans in ("y", "yes", "n", "no"):
            oe.mark_attendance(b.booking_id, ans.startswith("y"))
    print("  ✓ Attendance saved")
    _pause()


def follow_up_flow() -> None:
    due = oe.follow_up_due()
    print(f"\n  {len(due)} attendee(s) awaiting follow-up")
    b = _pick_booking(rows=due)
    subject, body = oe.render_follow_up(b.booking_id)
    print(f"\n  To: {b.email or '(no email)'}\n  Subject: {subject}\n\n{body}")
    status = _pick_from("Mark follow-up as", list(oe.FOLLOW_UP_STATUSES),
                        default="Sent")
    _try(oe.mark_follow_up, b.booking_id, status)
    _pause()


def create_application_flow() -> None:
    b = _pick_booking(rows=oe.list_bookings(attended_only=True,
                                            not_applied_only=True))
    payload = oe.application_payload(b.booking_id)
    print("  Pre-filled from the booking; complete the rest.")
    over = {}
    for key, label in (("first_name", "First name"), ("last_name", "Last name"),
                       ("dob", "Date of birth (YYYY-MM-DD)"),
                       ("email", "Email"), ("phone", "Phone"),
                       ("subject_1", "Subject 1"), ("subject_2", "Subject 2"),
                       ("subject_3", "Subject 3")):
        over[key] = _input(label, default=str(payload.get(key) or "")) or None
    res = _try(oe.create_application, b.booking_id, over)
    if res:
        a, created = res
        print(f"  ✓ {'Created' if created else 'Linked existing'} applicant "
              f"{a.applicant_id}")
    _pause()


def link_flow() -> None:
    b = _pick_booking(rows=oe.list_bookings(not_applied_only=True))
    a = _pick_applicant()
    if _try(oe.link_to_applicant, b.booking_id, a.applicant_id):
        print("  ✓ Linked")
    _pause()


def stats_flow() -> None:
    print("\n═══ Open event conversion ═══")
    for s in oe.all_event_stats():
        print(f"  {s.event.label:<48} attended {s.attended}/{s.bookings}, "
              f"no-shows {s.no_shows}, applied {s.applied} "
              f"({s.conversion}%)")
    print("\n  Interests: " + ", ".join(f"{k} {v}" for k, v in
                                       oe.interest_counts()[:15]))
    print("  Schools:   " + ", ".join(f"{k} {v}" for k, v in
                                       oe.school_counts()[:15]))
    _pause()


MENU = [
    ("List events", list_events_flow),
    ("Create event", create_event_flow),
    ("Edit event", edit_event_flow),
    ("Cancel event", cancel_event_flow),
    ("─" * 6, lambda: None),
    ("Book a place", book_flow),
    ("Bookings for an event", bookings_flow),
    ("Take attendance", attendance_flow),
    ("─" * 6, lambda: None),
    ("Follow up attendees", follow_up_flow),
    ("Create application from a booking", create_application_flow),
    ("Link booking to an existing applicant", link_flow),
    ("Conversion statistics", stats_flow),
]


def run() -> None:
    _run_submenu("Open Events", MENU)
