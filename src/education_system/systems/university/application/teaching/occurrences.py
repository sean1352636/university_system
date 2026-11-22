"""When timetabled sessions actually happen, and who needs to know.

A ``module_schedule`` row is a weekly pattern. Every timetable view used to
draw it in every week of the year — through holidays, outside its term,
after its ``recurrence_until`` — and to everyone who had ever enrolled. This
module is the one rule that turns patterns into dated sessions:

* a slot runs only inside the terms it belongs to: its delivery's term when
  it is tied to one (``section_id``), otherwise the terms whose name matches
  its ``semester`` (and whose dates include its ``year``, when set). With no
  terms defined at all, every week counts;
* never on a holiday, never after ``recurrence_until``;
* only in the teaching weeks of its ``week_pattern`` (week 1 is the week the
  term starts in), e.g. ``1-5,7-11`` around a reading week;
* one-off changes in ``module_session_changes`` cancel a single session or
  move it to another date / time / room.

It also checks rooms against ``room_bookings`` (exams, events) both ways,
room size against enrolment, and staff hours / preferences, and sends
change notices — to the Hub inbox (``messages``) and by email — to enrolled
students on the right delivery and to the instructor.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from education_system.systems.university.application.attendance import registers
from education_system.systems.university.infrastructure.database.schemas import (
    timetable_schema as schema,
)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_RANGE = re.compile(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})")
_PERIODS = {"morning": ("00:00", "12:00"), "afternoon": ("12:00", "17:00"),
            "evening": ("17:00", "23:59")}
#: How far outside a requested range to look for sessions moved into it.
_MOVE_MARGIN = timedelta(days=31)


def ensure(conn):
    schema.apply_to_connection(conn)
    from education_system.systems.university.services.bus.enrolment_bus import (
        ensure_section_column,
    )
    ensure_section_column(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _d(value):
    return registers._d(value)


def _minutes(t):
    h, m = str(t)[:5].split(":")
    return int(h) * 60 + int(m)


def _overlap(a_start, a_end, b_start, b_end):
    return str(a_start)[:5] < str(b_end)[:5] and str(a_end)[:5] > str(b_start)[:5]


def check_time(start, end):
    for t in (start, end):
        if not _TIME.match(str(t or "")):
            raise ValueError("Times must be HH:MM, e.g. 09:00")
    if start >= end:
        raise ValueError("The session must end after it starts")


# ── weekly slots ────────────────────────────────────────────────────────

_SLOT_SQL = (
    "SELECT ms.id, ms.module_code, COALESCE(m.module_name, '') AS module_name, "
    "ms.day_of_week, ms.start_time, ms.end_time, "
    "COALESCE(ms.session_type, 'Lecture') AS session_type, ms.room_id, "
    "TRIM(COALESCE(r.building, '') || ' ' || COALESCE(r.room_number, r.room_name, '')) AS room, "
    "r.capacity AS room_capacity, ms.instructor_id, "
    "TRIM(COALESCE(i.first_name, '') || ' ' || COALESCE(i.last_name, '')) AS instructor, "
    "ms.semester, ms.year, ms.recurrence_until, ms.section_id, ms.week_pattern, ms.online_url "
    "FROM module_schedule ms LEFT JOIN modules m ON m.module_code = ms.module_code "
    "LEFT JOIN rooms r ON r.id = ms.room_id LEFT JOIN instructors i ON i.id = ms.instructor_id "
    "WHERE COALESCE(ms.status, 'published') = 'published'")


def slots(conn, *, module_codes=None, instructor_id=None, room_id=None, slot_id=None):
    """Published weekly slots, optionally narrowed."""
    ensure(conn)
    sql, params = _SLOT_SQL, []
    for column, value in (("ms.instructor_id", instructor_id), ("ms.room_id", room_id),
                          ("ms.id", slot_id)):
        if value not in (None, ""):
            sql += f" AND {column} = ?"
            params.append(value)
    if module_codes is not None:
        if not module_codes:
            return []
        sql += f" AND ms.module_code IN ({', '.join('?' for _ in module_codes)})"
        params += list(module_codes)
    # db-audit: ignore[DBW001] - only literal column names and placeholders
    return _dicts(conn.execute(sql + " ORDER BY ms.module_code, ms.day_of_week, ms.start_time",
                               params))


def student_enrolments(conn, student_id) -> dict:
    """``{module_code: section_id}`` for the student's current enrolments."""
    ensure(conn)
    return {r[0]: r[1] for r in conn.execute(
        "SELECT module_code, section_id FROM student_modules WHERE student_id = ? "
        "AND LOWER(COALESCE(status, '')) = 'enrolled'", (str(student_id),))}


def student_slots(conn, student_id):
    """Weekly slots of the modules a student is on now — and, where a module
    runs in deliveries, only the slots for the student's delivery."""
    enrolled = student_enrolments(conn, student_id)
    return [s for s in slots(conn, module_codes=list(enrolled))
            if s["section_id"] in (None, enrolled.get(s["module_code"]))]


# ── terms, weeks ────────────────────────────────────────────────────────


def terms(conn) -> list[tuple]:
    """``[(name, start, end)]`` from ``academic_terms``."""
    try:
        rows = conn.execute("SELECT name, start_date, end_date FROM academic_terms WHERE "
                            "COALESCE(status, '') <> 'Superseded'").fetchall()
    except Exception:
        return []
    return [(r[0], _d(r[1]), _d(r[2])) for r in rows if _d(r[1]) and _d(r[2])]


def _section_terms(conn) -> dict:
    try:
        rows = conn.execute("SELECT s.id, t.name, t.start_date, t.end_date FROM course_sections s "
                            "JOIN academic_terms t ON t.id = s.term_id").fetchall()
    except Exception:
        return {}
    return {r[0]: (r[1], _d(r[2]), _d(r[3])) for r in rows if _d(r[2]) and _d(r[3])}


def _term_matches(slot, term):
    name, start, end = term
    semester = str(slot.get("semester") or "").strip().lower()
    if semester and semester not in str(name or "").lower():
        return False
    try:
        year = int(slot.get("year") or 0)
    except (TypeError, ValueError):
        year = 0
    return not year or year in (start.year, end.year)


def windows(slot, all_terms, section_terms):
    """The term(s) a slot runs in, as ``[(name, start, end)]``."""
    if slot.get("section_id") in section_terms:
        return [section_terms[slot["section_id"]]]
    if not all_terms:
        return [(None, date.min, date.max)]
    return [t for t in all_terms if _term_matches(slot, t)]


def parse_weeks(text):
    """``'1-5,7-11'`` -> {1..5, 7..11}; blank -> None (every week)."""
    text = str(text or "").replace(" ", "")
    if not text:
        return None
    weeks = set()
    for part in text.split(","):
        low, _, high = part.partition("-")
        if not low.isdigit() or (high and not high.isdigit()):
            raise ValueError("Teaching weeks look like 1-5,7-11")
        low, high = int(low), int(high or low)
        if not 1 <= low <= high <= 52:
            raise ValueError("Teaching weeks run from 1 to 52")
        weeks.update(range(low, high + 1))
    return weeks


def _monday(d):
    return d - timedelta(days=d.weekday())


def _base_dates(slot, window, start, end, holidays):
    """``(date, teaching_week)`` for each normal run of *slot* in *window*."""
    target = next((i for i, d in enumerate(DAYS)
                   if str(slot.get("day_of_week") or "").strip().lower() == d.lower()), None)
    _name, w_start, w_end = window
    until = _d(slot.get("recurrence_until")) or date.max
    low, high = max(start, w_start), min(end, w_end, until)
    if target is None or low > high:
        return
    weeks = parse_weeks(slot.get("week_pattern"))
    first_monday = _monday(w_start) if w_start != date.min else None
    day = low + timedelta(days=(target - low.weekday()) % 7)
    while day <= high:
        week = (day - first_monday).days // 7 + 1 if first_monday else None
        if day not in holidays and (weeks is None or week in weeks):
            yield day, week
        day += timedelta(days=7)


# ── occurrences ─────────────────────────────────────────────────────────


def _changes(conn, slot_ids):
    if not slot_ids:
        return {}
    rows = _dicts(conn.execute(
        "SELECT c.*, TRIM(COALESCE(r.building, '') || ' ' || COALESCE(r.room_number, "
        "r.room_name, '')) AS new_room FROM module_session_changes c "
        "LEFT JOIN rooms r ON r.id = c.new_room_id "
        f"WHERE c.schedule_id IN ({', '.join('?' for _ in slot_ids)})", list(slot_ids)))
    return {(r["schedule_id"], r["session_date"]): r for r in rows}


def _apply_change(occ, change):
    if change["action"] == "cancel":
        occ.update(status="cancelled", reason=change["reason"], change_id=change["id"])
        return occ
    occ.update(status="moved", moved_from=occ["date"], reason=change["reason"],
               change_id=change["id"], date=change["new_date"],
               start_time=change["new_start"] or occ["start_time"],
               end_time=change["new_end"] or occ["end_time"])
    if change["new_room_id"]:
        occ.update(room_id=change["new_room_id"], room=change["new_room"])
    return occ


def occurrences(conn, start, end, slot_list) -> list[dict]:
    """Dated sessions of *slot_list* between *start* and *end* (inclusive).

    Each is the slot's fields plus ``date``, ``week``, ``term`` and ``status``
    (``scheduled`` / ``cancelled`` / ``moved``; moved ones carry
    ``moved_from``). Cancelled sessions are kept so views can show them.
    """
    start, end = _d(start) or start, _d(end) or end
    all_terms, section_terms = terms(conn), _section_terms(conn)
    holidays = registers.holiday_dates(conn)
    changes = _changes(conn, [s["id"] for s in slot_list])
    seen, out = set(), []
    for slot in slot_list:
        for window in windows(slot, all_terms, section_terms):
            for day, week in _base_dates(slot, window, start - _MOVE_MARGIN,
                                         end + _MOVE_MARGIN, holidays):
                key = (slot["id"], day.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                occ = dict(slot, date=day.isoformat(), week=week, term=window[0],
                           status="scheduled")
                if key in changes:
                    occ = _apply_change(occ, changes[key])
                if start.isoformat() <= occ["date"] <= end.isoformat():
                    out.append(occ)
    return sorted(out, key=lambda o: (o["date"], o["start_time"] or "", o["module_code"]))


def unplaced(conn, slot_list) -> list[dict]:
    """Slots that match no term at all, so never appear on a timetable."""
    all_terms, section_terms = terms(conn), _section_terms(conn)
    return [s for s in slot_list if not windows(s, all_terms, section_terms)]


def for_student(conn, student_id, start, end):
    return occurrences(conn, start, end, student_slots(conn, student_id))


def for_instructor(conn, instructor_id, start, end):
    """Only the sessions this instructor takes — not every session of every
    module they teach on."""
    return occurrences(conn, start, end, slots(conn, instructor_id=instructor_id))


def for_module(conn, code, start, end):
    return occurrences(conn, start, end, slots(conn, module_codes=[code]))


def bookings(conn, room_id, start, end) -> list[dict]:
    """Confirmed ``room_bookings`` for a room overlapping the dates."""
    try:
        return _dicts(conn.execute(
            "SELECT booking_id, booking_type, purpose, booked_by, start_datetime, end_datetime "
            "FROM room_bookings WHERE room_id = ? AND COALESCE(booking_status, 'confirmed') "
            "<> 'cancelled' AND date(start_datetime) <= date(?) AND date(end_datetime) >= date(?) "
            "ORDER BY start_datetime", (room_id, str(end), str(start))))
    except Exception as exc:
        if "no such table" in str(exc):
            return []
        raise


def for_room(conn, room_id, start, end):
    """Timetabled sessions in the room (including ones moved into it) plus
    its bookings, as ``(sessions, bookings)``."""
    every = occurrences(conn, start, end, slots(conn))
    here = [o for o in every if str(o.get("room_id")) == str(room_id)]
    return here, bookings(conn, room_id, start, end)


# ── clashes and warnings ────────────────────────────────────────────────


def booking_clashes_for_slot(conn, room_id, day, start, end) -> list[tuple]:
    """Future room bookings on *day*'s weekday overlapping a weekly slot, as
    ``(booking_id, label, start, end)`` — the shape the scheduler's room
    conflict checks return."""
    if not room_id or day not in DAYS:
        return []
    weekday = (DAYS.index(day) + 1) % 7  # SQLite %w: Sunday = 0
    try:
        rows = conn.execute(
            "SELECT booking_id, purpose, start_datetime, end_datetime FROM room_bookings "
            "WHERE room_id = ? AND COALESCE(booking_status, 'confirmed') <> 'cancelled' "
            "AND date(start_datetime) >= date('now') AND CAST(strftime('%w', start_datetime) "
            "AS INTEGER) = ? AND time(start_datetime) < time(?) AND time(end_datetime) > time(?)",
            (room_id, weekday, end, start)).fetchall()
    except Exception as exc:
        if "no such table" in str(exc):
            return []
        raise
    return [(f"booking:{r[0]}", f"Room booking: {r[1] or 'booked'} on {str(r[2])[:10]}",
             str(r[2])[11:16], str(r[3])[11:16]) for r in rows]


def timetable_clash_for_booking(conn, room_id, start_dt, end_dt):
    """A timetabled session in the room during a proposed booking, or None."""
    s, e = _dt(start_dt), _dt(end_dt)
    sessions, _ = for_room(conn, room_id, s.date(), e.date())
    for o in sessions:
        if o["status"] == "cancelled":
            continue
        o_start = _dt(f"{o['date']} {o['start_time']}")
        o_end = _dt(f"{o['date']} {o['end_time']}")
        if o_start < e and o_end > s:
            return (f"{o['module_code']} {o['session_type']} {o['date']} "
                    f"{o['start_time']}–{o['end_time']}")
    return None


def _dt(value):
    return datetime.strptime(str(value).replace("T", " ")[:16], "%Y-%m-%d %H:%M")


def enrolled_for(conn, code, section_id=None) -> int:
    ensure(conn)
    sql = ("SELECT COUNT(*) FROM student_modules WHERE module_code = ? "
           "AND LOWER(COALESCE(status, '')) = 'enrolled'")
    params = [code]
    if section_id:
        sql += " AND section_id = ?"
        params.append(section_id)
    return conn.execute(sql, params).fetchone()[0]


def capacity_warning(conn, code, room_id, section_id=None):
    if not room_id:
        return None
    row = conn.execute("SELECT capacity, TRIM(COALESCE(building, '') || ' ' || "
                       "COALESCE(room_number, room_name, '')) FROM rooms WHERE id = ?",
                       (room_id,)).fetchone()
    if not row or not row[0]:
        return None
    expected = enrolled_for(conn, code, section_id)
    if section_id:
        places = conn.execute("SELECT capacity FROM course_sections WHERE id = ?",
                              (section_id,)).fetchone()
        expected = max(expected, places[0] if places and places[0] else 0)
    if expected > row[0]:
        return f"room {row[1]} holds {row[0]} but {expected} students are expected"
    return None


def _preferred_ranges(text):
    text = str(text or "").lower()
    ranges = [(a.zfill(5), b.zfill(5)) for a, b in _RANGE.findall(text)]
    ranges += [span for word, span in _PERIODS.items() if word in text]
    return ranges


def _instructor(conn, instructor_id):
    cur = conn.execute("SELECT TRIM(first_name || ' ' || last_name) AS name, "
                       "max_hours_per_week, preferred_days, preferred_times "
                       "FROM instructors WHERE id = ?", (instructor_id,))
    rows = _dicts(cur)
    return rows[0] if rows else None


def weekly_hours(conn, instructor_id, exclude_slot=None) -> float:
    total = 0
    for s in slots(conn, instructor_id=instructor_id):
        if s["id"] != exclude_slot and s["start_time"] and s["end_time"]:
            total += _minutes(s["end_time"]) - _minutes(s["start_time"])
    return total / 60


def staff_warnings(conn, instructor_id, day, start, end, exclude_slot=None) -> list[str]:
    """Weekly hours over the instructor's maximum, or a slot outside their
    preferred days / times."""
    who = _instructor(conn, instructor_id) if instructor_id else None
    if not who:
        return []
    out = []
    hours = weekly_hours(conn, instructor_id, exclude_slot) + (_minutes(end) - _minutes(start)) / 60
    if who["max_hours_per_week"] and hours > who["max_hours_per_week"]:
        out.append(f"{who['name']} would teach {hours:g} h a week (maximum "
                   f"{who['max_hours_per_week']})")
    days = [d.strip().lower()[:3] for d in str(who["preferred_days"] or "").split(",") if d.strip()]
    if days and day.lower()[:3] not in days:
        out.append(f"{who['name']} prefers {who['preferred_days']}")
    ranges = _preferred_ranges(who["preferred_times"])
    if ranges and not any(a <= start and end <= b for a, b in ranges):
        out.append(f"{who['name']} prefers {who['preferred_times']}")
    return out


def slot_warnings(conn, code, day, start, end, room_id=None, instructor_id=None,
                  section_id=None, exclude_slot=None) -> list[str]:
    """Everything beyond a straight timetable clash: room bookings, room size,
    staff hours and preferences."""
    out = [label for _id, label, _s, _e in booking_clashes_for_slot(conn, room_id, day, start, end)]
    room = capacity_warning(conn, code, room_id, section_id)
    if room:
        out.append(room)
    return out + staff_warnings(conn, instructor_id, day, start, end, exclude_slot)


def capacity_issues(conn) -> list[str]:
    out = []
    for s in slots(conn):
        warning = capacity_warning(conn, s["module_code"], s["room_id"], s["section_id"])
        if warning:
            out.append(f"{s['module_code']} {s['day_of_week']} {s['start_time']}: {warning}")
    return out


def staff_issues(conn) -> list[str]:
    out = []
    for (iid,) in conn.execute("SELECT DISTINCT instructor_id FROM module_schedule "
                               "WHERE instructor_id IS NOT NULL AND COALESCE(status, "
                               "'published') = 'published'").fetchall():
        who = _instructor(conn, iid)
        if not who:
            continue
        hours = weekly_hours(conn, iid)
        if who["max_hours_per_week"] and hours > who["max_hours_per_week"]:
            out.append(f"{who['name']}: {hours:g} h a week, maximum {who['max_hours_per_week']}")
        for s in slots(conn, instructor_id=iid):
            out += [f"{s['module_code']} {s['day_of_week']} {s['start_time']}: {w}"
                    for w in staff_warnings(conn, iid, s["day_of_week"], s["start_time"],
                                            s["end_time"], exclude_slot=s["id"])
                    if "prefers" in w]
    return out


# ── one-off changes ─────────────────────────────────────────────────────


def _the_occurrence(conn, schedule_id, session_date):
    slot = slots(conn, slot_id=schedule_id)
    if not slot:
        raise ValueError("That weekly session no longer exists")
    day = _d(session_date)
    if not day:
        raise ValueError("Dates are YYYY-MM-DD")
    # The date given may be where the session normally runs or where it was
    # moved to; look either side so both are found.
    for occ in occurrences(conn, day - _MOVE_MARGIN, day + _MOVE_MARGIN, slot):
        if day.isoformat() in (occ["date"], occ.get("moved_from")):
            return occ
    raise ValueError(f"{slot[0]['module_code']} does not run on {session_date}")


def date_clashes(conn, day, start, end, *, room_id=None, instructor_id=None,
                 exclude=None) -> list[str]:
    """Sessions and bookings on one date that would collide."""
    out = []
    d = _d(day)
    for o in occurrences(conn, d, d, slots(conn)):
        if o["status"] == "cancelled" or (o["id"], o.get("moved_from", o["date"])) == exclude:
            continue
        same = [w for w, hit in (("room", room_id and str(o["room_id"]) == str(room_id)),
                                 ("instructor", instructor_id and o["instructor_id"] == instructor_id))
                if hit]
        if same and _overlap(o["start_time"], o["end_time"], start, end):
            out.append(f"{o['module_code']} {o['start_time']}–{o['end_time']} ({' and '.join(same)})")
    for b in bookings(conn, room_id, d, d) if room_id else []:
        if _overlap(str(b["start_datetime"])[11:16], str(b["end_datetime"])[11:16], start, end):
            out.append(f"room booking: {b['purpose'] or b['booking_type']}")
    return out


def _record(conn, schedule_id, session_date, action, reason, actor, **new):
    conn.execute("DELETE FROM module_session_changes WHERE schedule_id = ? AND session_date = ?",
                 (schedule_id, session_date))
    cur = conn.execute(
        "INSERT INTO module_session_changes (schedule_id, session_date, action, new_date, "
        "new_start, new_end, new_room_id, reason, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (schedule_id, session_date, action, new.get("new_date"), new.get("new_start"),
         new.get("new_end"), new.get("new_room_id"), reason, actor))
    return int(cur.lastrowid)


def cancel_session(conn, schedule_id, session_date, reason, actor) -> dict:
    """Cancel one week's session. Returns ``{change_id, emails}``."""
    if not (reason or "").strip():
        raise ValueError("Give a reason; it is sent to the students")
    occ = _the_occurrence(conn, schedule_id, session_date)
    original = occ.get("moved_from", occ["date"])
    change = _record(conn, schedule_id, original, "cancel", reason.strip(), actor)
    emails = notify(conn, occ["module_code"], f"{occ['module_code']} cancelled on {original}",
                    f"The {occ['session_type']} for {occ['module_code']} {occ['module_name']} "
                    f"on {original} at {occ['start_time']} is cancelled.\n\nReason: {reason}",
                    section_id=occ["section_id"], instructor_id=occ["instructor_id"])
    return {"change_id": change, "emails": emails}


def move_session(conn, schedule_id, session_date, *, new_date, new_start, new_end,
                 new_room_id=None, reason, actor, force=False) -> dict:
    """Move one week's session to another date / time / room.
    Raises ValueError listing clashes unless *force*."""
    if not (reason or "").strip():
        raise ValueError("Give a reason; it is sent to the students")
    target = _d(new_date)
    if not target:
        raise ValueError("New date must be YYYY-MM-DD")
    check_time(new_start, new_end)
    occ = _the_occurrence(conn, schedule_id, session_date)
    original = occ.get("moved_from", occ["date"])
    room = new_room_id or occ["room_id"]
    clashes = date_clashes(conn, target, new_start, new_end, room_id=room,
                           instructor_id=occ["instructor_id"], exclude=(schedule_id, original))
    if clashes and not force:
        raise ValueError("Clashes with: " + "; ".join(clashes))
    change = _record(conn, schedule_id, original, "move", reason.strip(), actor,
                     new_date=target.isoformat(), new_start=new_start, new_end=new_end,
                     new_room_id=new_room_id or None)
    where = ""
    if new_room_id:
        row = conn.execute("SELECT TRIM(COALESCE(building, '') || ' ' || COALESCE(room_number, "
                           "room_name, '')) FROM rooms WHERE id = ?", (new_room_id,)).fetchone()
        where = f" in {row[0]}" if row else ""
    emails = notify(conn, occ["module_code"], f"{occ['module_code']} on {original} has moved",
                    f"The {occ['session_type']} for {occ['module_code']} {occ['module_name']} "
                    f"on {original} at {occ['start_time']} now takes place on {target:%A %d %B} "
                    f"{new_start}–{new_end}{where}.\n\nReason: {reason}",
                    section_id=occ["section_id"], instructor_id=occ["instructor_id"])
    return {"change_id": change, "emails": emails}


def restore_session(conn, change_id, actor) -> dict:
    """Undo a cancellation or move."""
    rows = _dicts(conn.execute(
        "SELECT c.*, ms.module_code, ms.section_id, ms.instructor_id, ms.start_time "
        "FROM module_session_changes c JOIN module_schedule ms ON ms.id = c.schedule_id "
        "WHERE c.id = ?", (change_id,)))
    if not rows:
        raise ValueError("That change no longer exists")
    c = rows[0]
    conn.execute("DELETE FROM module_session_changes WHERE id = ?", (change_id,))
    emails = notify(conn, c["module_code"], f"{c['module_code']} on {c['session_date']} is back on",
                    f"The {c['module_code']} session on {c['session_date']} at {c['start_time']} "
                    f"goes ahead as originally timetabled.",
                    section_id=c["section_id"], instructor_id=c["instructor_id"])
    return {"emails": emails, "by": actor}


def session_changes(conn, module_code=None) -> list[dict]:
    ensure(conn)
    sql = ("SELECT c.id, c.schedule_id, ms.module_code, c.session_date, c.action, c.new_date, "
           "c.new_start, c.new_end, c.reason, c.created_by, c.created_at "
           "FROM module_session_changes c JOIN module_schedule ms ON ms.id = c.schedule_id")
    params = []
    if module_code:
        sql += " WHERE ms.module_code = ?"
        params.append(module_code)
    return _dicts(conn.execute(sql + " ORDER BY c.session_date DESC", params))


# ── notices ─────────────────────────────────────────────────────────────


def recipients(conn, module_code, section_id=None) -> list[dict]:
    """Students currently enrolled (on the delivery, when one is given)."""
    ensure(conn)
    sql = ("SELECT sm.student_id, s.email_address AS email FROM student_modules sm "
           "LEFT JOIN students s ON s.student_id = sm.student_id WHERE sm.module_code = ? "
           "AND LOWER(COALESCE(sm.status, '')) = 'enrolled'")
    params = [module_code]
    if section_id:
        sql += " AND sm.section_id = ?"
        params.append(section_id)
    return _dicts(conn.execute(sql, params))


def notify(conn, module_code, subject, body, *, section_id=None, instructor_id=None) -> list:
    """Put a notice in each recipient's Hub inbox; return ``(email, subject,
    body)`` for :func:`send_emails` to send once the change is committed."""
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    emails = []
    for r in recipients(conn, module_code, section_id):
        deliver_inbox_message_on(conn, r["student_id"], subject, body)
        if r["email"] and "@" in r["email"]:
            emails.append((r["email"], subject, body))
    if instructor_id:
        row = conn.execute("SELECT email FROM instructors WHERE id = ?", (instructor_id,)).fetchone()
        if row and row[0]:
            user = conn.execute("SELECT username FROM users WHERE LOWER(email) = LOWER(?)",
                                (row[0],)).fetchone()
            if user:
                deliver_inbox_message_on(conn, user[0], subject, body)
            emails.append((row[0], subject, body))
    return emails


def send_emails(emails) -> int:
    """Best-effort email delivery. Returns how many were sent."""
    try:
        from education_system.systems.university.infrastructure.email import send_email
    except Exception:
        return 0
    sent = 0
    for address, subject, body in emails:
        try:
            send_email(recipient_email=address, subject=subject, body=body)
            sent += 1
        except Exception:
            continue
    return sent


# ── calendar export ─────────────────────────────────────────────────────


def export_window(conn, today=None):
    """``(start, end)`` for a calendar export: today to the end of the last
    term (or 26 weeks when no term reaches further)."""
    today = today or date.today()
    ends = [end for _name, _start, end in terms(conn) if end and end >= today]
    return today, max(ends) if ends else today + timedelta(weeks=26)


def _ics_text(value):
    return str(value or "").replace("\\", "\\\\").replace(",", "\\,").replace(
        ";", "\\;").replace("\n", "\\n")


def ical(occurrence_list, name="Timetable") -> str:
    """An iCalendar file of real dated sessions (cancelled ones left out)."""
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//University//Timetable//EN",
             f"X-WR-CALNAME:{_ics_text(name)}"]
    for o in occurrence_list:
        if o["status"] == "cancelled":
            continue
        day = o["date"].replace("-", "")
        note = f"Moved from {o['moved_from']}. " if o["status"] == "moved" else ""
        lines += ["BEGIN:VEVENT", f"UID:slot{o['id']}-{o.get('moved_from', o['date'])}@timetable",
                  f"DTSTAMP:{stamp}",
                  f"DTSTART:{day}T{o['start_time'].replace(':', '')[:4]}00",
                  f"DTEND:{day}T{o['end_time'].replace(':', '')[:4]}00",
                  f"SUMMARY:{_ics_text(o['module_code'] + ' ' + o['session_type'])}",
                  f"LOCATION:{_ics_text(o.get('room') or ('Online' if o.get('online_url') else ''))}",
                  f"DESCRIPTION:{_ics_text(note + (o.get('module_name') or ''))}"]
        if o.get("online_url"):
            lines.append(f"URL:{o['online_url']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
