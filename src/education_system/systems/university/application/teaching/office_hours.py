"""Office hours: when a student can actually meet a member of staff, and what
happens around the meeting.

A block (``office_hours``) is a weekly window — Monday 09:00–15:00 in a room,
online, or either. Bookings are for a *date* of that block and, when the block
has ``slot_minutes``, for one appointment slot inside it (a 15-minute slot,
say); without it the block is a drop-in and capacity counts heads.

Rules
-----
* A date must fall on the block's weekday, be in the future and at least
  ``min_notice_hours`` away, inside an academic term (when terms are set up),
  not a holiday and not a date the instructor has cancelled.
* A student may hold at most ``max_per_student_week`` bookings with one
  instructor in a week, and may cancel up to ``cancel_cutoff_hours`` before
  the meeting (staff can cancel at any time).
* A full date has a waitlist; a cancellation books the first person waiting.
* Cancelling one date (illness, leave) cancels its bookings and tells the
  students; the weekly block carries on.
* After the meeting, staff record attended / no-show and notes and agreed
  actions. A reminder goes out the day before.
* The staff directory's office-hours list mirrors the bookable blocks
  (``staff_office_hours_directory.office_hour_id``), so the two agree.

Notices go to the Hub inbox in the caller's transaction; emails are returned
for the caller to send once committed (``timetable_occurrences.send_emails``).
Functions take an open connection and do not commit.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from education_system.systems.university.infrastructure.database.schemas import (
    office_hours_schema as schema,
)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DEFAULTS = {"min_notice_hours": 2, "cancel_cutoff_hours": 2, "max_per_student_week": 2}
REMINDER_HOURS = 24
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def ensure(conn):
    schema.apply_to_connection(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _one(conn, sql, params=()):
    rows = _dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def _now(now=None):
    return now or datetime.now()


def _fmt(when):
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _minutes(t):
    return int(t[:2]) * 60 + int(t[3:5])


def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValueError("Dates are YYYY-MM-DD") from None


# ── blocks ──────────────────────────────────────────────────────────────


def block(conn, office_hour_id) -> dict:
    ensure(conn)
    row = _one(conn, "SELECT * FROM office_hours WHERE id = ?", (office_hour_id,))
    if not row:
        raise ValueError("No such office hours")
    for key, default in DEFAULTS.items():
        if row.get(key) is None:
            row[key] = default
    row["mode"] = row.get("mode") or "in_person"
    return row


def _check_block(values):
    day = str(values.get("day_of_week") or "").strip().title()
    if day not in DAYS:
        raise ValueError("Choose a day of the week")
    start, end = str(values.get("start_time") or ""), str(values.get("end_time") or "")
    if not (_TIME.match(start) and _TIME.match(end)) or start >= end:
        raise ValueError("Times are HH:MM and the end must be after the start")
    slot = values.get("slot_minutes")
    slot = int(slot) if str(slot or "").strip() else None
    if slot is not None and not (5 <= slot <= _minutes(end) - _minutes(start)):
        raise ValueError("Appointment length must be at least 5 minutes and fit in the block")
    mode = values.get("mode") or "in_person"
    if mode not in schema.MODES:
        raise ValueError(f"Mode is one of: {', '.join(schema.MODES)}")
    url = (values.get("online_url") or "").strip() or None
    if mode != "in_person" and not url:
        raise ValueError("Online office hours need a meeting link")
    if url and not url.lower().startswith(("https://", "http://")):
        raise ValueError("The meeting link must start with https://")
    if mode != "online" and not (values.get("location") or "").strip():
        raise ValueError("Give a location (or make the office hours online)")
    return day, start, end, slot, mode, url


def _rule(values, key):
    value = values.get(key)
    if not str(value if value is not None else "").strip():
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key.replace('_', ' ')} must be a whole number") from None
    if number < 0:
        raise ValueError(f"{key.replace('_', ' ')} cannot be negative")
    return number


def save_block(conn, values: dict, office_hour_id=None, actor=None) -> int:
    """Create or update a block with its slots, mode and booking rules."""
    ensure(conn)
    day, start, end, slot, mode, url = _check_block(values)
    capacity = _rule(values, "capacity")
    if slot is None and not capacity:
        raise ValueError("A drop-in block needs a capacity of at least 1")
    if slot:
        capacity = (_minutes(end) - _minutes(start)) // slot
    row = (str(values.get("instructor_id") or actor or "").strip(), day, start, end,
           (values.get("location") or "").strip() or "Online", capacity,
           values.get("notes") or "", slot, mode, url,
           (values.get("module_code") or "").strip() or None,
           _rule(values, "min_notice_hours"), _rule(values, "cancel_cutoff_hours"),
           _rule(values, "max_per_student_week"))
    if not row[0]:
        raise ValueError("Say whose office hours these are")
    cols = ("instructor_id", "day_of_week", "start_time", "end_time", "location", "capacity",
            "notes", "slot_minutes", "mode", "online_url", "module_code", "min_notice_hours",
            "cancel_cutoff_hours", "max_per_student_week")
    if office_hour_id:
        sets = ", ".join(f"{c} = ?" for c in cols[1:])
        # db-audit: ignore[DBW001] - column names are literals
        conn.execute(f"UPDATE office_hours SET {sets}, updated_at = datetime('now') WHERE id = ?",
                     (*row[1:], office_hour_id))
    else:
        # db-audit: ignore[DBW001] - column names are literals
        office_hour_id = conn.execute(
            f"INSERT INTO office_hours ({', '.join(cols)}, is_active) VALUES "
            f"({', '.join('?' for _ in cols)}, 1)", row).lastrowid
    sync_directory(conn, office_hour_id)
    return int(office_hour_id)


def retire_block(conn, office_hour_id, actor=None, now=None) -> dict:
    """Stop a weekly block: future bookings are cancelled and the students told."""
    b = block(conn, office_hour_id)
    conn.execute("UPDATE office_hours SET is_active = 0, updated_at = datetime('now') "
                 "WHERE id = ?", (office_hour_id,))
    emails = []
    today = _now(now).date().isoformat()
    for booking in _dicts(conn.execute(
            "SELECT id FROM office_hour_bookings WHERE office_hour_id = ? AND status = "
            "'confirmed' AND booking_date >= ?", (office_hour_id, today))):
        emails += _cancel_row(conn, booking["id"], actor, "these office hours have ended", b)
    sync_directory(conn, office_hour_id)
    return {"emails": emails}


# ── dates and slots ─────────────────────────────────────────────────────


def _term_ok(conn, day):
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    terms = timetable_occurrences.terms(conn)
    return not terms or any(s <= day <= e for _n, s, e in terms)


def _date_problem(conn, b, day, now):
    if DAYS[day.weekday()] != b["day_of_week"]:
        return f"{b['day_of_week']} office hours cannot be booked for a {DAYS[day.weekday()]}"
    if datetime.combine(day, datetime.strptime(b["end_time"], "%H:%M").time()) <= now:
        return "that date has passed"
    from education_system.systems.university.application.attendance import (
        registers as attendance_registers,
    )
    if day in attendance_registers.holiday_dates(conn):
        return "that date is a holiday"
    if not _term_ok(conn, day):
        return "that date is outside term"
    reason = conn.execute("SELECT reason FROM office_hour_exceptions WHERE office_hour_id = ? "
                          "AND exception_date = ?", (b["id"], day.isoformat())).fetchone()
    if reason:
        return f"cancelled that day: {reason[0]}"
    return None


def dates(conn, office_hour_id, weeks=6, now=None) -> list[str]:
    """The next bookable dates of a block."""
    b = block(conn, office_hour_id)
    now = _now(now)
    target = DAYS.index(b["day_of_week"]) if b["day_of_week"] in DAYS else None
    if target is None:
        return []
    day = now.date() + timedelta(days=(target - now.date().weekday()) % 7)
    out = []
    for _ in range(weeks):
        if not _date_problem(conn, b, day, now):
            out.append(day.isoformat())
        day += timedelta(days=7)
    return out


def slots(conn, office_hour_id, booking_date) -> list[dict]:
    """Appointment slots on a date with whether each is free; a drop-in block
    is one row with its remaining places."""
    b = block(conn, office_hour_id)
    taken = _dicts(conn.execute("SELECT slot_start FROM office_hour_bookings WHERE "
                                "office_hour_id = ? AND booking_date = ? AND status = "
                                "'confirmed'", (office_hour_id, str(booking_date)[:10])))
    if not b["slot_minutes"]:
        left = (b["capacity"] or 0) - len(taken)
        return [{"start": b["start_time"], "end": b["end_time"], "free": left > 0,
                 "places_left": max(left, 0)}]
    used = {t["slot_start"] for t in taken}
    out, m = [], _minutes(b["start_time"])
    while m + b["slot_minutes"] <= _minutes(b["end_time"]):
        out.append({"start": _hhmm(m), "end": _hhmm(m + b["slot_minutes"]),
                    "free": _hhmm(m) not in used})
        m += b["slot_minutes"]
    return out


# ── booking ─────────────────────────────────────────────────────────────


class FullError(ValueError):
    """The date (or every slot on it) is full."""


def _week_count(conn, instructor, student_id, day):
    monday = day - timedelta(days=day.weekday())
    return conn.execute(
        "SELECT COUNT(*) FROM office_hour_bookings b JOIN office_hours o ON o.id = "
        "b.office_hour_id WHERE o.instructor_id = ? AND b.student_id = ? AND b.status = "
        "'confirmed' AND b.booking_date BETWEEN ? AND ?",
        (instructor, student_id, monday.isoformat(),
         (monday + timedelta(days=6)).isoformat())).fetchone()[0]


def _pick_slot(conn, b, day, slot_start):
    free = [s for s in slots(conn, b["id"], day) if s["free"]]
    if not free:
        return None
    if not b["slot_minutes"]:
        return free[0]
    if not slot_start:
        raise ValueError("Choose an appointment time")
    chosen = next((s for s in free if s["start"] == slot_start), None)
    if not chosen:
        raise ValueError(f"{slot_start} is not a free appointment time that day")
    return chosen


def _check_booking(conn, b, day, student_id, now):
    if not b["is_active"]:
        raise ValueError("These office hours are no longer running")
    problem = _date_problem(conn, b, day, now)
    if problem:
        raise ValueError(f"Cannot book: {problem}")
    begins = datetime.combine(day, datetime.strptime(b["start_time"], "%H:%M").time())
    if begins - now < timedelta(hours=b["min_notice_hours"]) and begins > now:
        raise ValueError(f"Book at least {b['min_notice_hours']} hour(s) ahead")
    if conn.execute("SELECT 1 FROM office_hour_bookings WHERE office_hour_id = ? AND "
                    "student_id = ? AND booking_date = ? AND status = 'confirmed'",
                    (b["id"], student_id, day.isoformat())).fetchone():
        raise ValueError("You already have a booking in these office hours that day")
    if _week_count(conn, b["instructor_id"], student_id, day) >= b["max_per_student_week"]:
        raise ValueError(f"At most {b['max_per_student_week']} booking(s) a week with the "
                         "same member of staff")


def _module_ok(conn, b, student_id, module_code):
    if not module_code:
        return None
    if not conn.execute("SELECT 1 FROM student_modules WHERE student_id = ? AND module_code = ? "
                        "AND LOWER(COALESCE(status, '')) = 'enrolled'",
                        (student_id, module_code)).fetchone():
        raise ValueError(f"You are not enrolled on {module_code}")
    return module_code


def book(conn, office_hour_id, student_id, booking_date, *, slot_start=None, module_code=None,
         notes="", mode=None, now=None) -> dict:
    """Book a student in. Raises ValueError with the reason when they cannot;
    a full date raises ``FullError`` so the caller can offer the waitlist."""
    now = _now(now)
    b = block(conn, office_hour_id)
    student_id = str(student_id or "").strip()
    if not student_id:
        raise ValueError("Say who is booking")
    day = _date(booking_date)
    _check_booking(conn, b, day, student_id, now)
    module_code = _module_ok(conn, b, student_id, module_code or b.get("module_code"))
    if mode and mode not in ("in_person", "online"):
        raise ValueError("Meet in person or online")
    if mode and b["mode"] != "either" and mode != b["mode"]:
        raise ValueError(f"These office hours are {b['mode'].replace('_', ' ')} only")
    chosen = _pick_slot(conn, b, day, slot_start)
    if not chosen:
        raise FullError("Those office hours are full that day — join the waitlist")
    slot = (chosen["start"], chosen["end"]) if b["slot_minutes"] else (None, None)
    booking_id = conn.execute(
        "INSERT INTO office_hour_bookings (office_hour_id, student_id, booking_date, notes, "
        "status, created_at, module_code, slot_start, slot_end, mode) VALUES "
        "(?, ?, ?, ?, 'confirmed', ?, ?, ?, ?, ?)",
        (office_hour_id, student_id, day.isoformat(), notes or "", _fmt(now), module_code,
         *slot, mode or (b["mode"] if b["mode"] != "either" else "in_person"))).lastrowid
    conn.execute("UPDATE office_hour_waitlist SET status = 'booked', resolved_at = ? WHERE "
                 "office_hour_id = ? AND booking_date = ? AND student_id = ? AND status = "
                 "'waiting'", (_fmt(now), office_hour_id, day.isoformat(), student_id))
    when = f"{day:%A %d %B} {chosen['start']}–{chosen['end']}"
    emails = _notify(conn, student_id, b["instructor_id"], f"Office hours booked: {when}",
                     _describe(b, day, chosen, module_code, mode)
                     + (f"\n\nWhat you'd like to discuss: {notes}" if notes else ""))
    return {"booking_id": int(booking_id), "when": when, "emails": emails}


def _describe(b, day, slot, module_code, mode):
    where = (f"Online: {b['online_url']}" if (mode or b["mode"]) == "online"
             else f"Location: {b['location']}" + (f" (or online: {b['online_url']})"
                                                  if b["mode"] == "either" and b["online_url"]
                                                  else ""))
    return (f"Office hours with {b['instructor_id']} on {day:%A %d %B %Y}, "
            f"{slot['start']}–{slot['end']}.\n{where}"
            + (f"\nModule: {module_code}" if module_code else ""))


def _notify(conn, student_id, instructor, subject, body) -> list:
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    emails = []
    for ref, sql in ((student_id, "SELECT email_address FROM students WHERE student_id = ?"),
                     (instructor, "SELECT email FROM users WHERE username = ?")):
        if not ref:
            continue
        deliver_inbox_message_on(conn, ref, subject, body)
        try:
            row = conn.execute(sql, (ref,)).fetchone()
        except Exception:
            row = None
        if not row:
            row = conn.execute("SELECT email FROM users WHERE username = ?", (ref,)).fetchone()
        if row and row[0] and "@" in row[0]:
            emails.append((row[0], subject, body))
    return emails


def booking(conn, booking_id) -> dict:
    ensure(conn)
    row = _one(conn, "SELECT * FROM office_hour_bookings WHERE id = ?", (booking_id,))
    if not row:
        raise ValueError("No such booking")
    return row


def _starts(b, bk):
    day = _date(bk["booking_date"])
    return datetime.combine(day, datetime.strptime(bk["slot_start"] or b["start_time"],
                                                   "%H:%M").time())


def _cancel_row(conn, booking_id, actor, reason, b, now=None) -> list:
    bk = booking(conn, booking_id)
    conn.execute("UPDATE office_hour_bookings SET status = 'cancelled', cancelled_at = ?, "
                 "cancelled_by = ?, cancel_reason = ? WHERE id = ?",
                 (_fmt(_now(now)), actor, reason, booking_id))
    day = _date(bk["booking_date"])
    return _notify(conn, bk["student_id"], b["instructor_id"],
                   f"Office hours cancelled: {day:%A %d %B}",
                   f"The office hours booking on {day:%A %d %B} "
                   f"{bk['slot_start'] or b['start_time']} is cancelled"
                   + (f": {reason}" if reason else "."))


def cancel(conn, booking_id, by, *, staff=False, reason="", now=None) -> dict:
    """Cancel a booking. A student may cancel only their own, and not inside
    the cut-off; staff may cancel any. The place goes to the waitlist."""
    now = _now(now)
    bk = booking(conn, booking_id)
    if bk["status"] != "confirmed":
        raise ValueError("That booking is not active")
    b = block(conn, bk["office_hour_id"])
    if not staff:
        if bk["student_id"] != by:
            raise ValueError("You can only cancel your own bookings")
        if _starts(b, bk) - now < timedelta(hours=b["cancel_cutoff_hours"]):
            raise ValueError(f"Bookings can be cancelled up to {b['cancel_cutoff_hours']} "
                             "hour(s) before; contact the member of staff")
    emails = _cancel_row(conn, booking_id, by, reason or ("cancelled by the student" if not staff
                                                          else "cancelled by staff"), b, now)
    emails += _promote(conn, b, bk["booking_date"], now)
    return {"emails": emails}


def reschedule(conn, booking_id, by, new_date, *, slot_start=None, staff=False,
               now=None) -> dict:
    """Move a booking: the new place is taken first, then the old released."""
    bk = booking(conn, booking_id)
    if bk["status"] != "confirmed":
        raise ValueError("That booking is not active")
    if not staff and bk["student_id"] != by:
        raise ValueError("You can only move your own bookings")
    conn.execute("UPDATE office_hour_bookings SET status = 'rescheduled' WHERE id = ?",
                 (booking_id,))
    new = book(conn, bk["office_hour_id"], bk["student_id"], new_date, slot_start=slot_start,
               module_code=bk["module_code"], notes=bk["notes"], mode=bk["mode"], now=now)
    b = block(conn, bk["office_hour_id"])
    conn.execute("UPDATE office_hour_bookings SET cancelled_at = ?, cancelled_by = ?, "
                 "cancel_reason = ? WHERE id = ?",
                 (_fmt(_now(now)), by, f"moved to booking #{new['booking_id']}", booking_id))
    new["emails"] += _promote(conn, b, bk["booking_date"], _now(now))
    return new


# ── waitlist ────────────────────────────────────────────────────────────


def join_waitlist(conn, office_hour_id, student_id, booking_date, module_code=None,
                  notes="") -> int:
    b = block(conn, office_hour_id)
    day = _date(booking_date)
    problem = _date_problem(conn, b, day, _now())
    if problem:
        raise ValueError(f"Cannot wait for that date: {problem}")
    if conn.execute("SELECT 1 FROM office_hour_waitlist WHERE office_hour_id = ? AND "
                    "booking_date = ? AND student_id = ? AND status = 'waiting'",
                    (office_hour_id, day.isoformat(), student_id)).fetchone():
        raise ValueError("You are already waiting for that date")
    position = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM office_hour_waitlist "
                            "WHERE office_hour_id = ? AND booking_date = ? AND status = "
                            "'waiting'", (office_hour_id, day.isoformat())).fetchone()[0]
    conn.execute("INSERT INTO office_hour_waitlist (office_hour_id, booking_date, student_id, "
                 "module_code, notes, position) VALUES (?, ?, ?, ?, ?, ?)",
                 (office_hour_id, day.isoformat(), student_id, module_code, notes, position))
    return int(position)


def _promote(conn, b, booking_date, now) -> list:
    """Book the first person waiting who can take the freed place."""
    emails = []
    for w in _dicts(conn.execute("SELECT * FROM office_hour_waitlist WHERE office_hour_id = ? "
                                 "AND booking_date = ? AND status = 'waiting' ORDER BY position",
                                 (b["id"], str(booking_date)[:10]))):
        free = [s for s in slots(conn, b["id"], booking_date) if s["free"]]
        if not free:
            break
        try:
            made = book(conn, b["id"], w["student_id"], booking_date, slot_start=free[0]["start"],
                        module_code=w["module_code"], notes=w["notes"] or "", now=now)
        except ValueError:
            continue
        emails += made["emails"]
    return emails


# ── the instructor's side ───────────────────────────────────────────────


def cancel_date(conn, office_hour_id, cancel_on, reason, actor) -> dict:
    """The block does not run on one date: bookings and waitlist are
    cancelled and everyone booked is told."""
    b = block(conn, office_hour_id)
    day = _date(cancel_on)
    if DAYS[day.weekday()] != b["day_of_week"]:
        raise ValueError(f"These office hours run on {b['day_of_week']}s")
    if not (reason or "").strip():
        raise ValueError("Give a reason; it is sent to the students")
    try:
        exception_id = conn.execute("INSERT INTO office_hour_exceptions (office_hour_id, "
                                    "exception_date, reason, created_by) VALUES (?, ?, ?, ?)",
                                    (office_hour_id, day.isoformat(), reason.strip(),
                                     actor)).lastrowid
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError("That date is already cancelled") from None
        raise
    emails = []
    booked = _dicts(conn.execute("SELECT id FROM office_hour_bookings WHERE office_hour_id = ? "
                                 "AND booking_date = ? AND status = 'confirmed'",
                                 (office_hour_id, day.isoformat())))
    for bk in booked:
        emails += _cancel_row(conn, bk["id"], actor, reason.strip(), b)
    conn.execute("UPDATE office_hour_waitlist SET status = 'expired', resolved_at = datetime("
                 "'now') WHERE office_hour_id = ? AND booking_date = ? AND status = 'waiting'",
                 (office_hour_id, day.isoformat()))
    return {"exception_id": int(exception_id), "cancelled": len(booked), "emails": emails}


def exceptions(conn, office_hour_id) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT * FROM office_hour_exceptions WHERE office_hour_id = ? "
                               "ORDER BY exception_date", (office_hour_id,)))


def reinstate_date(conn, exception_id) -> bool:
    ensure(conn)
    return conn.execute("DELETE FROM office_hour_exceptions WHERE id = ?",
                        (exception_id,)).rowcount > 0


def record_meeting(conn, booking_id, attendance, notes="", actions="", actor=None,
                   now=None) -> None:
    bk = booking(conn, booking_id)
    b = block(conn, bk["office_hour_id"])
    if attendance not in schema.ATTENDANCE:
        raise ValueError(f"Attendance is one of: {', '.join(schema.ATTENDANCE)}")
    if bk["status"] != "confirmed":
        raise ValueError("Only a booking that went ahead can have a meeting record")
    if _starts(b, bk) > _now(now):
        raise ValueError("The meeting has not happened yet")
    conn.execute("UPDATE office_hour_bookings SET attendance = ?, meeting_notes = ?, actions = ?, "
                 "recorded_by = ?, recorded_at = ? WHERE id = ?",
                 (attendance, (notes or "").strip() or None, (actions or "").strip() or None,
                  actor, _fmt(_now(now)), booking_id))


def send_reminders(conn, now=None) -> dict:
    """Remind students of tomorrow's (next 24 hours') bookings, once each."""
    ensure(conn)
    now = _now(now)
    emails, sent = [], 0
    for bk in _dicts(conn.execute(
            "SELECT b.*, o.instructor_id FROM office_hour_bookings b JOIN office_hours o ON "
            "o.id = b.office_hour_id WHERE b.status = 'confirmed' AND b.reminder_sent_at IS NULL "
            "AND b.booking_date BETWEEN ? AND ?",
            (now.date().isoformat(), (now + timedelta(hours=REMINDER_HOURS)).date().isoformat()))):
        b = block(conn, bk["office_hour_id"])
        begins = _starts(b, bk)
        if not now < begins <= now + timedelta(hours=REMINDER_HOURS):
            continue
        slot = {"start": bk["slot_start"] or b["start_time"], "end": bk["slot_end"] or b["end_time"]}
        emails += _notify(conn, bk["student_id"], None, "Reminder: office hours appointment",
                          _describe(b, begins.date(), slot, bk["module_code"], bk["mode"]))
        conn.execute("UPDATE office_hour_bookings SET reminder_sent_at = ? WHERE id = ?",
                     (_fmt(now), bk["id"]))
        sent += 1
    return {"sent": sent, "emails": emails}


# ── finding office hours ────────────────────────────────────────────────


def teaching_staff(conn, student_id) -> dict[str, list[str]]:
    """``{username: [module codes]}`` for the staff teaching a student's modules."""
    from education_system.systems.university.application.modules import delivery as module_delivery
    out: dict[str, list[str]] = {}
    for (code,) in conn.execute("SELECT module_code FROM student_modules WHERE student_id = ? "
                                "AND LOWER(COALESCE(status, '')) = 'enrolled'",
                                (str(student_id),)).fetchall():
        people = {m["username"] for m in module_delivery.team(conn, code)}
        leader = module_delivery.leader(conn, code)
        if leader:
            people.add(leader)
        for person in people:
            out.setdefault(person, []).append(code)
    return out


def available(conn, *, student_id=None, mine_only=False) -> list[dict]:
    """Active blocks, each with its next bookable date and — for a student —
    which of their modules that member of staff teaches."""
    ensure(conn)
    staff = teaching_staff(conn, student_id) if student_id else {}
    rows = _dicts(conn.execute("SELECT * FROM office_hours WHERE is_active = 1 ORDER BY "
                               "instructor_id, CASE day_of_week " + " ".join(
                                   f"WHEN '{d}' THEN {i}" for i, d in enumerate(DAYS))
                               + " END, start_time"))
    out = []
    for r in rows:
        modules = staff.get(r["instructor_id"], [])
        if mine_only and not modules:
            continue
        upcoming = dates(conn, r["id"], weeks=4)
        out.append(dict(r, my_modules=modules, next_date=upcoming[0] if upcoming else None,
                        mode=r.get("mode") or "in_person"))
    return out


def bookings_for(conn, *, student_id=None, instructor=None, include_past=False) -> list[dict]:
    ensure(conn)
    sql = ("SELECT b.*, o.instructor_id, o.day_of_week, o.start_time, o.end_time, o.location, "
           "o.online_url, o.mode AS block_mode FROM office_hour_bookings b JOIN office_hours o "
           "ON o.id = b.office_hour_id WHERE 1 = 1")
    params = []
    if student_id:
        sql += " AND b.student_id = ?"
        params.append(student_id)
    if instructor:
        sql += " AND o.instructor_id = ?"
        params.append(instructor)
    if not include_past:
        sql += " AND b.booking_date >= ?"
        params.append(date.today().isoformat())
    return _dicts(conn.execute(sql + " ORDER BY b.booking_date, COALESCE(b.slot_start, "
                                     "o.start_time)", params))


def ical(bookings) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//University//Office hours//EN"]
    for bk in bookings:
        if bk["status"] != "confirmed":
            continue
        day = bk["booking_date"].replace("-", "")
        start = (bk["slot_start"] or bk["start_time"]).replace(":", "")
        end = (bk["slot_end"] or bk["end_time"]).replace(":", "")
        online = bk.get("mode") == "online"
        lines += ["BEGIN:VEVENT", f"UID:office-hours-{bk['id']}@university", f"DTSTAMP:{stamp}",
                  f"DTSTART:{day}T{start}00", f"DTEND:{day}T{end}00",
                  f"SUMMARY:Office hours with {bk['instructor_id']}"
                  + (f" ({bk['module_code']})" if bk.get("module_code") else ""),
                  f"LOCATION:{'Online' if online else bk['location']}"]
        if bk.get("online_url") and online:
            lines.append(f"URL:{bk['online_url']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ── reporting ───────────────────────────────────────────────────────────


def report(conn, since, until) -> list[dict]:
    """Per member of staff: places offered, booked, attended, no-shows,
    cancelled; how full the sessions were and the no-show rate."""
    ensure(conn)
    start, end = _date(since), _date(until)
    out = {}
    for b in _dicts(conn.execute("SELECT * FROM office_hours")):
        row = out.setdefault(b["instructor_id"], {"instructor": b["instructor_id"], "offered": 0,
                                                  "booked": 0, "attended": 0, "no_show": 0,
                                                  "cancelled": 0, "modules": {}})
        day = start
        while day <= end and b["is_active"]:
            if DAYS[day.weekday()] == b["day_of_week"] and not conn.execute(
                    "SELECT 1 FROM office_hour_exceptions WHERE office_hour_id = ? AND "
                    "exception_date = ?", (b["id"], day.isoformat())).fetchone():
                row["offered"] += b["capacity"] or 0
            day += timedelta(days=1)
        for bk in _dicts(conn.execute("SELECT status, attendance, module_code FROM "
                                      "office_hour_bookings WHERE office_hour_id = ? AND "
                                      "booking_date BETWEEN ? AND ?",
                                      (b["id"], start.isoformat(), end.isoformat()))):
            _tally(row, bk)
    for row in out.values():
        row["fill_pct"] = round(row["booked"] / row["offered"] * 100, 1) if row["offered"] else None
        recorded = row["attended"] + row["no_show"]
        row["no_show_pct"] = round(row["no_show"] / recorded * 100, 1) if recorded else None
    return sorted(out.values(), key=lambda r: r["instructor"])


def _tally(row, bk):
    if bk["status"] == "cancelled":
        row["cancelled"] += 1
        return
    if bk["status"] != "confirmed":
        return
    row["booked"] += 1
    row["modules"][bk["module_code"] or "—"] = row["modules"].get(bk["module_code"] or "—", 0) + 1
    if bk["attendance"] == "attended":
        row["attended"] += 1
    elif bk["attendance"] == "no_show":
        row["no_show"] += 1


# ── the staff directory ─────────────────────────────────────────────────


def _directory_exists(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(staff_office_hours_directory)")}


def sync_directory(conn, office_hour_id) -> None:
    """Mirror one block into the staff directory (or remove it when retired)."""
    cols = _directory_exists(conn)
    if "office_hour_id" not in cols:
        return
    b = _one(conn, "SELECT * FROM office_hours WHERE id = ?", (office_hour_id,))
    conn.execute("DELETE FROM staff_office_hours_directory WHERE office_hour_id = ?",
                 (office_hour_id,))
    if not b or not b["is_active"]:
        return
    conn.execute("INSERT INTO staff_office_hours_directory (user_id, day_of_week, start_time, "
                 "end_time, location, virtual_link, is_by_appointment, office_hour_id) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (b["instructor_id"], b["day_of_week"], b["start_time"], b["end_time"],
                  None if b.get("mode") == "online" else b["location"], b.get("online_url"),
                  1 if b.get("slot_minutes") else 0, office_hour_id))


def directory_only(conn, username) -> list[dict]:
    """Directory entries for a person that are not bookable yet."""
    if "office_hour_id" not in _directory_exists(conn):
        return []
    return _dicts(conn.execute("SELECT * FROM staff_office_hours_directory WHERE user_id = ? "
                               "AND office_hour_id IS NULL", (username,)))


def make_bookable(conn, directory_id, capacity=5, slot_minutes=None, actor=None) -> int:
    """Turn a hand-entered directory entry into bookable office hours."""
    row = _one(conn, "SELECT * FROM staff_office_hours_directory WHERE hours_id = ? AND "
                     "office_hour_id IS NULL", (directory_id,))
    if not row:
        raise ValueError("That directory entry is already bookable or gone")
    day = row["day_of_week"]
    if str(day).isdigit():
        day = DAYS[int(day) % 7]
    office_hour_id = save_block(conn, {
        "instructor_id": row["user_id"], "day_of_week": day, "start_time": row["start_time"],
        "end_time": row["end_time"], "location": row["location"] or "",
        "online_url": row["virtual_link"], "capacity": capacity, "slot_minutes": slot_minutes,
        "mode": "online" if row["virtual_link"] and not row["location"] else (
            "either" if row["virtual_link"] else "in_person")}, actor=actor)
    conn.execute("DELETE FROM staff_office_hours_directory WHERE hours_id = ?", (directory_id,))
    return office_hour_id
