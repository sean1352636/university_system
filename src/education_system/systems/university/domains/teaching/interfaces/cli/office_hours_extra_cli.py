"""CLI: office hours booking and management on the shared rules
(``university/application/teaching/office_hours``) — real dates and appointment
times, the waitlist, moving a booking, cancelling one date, meeting records,
reminders, reporting and calendar export."""

from __future__ import annotations

from contextlib import closing
from datetime import date, timedelta

from education_system.systems.university.application.teaching import office_hours as rules
from education_system.systems.university.application.teaching import (
    occurrences as timetable_occurrences,
)
from education_system.systems.university.infrastructure.database.db import get_connection


def _run(fn, *args, write=False, **kwargs):
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
    except rules.FullError:
        raise
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None
    emails = result.get("emails") if isinstance(result, dict) else None
    if write and emails:
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def _pause():
    input("Press Enter to continue...")


def _list(rows):
    for r in rows:
        how = f"{r['slot_minutes']}-min slots" if r["slot_minutes"] else f"drop-in ({r['capacity']})"
        print(f"  #{r['id']:<4} {r['instructor_id']:<12} {r['day_of_week']:<9} "
              f"{r['start_time']}-{r['end_time']}  {r.get('mode') or 'in_person':<9} {how:<16} "
              f"next {r['next_date'] or '—'}" + (f"  teaches you: {', '.join(r['my_modules'])}"
                                                  if r["my_modules"] else ""))


def book(student_id):
    """Pick office hours, a real date and an appointment time."""
    mine = input("Only staff who teach your modules? (Y/n): ").strip().lower() != "n"
    rows = _run(rules.available, student_id=student_id, mine_only=mine) or []
    if not rows:
        print("No office hours to show.")
        return _pause()
    _list(rows)
    oh = input("Office hours #: ").strip()
    if not oh.isdigit():
        return None
    dates = _run(rules.dates, int(oh), 8) or []
    print("Dates: " + (", ".join(dates) or "none bookable soon"))
    when = input("Date: ").strip()
    slots = _run(rules.slots, int(oh), when) or []
    for s in slots:
        print(f"  {s['start']}-{s['end']}  " + ("free" if s["free"] else "taken")
              + (f" ({s['places_left']} places)" if "places_left" in s else ""))
    slot = input("Start time (blank for drop-in): ").strip() or None
    module = input("Module this is about (blank = none): ").strip() or None
    notes = input("What would you like to discuss? ").strip()
    try:
        made = _run(rules.book, int(oh), student_id, when, slot_start=slot, module_code=module,
                    notes=notes, write=True)
        if made:
            print(f"Booked: {made['when']}.")
    except rules.FullError as exc:
        print(exc)
        if input("Join the waitlist? (y/N): ").strip().lower() == "y":
            pos = _run(rules.join_waitlist, int(oh), student_id, when, module, notes, write=True)
            if pos:
                print(f"You are #{pos} on the waitlist.")
    return _pause()


def my_bookings(who, *, staff=False):
    rows = _run(rules.bookings_for, **({"instructor": who} if staff else {"student_id": who}),
                include_past=staff) or []
    for r in rows:
        print(f"  #{r['id']:<4} {r['booking_date']} {r['slot_start'] or r['start_time']}-"
              f"{r['slot_end'] or r['end_time']}  {r['student_id'] if staff else r['instructor_id']:<12} "
              f"{r['module_code'] or '':<10} {r['status']}"
              + (f" · {r['attendance']}" if r["attendance"] else ""))
    return rows


def move(student_id):
    rows = my_bookings(student_id)
    bid = input("Booking # to move: ").strip()
    target = next((r for r in rows if str(r["id"]) == bid), None)
    if not target:
        return None
    print("Dates: " + ", ".join(_run(rules.dates, target["office_hour_id"], 8) or []))
    when = input("New date: ").strip()
    slot = input("New start time (blank for drop-in): ").strip() or None
    made = _run(rules.reschedule, int(bid), student_id, when, slot_start=slot, write=True)
    if made:
        print(f"Moved to {made['when']}.")
    return _pause()


def cancel_date(instructor):
    rows = _run(rules.available, mine_only=False) or []
    mine = [r for r in rows if r["instructor_id"] == instructor]
    _list(mine)
    oh = input("Office hours #: ").strip()
    when = input("Date to cancel (YYYY-MM-DD): ").strip()
    reason = input("Reason (sent to students): ").strip()
    if oh.isdigit():
        result = _run(rules.cancel_date, int(oh), when, reason, instructor, write=True)
        if result:
            print(f"Cancelled; {result['cancelled']} booked student(s) told.")
    return _pause()


def record_meeting(instructor):
    my_bookings(instructor, staff=True)
    bid = input("Booking #: ").strip()
    attendance = input(f"Attendance ({', '.join(rules.schema.ATTENDANCE)}): ").strip()
    notes = input("Notes: ").strip()
    actions = input("Agreed actions: ").strip()
    if bid.isdigit() and _run(rules.record_meeting, int(bid), attendance, notes, actions,
                              instructor, write=True):
        print("Recorded.")
    return _pause()


def reminders():
    result = _run(rules.send_reminders, write=True)
    if isinstance(result, dict):
        print(f"{result['sent']} reminder(s) sent.")
    return _pause()


def report():
    since = input(f"From [{(date.today() - timedelta(days=90)).isoformat()}]: ").strip() or (
        date.today() - timedelta(days=90)).isoformat()
    until = input(f"To [{date.today().isoformat()}]: ").strip() or date.today().isoformat()
    for r in _run(rules.report, since, until) or []:
        print(f"  {r['instructor']:<12} offered {r['offered']}, booked {r['booked']} "
              f"({r['fill_pct'] if r['fill_pct'] is not None else '—'}% full), attended "
              f"{r['attended']}, no-shows {r['no_show']} "
              f"({r['no_show_pct'] if r['no_show_pct'] is not None else '—'}%)")
    return _pause()


def export(who, *, staff=False):
    rows = _run(rules.bookings_for, **({"instructor": who} if staff else {"student_id": who})) or []
    path = input("Save as (e.g. office-hours.ics): ").strip()
    if path:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(rules.ical(rows))
        print(f"Saved {sum(1 for r in rows if r['status'] == 'confirmed')} booking(s).")
    return _pause()
