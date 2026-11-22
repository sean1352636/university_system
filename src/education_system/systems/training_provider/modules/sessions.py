"""Scheduled sessions (a course on given dates), bookings and the register.

Rules:

* a session runs an Active course; its end date defaults from the course
  length (weekdays) and times are HH:MM with the end after the start;
* capacity defaults to the smaller of the course maximum and the venue's
  capacity and can't exceed either (an Online venue has no room limit), nor
  drop below the places already booked;
* the trainer must be active, hold an in-date approval for the course on the
  start date and not be teaching another session at the same time; a venue
  (other than Online) can't be double-booked either;
* a **closed** session is run for one client, so it names that client and
  only takes their learners;
* cancelling a session needs a reason and cancels its bookings at no charge;
  a session is Completed only once its last day has passed.

Bookings:

* one live booking per learner per session; an archived learner, a learner
  under the course's minimum age, or a client On hold / Closed can't be
  booked;
* an employer-funded learner is billed to their employer unless another
  client is chosen; a client that needs purchase orders must give one;
* the price defaults to the course price less the client's contract
  discount, and can't change once invoiced;
* a booking made when the session is full goes on the **waiting list**; when
  a place frees up (a cancellation or more capacity) the longest-waiting
  learner is moved up automatically;
* the learner cancelling within 7 days of the start is charged 50%, within 2
  days 100%; a no-show (Did not attend) pays in full; we cancel = no charge;
* Attended / Did not attend only once the session has started.
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta

from education_system.systems.training_provider.core import dates
from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.infrastructure import database as db
from education_system.systems.training_provider.modules import clients, courses, learners

SESSION_KINDS = ("Open (public)", "Closed (one client)")
SESSION_STATUSES = ("Planned", "Confirmed", "Completed", "Cancelled")
LIVE = ("Planned", "Confirmed")
BOOKING_STATUSES = ("Booked", "Waiting list", "Attended", "Did not attend", "Cancelled",
                    "Cancelled by us")
PLACE_TAKEN = ("Booked", "Attended", "Did not attend")
CHARGE_50_DAYS = 7
CHARGE_100_DAYS = 2
MARKS = ("Present", "Late", "Left early", "Absent")
PRESENT = ("Present", "Late")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _today() -> str:
    return date.today().isoformat()


# ── sessions ────────────────────────────────────────────────────────

def session_label(row: dict) -> str:
    course = r.get(courses.COURSES, row["course_id"]) if row.get("course_id") else None
    start = r.to_date(row.get("start_date"))
    code = course["code"] if course else "?"
    return f"{code} {dates.uk(start)}" + (f" #{row['id']}" if row.get("id") else "")


def session_days(row: dict) -> list[date]:
    """The days a session runs: weekdays from start to end, or every day if
    it starts or ends at a weekend."""
    start, end = r.to_date(row.get("start_date")), r.to_date(row.get("end_date"))
    if not start:
        return []
    end = end or start
    every = start.weekday() >= 5 or end.weekday() >= 5
    out, d = [], start
    while d <= end:
        if every or d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def taken(session_id: int, conn=None) -> int:
    sql = ("SELECT COUNT(*) FROM bookings WHERE session_id = ? AND status IN "
           "('Booked', 'Attended', 'Did not attend')")
    if conn is not None:
        return conn.execute(sql, (session_id,)).fetchone()[0]
    with db.connect() as c:
        return c.execute(sql, (session_id,)).fetchone()[0]


def waiting(session_id: int) -> int:
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM bookings WHERE session_id = ? AND "
                            "status = 'Waiting list'", (session_id,)).fetchone()[0]


def _overlaps(a: dict, b: dict) -> bool:
    a0, a1 = r.to_date(a.get("start_date")), r.to_date(a.get("end_date"))
    b0, b1 = r.to_date(b.get("start_date")), r.to_date(b.get("end_date"))
    if not (a0 and b0):
        return False
    a1, b1 = a1 or a0, b1 or b0
    if a1 < b0 or b1 < a0:
        return False
    times = [a.get("start_time"), a.get("end_time"), b.get("start_time"), b.get("end_time")]
    if all(times):
        return times[0] < times[3] and times[2] < times[1]
    return True


def _check_session(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    course = r.get(courses.COURSES, int(merged["course_id"])) if merged.get("course_id") \
        else None
    if course is None:
        raise ValidationError("Choose the course.")
    status, was = merged.get("status"), (old or {}).get("status")
    if (old is None or "course_id" in values and int(values["course_id"]) !=
            old.get("course_id")) and course["status"] != "Active":
        raise ValidationError(f"{course['code']} is retired: it can't be scheduled.")
    for key in ("start_time", "end_time"):
        if merged.get(key) and not _TIME.match(str(merged[key])):
            raise ValidationError("Times are 24-hour HH:MM, e.g. 09:30.")
    if merged.get("start_time") and merged.get("end_time") and \
            merged["end_time"] <= merged["start_time"]:
        raise ValidationError("The finish time is after the start time.")
    start = r.to_date(merged.get("start_date"))
    end = r.to_date(merged.get("end_date"))
    if start and not end:
        end = dates.school_day(start, max(1, math.ceil(float(course["duration_days"]))))
        if start.weekday() >= 5:
            end = start + timedelta(days=max(0, math.ceil(float(course["duration_days"])) - 1))
        values["end_date"] = end.isoformat()
    if start and end and end < start:
        raise ValidationError("A session can't end before it starts.")
    merged = {**merged, **values}
    venue = r.get(courses.VENUES, int(merged["venue_id"])) if merged.get("venue_id") else None
    online = bool(venue and venue["kind"] == "Online")
    limits = [int(course["max_delegates"])]
    if venue and not online and venue.get("capacity"):
        limits.append(int(venue["capacity"]))
    if merged.get("capacity") in (None, ""):
        values["capacity"] = min(limits)
    cap = int(values.get("capacity", merged.get("capacity")))
    if cap < 1:
        raise ValidationError("Capacity must be at least 1.")
    if cap > limits[0]:
        raise ValidationError(f"{course['code']} takes at most {limits[0]} learners.")
    if len(limits) > 1 and cap > limits[1]:
        raise ValidationError(f"{venue['name']} holds {limits[1]}.")
    if old is not None:
        booked = taken(old["id"])
        if cap < booked:
            raise ValidationError(f"{booked} places are already booked, so capacity can't be "
                                  f"below {booked}.")
    if merged.get("kind") == SESSION_KINDS[1] and not merged.get("client_id"):
        raise ValidationError("A closed session is run for one client: choose the client.")
    if merged.get("kind") == SESSION_KINDS[0]:
        values["client_id"] = None
    if status == "Cancelled":
        if not merged.get("cancel_reason"):
            raise ValidationError("Give the reason the session was cancelled.")
    elif was == "Cancelled":
        raise ValidationError("A cancelled session stays cancelled: schedule a new one.")
    if status == "Completed" and end and end >= date.today():
        raise ValidationError("A session is Completed once its last day has passed.")
    if status in LIVE and start:
        trainer = r.get(courses.TRAINERS, int(merged["trainer_id"])) \
            if merged.get("trainer_id") else None
        if trainer is not None:
            if trainer["status"] != "Active":
                raise ValidationError(f"{trainer['name']} is inactive.")
            if not courses.approved(trainer["id"], course["id"], start):
                raise ValidationError(f"{trainer['name']} has no in-date approval to deliver "
                                      f"{course['code']} on {dates.uk(start)}.")
        me = {**merged, "end_date": end.isoformat() if end else None}
        for other in r.list_records(SESSIONS):
            if other["id"] == (old or {}).get("id") or other["status"] not in LIVE:
                continue
            if not _overlaps(me, other):
                continue
            if trainer is not None and other.get("trainer_id") == trainer["id"]:
                raise ValidationError(f"{trainer['name']} is already teaching "
                                      f"{session_label(other)} then.")
            if venue is not None and not online and other.get("venue_id") == venue["id"]:
                raise ValidationError(f"{venue['name']} is already booked for "
                                      f"{session_label(other)} then.")


def _promote(conn, session_id: int, actor: str = "system") -> int:
    """Move waiting-list bookings up into any free places; returns how many."""
    row = conn.execute("SELECT capacity, status FROM sessions WHERE id = ?",
                       (session_id,)).fetchone()
    if row is None or row["status"] not in LIVE:
        return 0
    free = int(row["capacity"]) - taken(session_id, conn)
    moved = 0
    for b in conn.execute("SELECT id, learner_id FROM bookings WHERE session_id = ? AND "
                          "status = 'Waiting list' ORDER BY booked_on, id LIMIT ?",
                          (session_id, max(0, free))).fetchall():
        conn.execute("UPDATE bookings SET status = 'Booked', updated_at = datetime('now') "
                     "WHERE id = ?", (b["id"],))
        conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, action, "
                     "summary) VALUES (?, 'bookings', ?, ?, 'updated', ?)",
                     (actor, b["id"], b["learner_id"],
                      "Booking moved up from the waiting list"))
        moved += 1
    return moved


def _after_session(conn, row: dict, old: dict | None) -> None:
    if row["status"] == "Cancelled" and (old or {}).get("status") != "Cancelled":
        for b in conn.execute("SELECT id, learner_id FROM bookings WHERE session_id = ? AND "
                              "status IN ('Booked', 'Waiting list')", (row["id"],)).fetchall():
            conn.execute("UPDATE bookings SET status = 'Cancelled by us', cancelled_on = ?, "
                         "cancellation_charge = 0, updated_at = datetime('now') WHERE id = ?",
                         (_today(), b["id"]))
            conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                         "action, summary) VALUES ('system', 'bookings', ?, ?, 'updated', ?)",
                         (b["id"], b["learner_id"], "Booking cancelled - session cancelled: "
                          + (row.get("cancel_reason") or "")))
    elif old is not None:
        _promote(conn, row["id"])


def _fill(row: dict) -> str:
    if not row.get("id"):
        return ""
    w = waiting(row["id"])
    return f"{taken(row['id'])}/{row.get('capacity')}" + (f" (+{w} waiting)" if w else "")


SESSIONS = RecordType(
    key="sessions", title="Sessions", singular="session", order_by="start_date DESC, id DESC",
    check=_check_session, after_save=_after_session, filters=("kind", "status"),
    describe=session_label, computed=(("Booked", _fill),),
    fields=(
        Field("course_id", "Course", "ref", ref="courses", required=True),
        Field("kind", "Type", "choice", SESSION_KINDS, required=True, default=SESSION_KINDS[0]),
        Field("client_id", "Client (closed session)", "ref", ref="clients",
              on_delete="SET NULL"),
        Field("start_date", "Starts", "date", required=True),
        Field("end_date", "Ends", "date", help="Blank: from the course length"),
        Field("start_time", "From", default="09:00", listed=False),
        Field("end_time", "To", default="16:30", listed=False),
        Field("venue_id", "Venue", "ref", ref="venues", required=True),
        Field("trainer_id", "Trainer", "ref", ref="trainers"),
        Field("capacity", "Capacity", "int", listed=False,
              help="Blank: the course / venue maximum"),
        Field("status", "Status", "choice", SESSION_STATUSES, required=True, default="Planned"),
        Field("cancel_reason", "Cancellation reason", listed=False),
        Field("joining_instructions", "Joining instructions", "long", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def upcoming(days: int = 60) -> list[dict]:
    today, horizon = date.today(), date.today() + timedelta(days=days)
    return [s for s in reversed(r.list_records(SESSIONS)) if s["status"] in LIVE
            and today <= (r.to_date(s["end_date"]) or today) and
            (r.to_date(s["start_date"]) or today) <= horizon]


def session_options(live_only: bool = True) -> list[tuple[int, str]]:
    rows = r.list_records(SESSIONS)
    if live_only:
        rows = [s for s in rows if s["status"] in LIVE]
    return [(s["id"], session_label(s)) for s in rows]


# ── bookings ────────────────────────────────────────────────────────

def cancellation_charge(price: float, start: date | None, cancelled: date) -> float:
    if start is None:
        return 0.0
    notice = (start - cancelled).days
    if notice < CHARGE_100_DAYS:
        return round(price, 2)
    if notice < CHARGE_50_DAYS:
        return round(price * 0.5, 2)
    return 0.0


def chargeable(row: dict) -> float:
    """What a booking costs the payer as it stands."""
    if row.get("status") in PLACE_TAKEN:
        return float(row.get("price") or 0)
    if row.get("status") == "Cancelled":
        return float(row.get("cancellation_charge") or 0)
    return 0.0


def _check_booking(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    session = r.get(SESSIONS, int(merged["session_id"])) if merged.get("session_id") else None
    if session is None:
        raise ValidationError("Choose the session.")
    course = r.get(courses.COURSES, session["course_id"])
    learner = r.get(learners.LEARNERS, int(merged["learner_id"]))
    status, was = merged.get("status"), (old or {}).get("status")
    start = r.to_date(session["start_date"])
    new_place = old is None or ("session_id" in values and
                                int(values["session_id"]) != old["session_id"])
    if new_place:
        if session["status"] not in LIVE:
            raise ValidationError(f"That session is {session['status'].lower()}: it can't "
                                  "take bookings.")
        if learner["status"] != "Active":
            raise ValidationError(f"{learners.learner_label(learner)} is archived.")
        with db.connect() as conn:
            dupe = conn.execute(
                "SELECT 1 FROM bookings WHERE learner_id = ? AND session_id = ? AND status NOT "
                "IN ('Cancelled', 'Cancelled by us') AND id IS NOT ?",
                (learner["id"], session["id"], (old or {}).get("id"))).fetchone()
        if dupe:
            raise ValidationError("That learner is already booked on this session.")
        if course.get("min_age"):
            dob = r.to_date(learner.get("dob"))
            if dob is None:
                raise ValidationError(f"{course['code']} has a minimum age of "
                                      f"{course['min_age']}: record the learner's date of "
                                      "birth first.")
            if start and dates.age_on(dob, start) < int(course["min_age"]):
                raise ValidationError(f"{course['code']} is for learners aged "
                                      f"{course['min_age']} or over.")
    if "client_id" not in values or merged.get("client_id") is None:
        if old is None and learner.get("funding") == "Employer" and learner.get("client_id"):
            values["client_id"] = learner["client_id"]
        elif old is None:
            # A learner sent by an apprenticeship provider or FE college:
            # bill whoever their open training request says pays.
            from education_system.systems.training_provider.modules import requests
            with db.connect() as conn:
                bill_to, po = requests.billing_for(conn, learner["id"])
            if bill_to:
                values["client_id"] = bill_to
                if not merged.get("po_number") and po:
                    values["po_number"] = po
    merged = {**merged, **values}
    client = r.get(clients.CLIENTS, int(merged["client_id"])) if merged.get("client_id") \
        else None
    if session["kind"] == SESSION_KINDS[1] and (client is None or
                                                client["id"] != session["client_id"]):
        raise ValidationError("That is a closed session run for another client.")
    if client is not None:
        if new_place and client["status"] != "Active":
            raise ValidationError(f"{client['name']}'s account is {client['status'].lower()}"
                                  + (f": {client['hold_reason']}" if client.get("hold_reason")
                                     else "") + ".")
        if client.get("po_required") and not merged.get("po_number"):
            raise ValidationError(f"{client['name']} needs a purchase order number.")
    if merged.get("price") in (None, ""):
        disc = clients.contract_discount(client["id"] if client else None,
                                         start or date.today())
        values["price"] = round(float(course["price"]) * (1 - disc / 100), 2)
    if old is not None and old.get("invoice_id") and "price" in values and \
            float(values["price"]) != float(old.get("price") or 0):
        raise ValidationError("This booking has been invoiced: its price can't change. "
                              "Cancel the invoice first.")
    if not merged.get("booked_on"):
        values["booked_on"] = _today()
    # place on the session, or the waiting list
    if status == "Booked" and (old is None or was not in PLACE_TAKEN or new_place):
        if taken(session["id"]) >= int(session["capacity"]):
            values["status"] = status = "Waiting list"
    if status in ("Attended", "Did not attend") and start and start > date.today():
        raise ValidationError("The session hasn't started yet.")
    if status == "Cancelled":
        on = r.to_date(merged.get("cancelled_on")) or date.today()
        values["cancelled_on"] = on.isoformat()
        if merged.get("cancellation_charge") in (None, "") or was != "Cancelled":
            price = float(values.get("price", merged.get("price")) or 0)
            values["cancellation_charge"] = (0.0 if was == "Waiting list" else
                                             cancellation_charge(price, start, on))
    elif status == "Cancelled by us":
        values["cancelled_on"] = merged.get("cancelled_on") or _today()
        values["cancellation_charge"] = 0
    else:
        values["cancelled_on"] = None
        values["cancellation_charge"] = None


def _after_booking(conn, row: dict, old: dict | None) -> None:
    if old is not None and old.get("status") in PLACE_TAKEN and \
            row["status"] not in PLACE_TAKEN:
        _promote(conn, old["session_id"])
    if old is not None and old["session_id"] != row["session_id"]:
        _promote(conn, old["session_id"])


def who(row: dict) -> str:
    """The learner's name for a row (the joined name, else looked up)."""
    if row.get("learner_name"):
        return row["learner_name"]
    learner = r.get(learners.LEARNERS, row["learner_id"]) if row.get("learner_id") else None
    return f"{learner['first_name']} {learner['last_name']}" if learner else "Learner"


def booking_label(row: dict) -> str:
    s = r.get(SESSIONS, row["session_id"]) if row.get("session_id") else None
    return f"{who(row)} - {session_label(s) if s else '?'}"


BOOKINGS = RecordType(
    key="bookings", title="Bookings", singular="booking", order_by="booked_on DESC, id DESC",
    check=_check_booking, after_save=_after_booking, filters=("status",),
    after_commit=learners.platform_hook("booking_saved"),
    describe=booking_label,
    computed=(("Session", lambda row: session_label(r.get(SESSIONS, row["session_id"]) or {})),
              ("Charge", lambda row: f"£{chargeable(row):,.2f}")),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("session_id", "Session", "ref", ref="sessions", required=True),
        Field("client_id", "Billed to (client)", "ref", ref="clients", on_delete="SET NULL",
              help="Blank: the learner pays (or their employer, if employer-funded)"),
        Field("po_number", "PO number", listed=False),
        Field("price", "Price", "money", help="Blank: course price less contract discount"),
        Field("status", "Status", "choice", BOOKING_STATUSES, required=True, default="Booked"),
        Field("booked_on", "Booked", "date", listed=False),
        Field("cancelled_on", "Cancelled", "date", listed=False),
        Field("cancellation_charge", "Cancellation charge", "money", listed=False,
              help="Worked out from the notice given"),
        Field("special_requirements", "Access / dietary needs", "long", listed=False),
        Field("invoice_id", "Invoice", "int", form=False, listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def session_bookings(session_id: int, *, places_only: bool = True) -> list[dict]:
    rows = r.list_records(BOOKINGS, equals={"session_id": session_id})
    if places_only:
        rows = [b for b in rows if b["status"] in PLACE_TAKEN]
    return sorted(rows, key=lambda b: b.get("learner_name") or "")


def booking_for(learner_id: int, session_id: int) -> dict | None:
    rows = [b for b in r.list_records(BOOKINGS, equals={"learner_id": learner_id,
                                                        "session_id": session_id})
            if b["status"] not in ("Cancelled", "Cancelled by us")]
    return rows[0] if rows else None


# ── attendance (the register) ───────────────────────────────────────

def _check_attendance(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    session = r.get(SESSIONS, int(merged["session_id"]))
    booking = booking_for(int(merged["learner_id"]), session["id"])
    if booking is None or booking["status"] not in PLACE_TAKEN:
        raise ValidationError("That learner has no place on this session.")
    day = r.to_date(merged.get("day"))
    if day not in session_days(session):
        raise ValidationError("That isn't one of the session's days.")
    if day > date.today():
        raise ValidationError("The register can't be taken for a future day.")
    with db.connect() as conn:
        dupe = conn.execute("SELECT 1 FROM attendance WHERE learner_id = ? AND session_id = ? "
                            "AND day = ? AND id IS NOT ?",
                            (merged["learner_id"], session["id"], day.isoformat(),
                             (old or {}).get("id"))).fetchone()
    if dupe:
        raise ValidationError("That day is already marked for the learner: edit that mark.")


ATTENDANCE = RecordType(
    key="attendance", title="Attendance", singular="attendance mark",
    order_by="day DESC, id DESC", check=_check_attendance, filters=("mark",),
    describe=lambda row: f"{who(row)} {row.get('day')}: "
                         f"{row.get('mark')}",
    computed=(("Session", lambda row: session_label(r.get(SESSIONS, row["session_id"]) or {})),),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("session_id", "Session", "ref", ref="sessions", required=True,
              on_delete="CASCADE"),
        Field("day", "Day", "date", required=True),
        Field("mark", "Mark", "choice", MARKS, required=True, default="Present"),
        Field("notes", "Notes", listed=False),
    ),
)


def marks_for(session_id: int, day: date | None = None) -> dict[tuple[int, str], dict]:
    equals: dict = {"session_id": session_id}
    if day is not None:
        equals["day"] = day.isoformat()
    return {(m["learner_id"], m["day"]): m for m in r.list_records(ATTENDANCE, equals=equals)}


def full_attendance(learner_id: int, session_id: int) -> bool:
    session = r.get(SESSIONS, session_id)
    marks = marks_for(session_id)
    days = session_days(session or {})
    return bool(days) and all(
        (marks.get((learner_id, d.isoformat())) or {}).get("mark") in PRESENT for d in days)


def take_register(session_id: int, day: date, marks: dict[int, str], *,
                  actor: str = "system") -> int:
    """Save one day's marks ({learner_id: mark}); on the last day, settle each
    booking as Attended / Did not attend. Returns marks saved."""
    session = r.get(SESSIONS, session_id)
    if session is None or session["status"] == "Cancelled":
        raise ValidationError("That session was cancelled.")
    existing = marks_for(session_id, day)
    saved = 0
    for learner_id, mark in marks.items():
        if not mark:
            continue
        old = existing.get((learner_id, day.isoformat()))
        if old and old["mark"] == mark:
            continue
        r.save(ATTENDANCE, {"learner_id": learner_id, "session_id": session_id,
                            "day": day.isoformat(), "mark": mark},
               record_id=old["id"] if old else None, actor=actor)
        saved += 1
    days = session_days(session)
    if days and day == days[-1]:
        settle(session_id, actor=actor)
    return saved


def settle(session_id: int, *, actor: str = "system") -> None:
    """Mark each booking Attended (present on any day) or Did not attend."""
    marks = marks_for(session_id)
    for b in session_bookings(session_id):
        if b["status"] != "Booked":
            continue
        days = [m for (lid, _), m in marks.items() if lid == b["learner_id"]]
        if not days:
            continue
        seen = any(m["mark"] != "Absent" for m in days)
        r.save(BOOKINGS, {"status": "Attended" if seen else "Did not attend"},
               record_id=b["id"], actor=actor)
