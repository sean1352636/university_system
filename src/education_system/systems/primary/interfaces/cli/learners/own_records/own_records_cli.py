"""Student and parent screens for the Primary School System (terminal).

Mirrors the GUI through the same read layer, ``domain/learners/own_records``:
identity comes from ``auth`` and a pupil id is never typed, only chosen from the
parent's own linked children.
"""

from __future__ import annotations

from typing import Any, Callable

from education_system.platform.delivery.cli.own_record_cli import (
    choose_child,
    guarded,
    pick,
    print_table,
    prompt,
)
from education_system.systems.primary.domain.learners.own_records import own_records as data


def _timetable(auth: Any) -> None:
    print_table([("Day", 5), ("Per", 4), ("Start", 6), ("End", 6), ("Subject", 24),
                 ("Room", 10), ("Teacher", 20)],
                [(r.day, r.period, r.start_time, r.end_time, r.subject, r.room, r.teacher)
                 for r in data.timetable(auth)],
                empty="No timetable has been set for your year or class yet.")


def _homework(auth: Any) -> None:
    rows = data.homework(auth)
    print_table([("Due", 11), ("Subject", 16), ("Title", 30), ("Status", 10), ("Grade", 6),
                 ("Mark", 6)],
                [(r.due_date, r.subject, r.title, r.status, r.grade, r.mark_pct) for r in rows],
                empty="No homework has been set for your year or class.", numbered=True)
    if rows:
        row = pick(rows, "  Show details for # (blank to skip): ")
        if row:
            print(f"\n  What to do: {row.instructions or 'No instructions given.'}")
            print(f"  Feedback: {row.feedback or 'None yet.'}")


def _reading_log(auth: Any) -> None:
    current, history = data.reading_log(auth)
    if current is not None:
        print(f"  Current book band: {current.band} ({current.status})")
    print_table([("Date", 11), ("Band", 14), ("Status", 8), ("Book", 40)],
                [(h.assessed_on, h.band, h.status, h.book_title) for h in history],
                empty="No reading has been logged for you yet.")


def _attendance(auth: Any, pupil_id: str) -> None:
    s = data.attendance(auth, pupil_id)
    print(f"  Attendance {s.attendance_pct}% of {s.total_sessions} sessions: {s.present} "
          f"present, {s.authorised_absent} authorised absence, "
          f"{s.unauthorised_absent} unauthorised absence")
    print_table([("Date", 11), ("Session", 8), ("Mark", 24)],
                [(m.date, m.session, m.mark) for m in s.marks],
                empty="No attendance has been recorded yet.")


def _assessment(auth: Any, pupil_id: str) -> None:
    print_table([("Year", 9), ("Term", 8), ("Subject", 24), ("Grade", 6), ("Score", 6),
                 ("Assessed", 11)],
                [(r.academic_year, r.term, r.subject, r.grade, r.score, r.assessed_on)
                 for r in data.assessment(auth, pupil_id)],
                empty="No assessment has been recorded yet.")


def _reports(auth: Any, pupil_id: str) -> None:
    rows = data.reports(auth, pupil_id)
    print_table([("Year", 9), ("Term", 8), ("Published", 11), ("Headline", 46)],
                [(r.academic_year, r.term, r.published_on, r.headline) for r in rows],
                empty="No reports have been published yet.", numbered=True)
    if rows:
        r = pick(rows, "  Read report # (blank to skip): ")
        if r:
            for name, value in (("Summary", r.summary), ("Strengths", r.strengths),
                                ("Next steps", r.next_steps), ("Behaviour", r.behaviour)):
                if value:
                    print(f"\n  {name}: {value}")
            if r.attendance_pct is not None:
                print(f"\n  Attendance: {r.attendance_pct}%")


def _yes_no(question: str) -> bool:
    return prompt(f"  {question} (y/N): ").lower() == "y"


def _consent(auth: Any, pupil_id: str) -> None:
    answers = data.consent_answers(auth, pupil_id)
    print("  School consent forms")
    print_table([("Form", 24), ("Your answer", 13), ("Date", 11)],
                [(a.purpose, a.answer, a.answered_on) for a in answers],
                empty="There are no consent forms.", numbered=True)
    chosen = pick(answers, "  Answer form # (blank to skip): ")
    if chosen:
        give = _yes_no(f"Give consent for {chosen.purpose}? Answering no records it as not given.")
        saved = data.answer_consent(auth, pupil_id, chosen.purpose, give)
        print(f"  Saved: {saved.purpose} {saved.answer}.")

    trips = data.trip_consents(auth, pupil_id)
    print("\n  Trips")
    print_table([("Trip", 24), ("Destination", 20), ("Starts", 11), ("Consent", 10)],
                [(t.trip, t.destination, t.start_date,
                  "Given" if t.consent_received else "Not given") for t in trips],
                empty="Your child is not booked on any upcoming trips.", numbered=True)
    if trips:
        trip = pick(trips, "  Answer for trip # (blank to skip): ")
        if trip:
            give = _yes_no(f"Give consent for {trip.trip}? Answering no records it as not given.")
            saved_trip = data.answer_trip_consent(auth, pupil_id, trip.booking_id, give)
            word = "Given" if saved_trip.consent_received else "Not given"
            print(f"  Saved: {saved_trip.trip} {word}.")


def _evening(auth: Any, pupil_id: str) -> None:
    print("  Your bookings")
    print_table([("Evening", 24), ("Date", 11), ("Time", 6), ("Teacher", 20), ("Status", 10)],
                [(b.event, b.event_date, b.slot_time, b.teacher, b.status)
                 for b in data.evening_bookings(auth, pupil_id)],
                empty="You have no bookings for this child.")
    events = data.evening_options(auth, pupil_id)
    if not events:
        print("  No parents' evening is open for booking at the moment.")
        return
    teachers = data.evening_teachers(auth, pupil_id)
    if not teachers:
        print("  No class teacher is recorded for your child's class yet, so there is "
              "nobody to book with. Please contact the school office.")
        return
    print("\n  Evenings open for booking")
    print_table([("Evening", 24), ("Date", 11), ("From", 6), ("To", 6), ("Where", 16)],
                [(e.name, e.event_date, e.start_time, e.end_time, e.location) for e in events],
                empty="None.", numbered=True)
    event = pick(events, "  Book at evening # (blank to skip): ")
    if not event:
        return
    print_table([("Teacher", 30)], [(t.name,) for t in teachers], empty="None.", numbered=True)
    teacher = pick(teachers, "  With teacher # (blank to skip): ")
    if not teacher:
        return
    slots = data.evening_slots(auth, pupil_id, event.event_id, teacher.staff_id)
    if not slots:
        print("  There are no free times for this teacher.")
        return
    print_table([("Time", 8)], [(s,) for s in slots], empty="None.", numbered=True)
    slot = pick(slots, "  Time # (blank to skip): ")
    if slot and _yes_no(f"Book {slot} with {teacher.name}? To change it afterwards, "
                        "contact the school office."):
        saved = data.book_evening(auth, pupil_id, event.event_id, teacher.staff_id, slot)
        print(f"  Booked: {saved.slot_time} with {saved.teacher} on {saved.event_date}.")


_STUDENT: dict[str, Callable[[Any], None]] = {
    "My Timetable": _timetable,
    "My Homework": _homework,
    "My Reading Log": _reading_log,
}

_PARENT: dict[str, Callable[[Any, str], None]] = {
    "Child Attendance": _attendance,
    "Child Assessment": _assessment,
    "Child Reports": _reports,
    "Consent Forms": _consent,
    "Parents' Evening Booking": _evening,
}


def _for_child(auth: Any, screen: Callable[[Any, str], None]) -> None:
    children = data.my_children(auth)
    if not children:
        raise data.NoRecordLink(
            "Your login is not linked to a child at this school, so no records can be "
            "shown. Please ask the school office to link your account.")
    pupil_id = choose_child(children)
    if pupil_id:
        screen(auth, pupil_id)


def dispatch(label: str, *, auth: Any) -> bool:
    if label in _STUDENT:
        guarded(label, lambda: _STUDENT[label](auth))
        return True
    if label in _PARENT:
        guarded(label, lambda: _for_child(auth, _PARENT[label]))
        return True
    return False


# ── Administrators: linking a parent's login to their child ────────

def link_parent_logins(auth: Any) -> None:
    """Admin-only step on the Parent Contacts menu, by exact username and pupil id."""
    def draw() -> None:
        username = prompt("  Parent login username: ")
        if not username:
            return
        print_table([("Pupil ID", 10), ("Name", 30), ("Year", 5)],
                    [(c.pupil_id, c.name, c.year_group)
                     for c in data.linked_children_of(auth, username)],
                    empty="This login is not linked to any child.")
        action = prompt("  L) Link a child  U) Unlink a child  (blank to go back): ").lower()
        if action == "l":
            child = data.link_parent_login(auth, username, prompt("  Exact pupil ID: "))
            print(f"  Linked to {child.name}.")
        elif action == "u":
            ended = data.unlink_parent_login(auth, username, prompt("  Exact pupil ID: "))
            print("  Link ended." if ended else "  No such link.")
    guarded("Link Parent Login", draw)
