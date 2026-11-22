"""The health clinic diary: one service behind every appointment screen.

Reads union the appointment tables the clinics keep —
``health_appointments``, ``dentist_appointments`` (student via
``dentist_patients.user_id``), ``counseling_appointments`` and
``mental_health_appointments`` — into one shape (:func:`appointments`).
They are still separate tables; merging them physically is wave 3. Until
then every GUI/CLI read and every booking check goes through here, so a
student cannot be double-booked across clinics and a provider cannot be
double-booked across screens.

Booking checks (:func:`check_booking`):

* **time off** (``provider_time_off``) blocks the booking outright;
* **clashes** — the provider or the student already has an appointment
  that overlaps — and **schedule** problems (outside the provider's hours in
  ``provider_schedules``, or the day already at ``max_appointments``) need
  an override with a reason (:func:`record_booking_override`, audited).

Also here: schedule templates (weekly patterns that write
``provider_schedules``), the waiting list (join when no slot; a cancelled
slot is offered to the first matching entry), post-appointment feedback
(real satisfaction figures), and the reminder run used by the hourly worker
(``infrastructure/health/reminder_worker``). Functions take an open
connection and never commit; e-mails are returned as
``(template, recipient, vars)`` for the caller to send after its commit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from education_system.systems.university.domains.health.application.health.workflow import (
    ensure_schema,
)

CLOSED = ("cancelled", "canceled", "no-show", "no_show", "rescheduled")
DEFAULT_MINUTES = 30
OFFER_HOURS = 24
TEMPLATE_DIR = "campus_services/health/"

# source table -> how to read it as a diary entry (column expressions).
SOURCES = {
    "health_appointments": {
        "id": "a.id", "student": "a.student_id", "date": "a.appointment_date",
        "time": "a.appointment_time", "provider": "a.provider", "type": "a.appointment_type",
        "status": "a.status", "duration": None, "from": "health_appointments a",
        "email": "(SELECT s.email_address FROM students s WHERE s.student_id = a.student_id)",
        "name": "(SELECT TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')) "
                "FROM students s WHERE s.student_id = a.student_id)",
    },
    "dentist_appointments": {
        "id": "a.appointment_id", "student": "p.user_id", "date": "a.appointment_date",
        "time": "a.appointment_time", "provider": "a.dentist_name", "type": "a.treatment_type",
        "status": "a.status", "duration": "a.duration_minutes",
        "from": "dentist_appointments a LEFT JOIN dentist_patients p ON p.patient_id = a.patient_id",
        "email": "p.user_email", "name": "p.user_name",
    },
    "counseling_appointments": {
        "id": "a.appointment_id", "student": "a.student_id", "date": "a.appointment_date",
        "time": "a.appointment_time", "provider": "a.counselor_name",
        "type": "a.appointment_type", "status": "a.status", "duration": None,
        "from": "counseling_appointments a",
        "email": "(SELECT s.email_address FROM students s WHERE s.student_id = a.student_id)",
        "name": "(SELECT TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')) "
                "FROM students s WHERE s.student_id = a.student_id)",
    },
    "mental_health_appointments": {
        "id": "a.appointment_id", "student": "a.student_id", "date": "a.appointment_date",
        "time": "a.appointment_time", "provider": "CAST(a.counselor_id AS TEXT)",
        "type": "a.appointment_type", "status": "a.status", "duration": "a.duration_minutes",
        "from": "mental_health_appointments a", "anonymous": "COALESCE(a.is_anonymous, 0)",
        "email": "(SELECT s.email_address FROM students s WHERE s.student_id = a.student_id)",
        "name": "(SELECT TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')) "
                "FROM students s WHERE s.student_id = a.student_id)",
    },
}


def _tables(conn) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def student_keys(conn, student_id) -> list[str]:
    """The ids a student appears under: student number, plus login id and
    username (the dental clinic keys patients on the login)."""
    keys = {str(student_id)}
    try:
        for uid, username in conn.execute("SELECT id, username FROM users WHERE student_id = ?",
                                          (str(student_id),)).fetchall():
            keys.update({str(uid), str(username)})
    except Exception:
        pass
    return sorted(keys)


def _minutes(hhmm) -> int | None:
    try:
        h, m = str(hhmm).strip()[:5].split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def appointments(conn, *, student_id=None, provider=None, date_from=None, date_to=None,
                 on_date=None, include_closed=True, sources=None) -> list[dict]:
    """Every clinic's appointments in one shape, sorted by date and time:
    ``{source, id, student_id, date, time, duration, provider, type, status,
    email, name, anonymous}``. An anonymous mental-health booking carries its
    student for clash checks only — screens must show it as anonymous."""
    present = _tables(conn)
    keys = student_keys(conn, student_id) if student_id else None
    out = []
    for source, m in SOURCES.items():
        if source not in present or (sources and source not in sources):
            continue
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{source}")')}
        duration = m["duration"] if m["duration"] and m["duration"].split(".")[1] in cols else None
        where, args = [], []
        if keys:
            where.append(f"CAST({m['student']} AS TEXT) IN ({','.join('?' * len(keys))})")
            args += keys
        if provider:
            where.append(f"LOWER(TRIM({m['provider']})) = LOWER(TRIM(?))")
            args.append(str(provider))
        if on_date:
            where.append(f"{m['date']} = ?")
            args.append(str(on_date))
        if date_from:
            where.append(f"{m['date']} >= ?")
            args.append(str(date_from))
        if date_to:
            where.append(f"{m['date']} <= ?")
            args.append(str(date_to))
        if not include_closed:
            where.append(f"LOWER(COALESCE({m['status']}, 'scheduled')) NOT IN "
                         f"({','.join('?' * len(CLOSED))})")
            args += list(CLOSED)
        sql = (f"SELECT {m['id']}, {m['student']}, {m['date']}, {m['time']}, "  # nosec B608
               f"{duration or DEFAULT_MINUTES}, {m['provider']}, {m['type']}, {m['status']}, "
               f"{m['email']}, {m['name']}, {m.get('anonymous', '0')} FROM {m['from']}"
               + (f" WHERE {' AND '.join(where)}" if where else ""))
        for row in conn.execute(sql, args).fetchall():
            out.append({"source": source, "id": row[0], "student_id": row[1], "date": row[2],
                        "time": row[3], "duration": int(row[4] or DEFAULT_MINUTES),
                        "provider": row[5], "type": row[6], "status": row[7] or "scheduled",
                        "email": row[8], "name": row[9] or row[1],
                        "anonymous": bool(row[10])})
    out.sort(key=lambda a: (str(a["date"] or ""), str(a["time"] or "")))
    return out


def _overlaps(a_start, a_len, b_start, b_len) -> bool:
    if a_start is None or b_start is None:
        return a_start == b_start
    return a_start < b_start + b_len and b_start < a_start + a_len


# ----------------------------------------------------------------- checks
@dataclass
class BookingCheck:
    blocked: list[str] = field(default_factory=list)      # time off: cannot book
    needs_override: list[str] = field(default_factory=list)   # clash / schedule

    @property
    def ok(self) -> bool:
        return not self.blocked and not self.needs_override

    def summary(self) -> str:
        return "\n".join([f"Blocked: {b}" for b in self.blocked]
                         + [f"Problem: {p}" for p in self.needs_override])


def find_clashes(conn, *, student_id, provider, date, time, duration=DEFAULT_MINUTES,
                 exclude=None) -> list[str]:
    """Overlapping open appointments for the provider or the student, across
    every clinic. ``exclude`` = ``(source, id)`` of the appointment being moved."""
    start = _minutes(time)
    found = []
    keys = set(student_keys(conn, student_id)) if student_id else set()
    for appt in appointments(conn, on_date=date, include_closed=False):
        if exclude and (appt["source"], str(appt["id"])) == (exclude[0], str(exclude[1])):
            continue
        if not _overlaps(start, duration, _minutes(appt["time"]), appt["duration"]):
            continue
        where = f"{appt['date']} {appt['time']} ({appt['source'].replace('_', ' ')} #{appt['id']})"
        if provider and str(appt["provider"] or "").strip().lower() == str(provider).strip().lower():
            found.append(f"{provider} is already booked at {where}")
        elif keys and str(appt["student_id"]) in keys:
            found.append(f"The student already has an appointment at {where}")
    return found


def time_off_for(conn, provider, date, time=None) -> list[dict]:
    if not provider:
        return []
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT id, start_date, end_date, start_time, end_time, reason FROM provider_time_off "
        "WHERE LOWER(TRIM(provider_name)) = LOWER(TRIM(?)) AND start_date <= ? AND end_date >= ?",
        (str(provider), str(date), str(date))).fetchall()
    out = []
    t = _minutes(time) if time else None
    for rid, s, e, st, et, reason in rows:
        if t is not None and st and et and (s == e == str(date)):
            if not (_minutes(st) <= t < _minutes(et)):
                continue
        out.append({"id": rid, "start_date": s, "end_date": e, "start_time": st,
                    "end_time": et, "reason": reason})
    return out


def day_of_week(date) -> int:
    """``provider_schedules.day_of_week`` for a date: 1 = Monday … 6 =
    Saturday, 0 = Sunday."""
    return (datetime.strptime(str(date), "%Y-%m-%d").weekday() + 1) % 7


def schedule_problems(conn, provider, date, time, duration=DEFAULT_MINUTES) -> list[str]:
    """Outside the provider's hours, or the day full. A provider with no
    schedule rows at all is not checked (nothing to enforce)."""
    if not provider:
        return []
    rows = conn.execute(
        "SELECT day_of_week, start_time, end_time, max_appointments FROM provider_schedules "
        "WHERE LOWER(TRIM(provider_name)) = LOWER(TRIM(?)) AND COALESCE(active, 1) = 1",
        (str(provider),)).fetchall()
    if not rows:
        return []
    dow = day_of_week(date)
    today = [r for r in rows if r[0] is not None and int(r[0]) == dow]
    if not today:
        return [f"{provider} has no clinic on that day"]
    start = _minutes(time)
    fits = [r for r in today if _minutes(r[1]) is not None and _minutes(r[2]) is not None
            and start is not None and _minutes(r[1]) <= start
            and start + duration <= _minutes(r[2])]
    if not fits:
        hours = ", ".join(f"{r[1]}-{r[2]}" for r in today)
        return [f"{time} is outside {provider}'s hours that day ({hours})"]
    capacity = max(int(r[3] or 0) for r in fits)
    booked = len(appointments(conn, provider=provider, on_date=date, include_closed=False))
    if capacity and booked >= capacity:
        return [f"{provider} is full that day ({booked} of {capacity} appointments)"]
    return []


def check_booking(conn, *, student_id, provider, date, time, duration=DEFAULT_MINUTES,
                  exclude=None) -> BookingCheck:
    check = BookingCheck()
    for off in time_off_for(conn, provider, date, time):
        span = off["start_date"] if off["start_date"] == off["end_date"] else \
            f"{off['start_date']} to {off['end_date']}"
        check.blocked.append(f"{provider} is away {span} ({off['reason'] or 'time off'})")
    check.needs_override += find_clashes(conn, student_id=student_id, provider=provider,
                                         date=date, time=time, duration=duration,
                                         exclude=exclude)
    check.needs_override += schedule_problems(conn, provider, date, time, duration)
    return check


def record_booking_override(conn, user, appointment_id, check: BookingCheck, reason: str,
                            source="health_appointments") -> None:
    """Audit a booking made despite clashes / schedule problems. Raises
    ``ValueError`` without a reason. Does not commit."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give a reason for booking over the clash")
    from education_system.systems.university.domains.health.domain.health.records.db.audit import (
        log_audit_event,
    )
    log_audit_event(user, "BOOKING_OVERRIDE", source, appointment_id,
                    {"problems": check.needs_override}, conn=conn, reason=reason)


def book(conn, *, student_id, appointment_type, date, time, provider, reason="",
         status="scheduled", department=None, has_conflict=False) -> int:
    """Insert a ``health_appointments`` row; returns its id. Run
    :func:`check_booking` first. Does not commit."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(health_appointments)")}
    values = {"student_id": str(student_id), "appointment_type": appointment_type,
              "appointment_date": str(date), "appointment_time": str(time),
              "provider": provider, "reason": reason, "status": status,
              "scheduled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    if "department" in cols and department is not None:
        values["department"] = department
    if "has_conflict" in cols:
        values["has_conflict"] = 1 if has_conflict else 0
    names = ", ".join(values)
    cur = conn.execute(f"INSERT INTO health_appointments ({names}) VALUES "  # nosec B608
                       f"({', '.join('?' * len(values))})", list(values.values()))
    return cur.lastrowid


def publish_booking(appointment_id, *, student_id, date, time, provider, appointment_type) -> None:
    """Tell the class-clash checker (after commit; never raises)."""
    try:
        from education_system.systems.university.services.bus.integration_bus import (
            publish_health_appointment,
        )
        publish_health_appointment(appointment_id=int(appointment_id), student_id=str(student_id),
                                   appointment_date=str(date), appointment_time=str(time),
                                   provider=provider, appointment_type=appointment_type)
    except Exception:
        import logging
        logging.getLogger(__name__).debug("health appointment not published", exc_info=True)


# --------------------------------------------------------------- time off
def add_time_off(conn, *, provider, start_date, end_date, by, reason="", start_time=None,
                 end_time=None) -> tuple[int, list[dict]]:
    """Record time off; returns ``(id, open appointments it now covers)`` so
    the caller can rebook them."""
    for d in (start_date, end_date):
        datetime.strptime(str(d), "%Y-%m-%d")
    if str(end_date) < str(start_date):
        raise ValueError("The end date is before the start date")
    ensure_schema(conn)
    cur = conn.execute(
        "INSERT INTO provider_time_off (provider_name, start_date, end_date, start_time, "
        "end_time, reason, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (provider.strip(), str(start_date), str(end_date), start_time or None, end_time or None,
         reason, by))
    affected = appointments(conn, provider=provider, date_from=start_date, date_to=end_date,
                            include_closed=False)
    return cur.lastrowid, affected


def list_time_off(conn, provider=None, *, upcoming_only=True) -> list[dict]:
    ensure_schema(conn)
    sql = ("SELECT id, provider_name, start_date, end_date, start_time, end_time, reason, "
           "created_by FROM provider_time_off WHERE 1=1")
    args = []
    if provider:
        sql += " AND LOWER(TRIM(provider_name)) = LOWER(TRIM(?))"
        args.append(provider)
    if upcoming_only:
        sql += " AND end_date >= date('now')"
    keys = ("id", "provider", "start_date", "end_date", "start_time", "end_time", "reason", "by")
    return [dict(zip(keys, r)) for r in conn.execute(sql + " ORDER BY start_date", args)]


def remove_time_off(conn, time_off_id) -> bool:
    ensure_schema(conn)
    return conn.execute("DELETE FROM provider_time_off WHERE id = ?",
                        (time_off_id,)).rowcount > 0


# -------------------------------------------------------------- templates
def list_templates(conn) -> list[dict]:
    ensure_schema(conn)
    return [{"id": r[0], "name": r[1], "pattern": json.loads(r[2]), "max_appointments": r[3],
             "specialty": r[4], "location": r[5]} for r in conn.execute(
        "SELECT id, name, pattern_json, max_appointments, specialty, location FROM "
        "provider_schedule_templates WHERE COALESCE(active, 1) = 1 ORDER BY id")]


def save_template(conn, *, name, pattern, max_appointments=8, specialty=None, location=None,
                  by=None, template_id=None) -> int:
    """Create (or, with ``template_id``, change) a weekly pattern:
    ``[{"day": 0-6, "start": "HH:MM", "end": "HH:MM"}, ...]``."""
    ensure_schema(conn)
    clean = []
    for slot in pattern:
        day = int(slot["day"])
        if not 0 <= day <= 6 or _minutes(slot["start"]) is None or _minutes(slot["end"]) is None \
                or _minutes(slot["end"]) <= _minutes(slot["start"]):
            raise ValueError(f"Bad slot {slot!r}")
        clean.append({"day": day, "start": slot["start"][:5], "end": slot["end"][:5]})
    if not clean:
        raise ValueError("A template needs at least one day")
    if template_id:
        conn.execute("UPDATE provider_schedule_templates SET name = ?, pattern_json = ?, "
                     "max_appointments = ?, specialty = ?, location = ? WHERE id = ?",
                     (name, json.dumps(clean), int(max_appointments), specialty, location,
                      template_id))
        return int(template_id)
    return conn.execute("INSERT INTO provider_schedule_templates (name, pattern_json, "
                        "max_appointments, specialty, location, created_by) VALUES "
                        "(?, ?, ?, ?, ?, ?)", (name, json.dumps(clean), int(max_appointments),
                                               specialty, location, by)).lastrowid


def apply_template(conn, template_id, provider) -> int:
    """Replace the provider's active weekly schedule with the template's
    pattern (old rows are deactivated, not deleted). Returns rows written."""
    ensure_schema(conn)
    row = conn.execute("SELECT pattern_json, max_appointments, specialty, location FROM "
                       "provider_schedule_templates WHERE id = ?", (template_id,)).fetchone()
    if row is None:
        raise LookupError(f"Template {template_id} not found")
    conn.execute("UPDATE provider_schedules SET active = 0 WHERE "
                 "LOWER(TRIM(provider_name)) = LOWER(TRIM(?))", (provider,))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    slots = json.loads(row[0])
    for slot in slots:
        conn.execute("INSERT INTO provider_schedules (provider_name, day_of_week, start_time, "
                     "end_time, max_appointments, specialty, location, active, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                     (provider.strip(), slot["day"], slot["start"], slot["end"], row[1],
                      row[2], row[3], now))
    return len(slots)


def free_slots(conn, provider, date, step=DEFAULT_MINUTES) -> list[str]:
    """Open start times for the provider on a date from their schedule,
    minus bookings and time off."""
    rows = conn.execute(
        "SELECT start_time, end_time FROM provider_schedules WHERE "
        "LOWER(TRIM(provider_name)) = LOWER(TRIM(?)) AND COALESCE(active, 1) = 1 AND "
        "day_of_week = ?", (provider, day_of_week(date))).fetchall()
    slots = []
    for start, end in rows:
        t, stop = _minutes(start), _minutes(end)
        while t is not None and stop is not None and t + step <= stop:
            hhmm = f"{t // 60:02d}:{t % 60:02d}"
            if check_booking(conn, student_id=None, provider=provider, date=date,
                             time=hhmm, duration=step).ok:
                slots.append(hhmm)
            t += step
    return slots


# --------------------------------------------------------------- waitlist
def join_waitlist(conn, *, student_id, appointment_type, by, provider=None, preferred_from=None,
                  preferred_to=None, notes=None) -> int:
    ensure_schema(conn)
    return conn.execute(
        "INSERT INTO appointment_waitlist (student_id, appointment_type, provider_name, "
        "preferred_from, preferred_to, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(student_id), appointment_type, provider or None, preferred_from or None,
         preferred_to or None, notes, by)).lastrowid


def list_waitlist(conn, status=None, student_id=None) -> list[dict]:
    ensure_schema(conn)
    sql = ("SELECT id, student_id, appointment_type, provider_name, preferred_from, "
           "preferred_to, status, offered_date, offered_time, offered_provider, "
           "offer_expires_at, created_at FROM appointment_waitlist WHERE 1=1")
    args = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if student_id:
        sql += " AND student_id = ?"
        args.append(str(student_id))
    keys = ("id", "student_id", "appointment_type", "provider", "preferred_from",
            "preferred_to", "status", "offered_date", "offered_time", "offered_provider",
            "offer_expires_at", "created_at")
    return [dict(zip(keys, r)) for r in conn.execute(sql + " ORDER BY created_at, id", args)]


def _student_contact(conn, student_id):
    row = conn.execute("SELECT TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')), "
                       "email_address FROM students WHERE student_id = ?",
                       (str(student_id),)).fetchone()
    return (row[0] or str(student_id), row[1]) if row else (str(student_id), None)


def offer_freed_slot(conn, *, date, time, provider, appointment_type=None) -> list[tuple]:
    """A slot came free (cancellation): offer it to the first waiting entry
    that fits (type, provider, date window). Returns the e-mails to send."""
    ensure_schema(conn)
    if str(date) < datetime.now().strftime("%Y-%m-%d"):
        return []
    for entry in list_waitlist(conn, status="waiting"):
        if appointment_type and entry["appointment_type"] and \
                entry["appointment_type"].lower() != str(appointment_type).lower():
            continue
        if entry["provider"] and provider and entry["provider"].lower() != str(provider).lower():
            continue
        if entry["preferred_from"] and str(date) < entry["preferred_from"]:
            continue
        if entry["preferred_to"] and str(date) > entry["preferred_to"]:
            continue
        if find_clashes(conn, student_id=entry["student_id"], provider=None, date=date, time=time):
            continue
        expires = (datetime.now() + timedelta(hours=OFFER_HOURS)).strftime("%Y-%m-%d %H:%M")
        conn.execute("UPDATE appointment_waitlist SET status = 'offered', offered_date = ?, "
                     "offered_time = ?, offered_provider = ?, offered_at = datetime('now'), "
                     "offer_expires_at = ? WHERE id = ?",
                     (str(date), str(time), provider, expires, entry["id"]))
        name, email = _student_contact(conn, entry["student_id"])
        if not email:
            return []
        return [(TEMPLATE_DIR + "waitlist_offer", email, {
            "patient_name": name, "appointment_type": entry["appointment_type"],
            "date": date, "time": time, "practitioner": provider or "the health team",
            "expires": expires})]
    return []


def accept_offer(conn, waitlist_id, *, by) -> int:
    """Book the offered slot for the waiting student; returns the appointment id."""
    ensure_schema(conn)
    row = conn.execute("SELECT student_id, appointment_type, offered_date, offered_time, "
                       "offered_provider, status, offer_expires_at FROM appointment_waitlist "
                       "WHERE id = ?", (waitlist_id,)).fetchone()
    if row is None or row[5] != "offered":
        raise ValueError("That waiting-list entry has no open offer")
    if row[6] and row[6] < datetime.now().strftime("%Y-%m-%d %H:%M"):
        raise ValueError("The offer has expired")
    check = check_booking(conn, student_id=row[0], provider=row[4], date=row[2], time=row[3])
    if not check.ok:
        raise ValueError("The slot is no longer free:\n" + check.summary())
    appt = book(conn, student_id=row[0], appointment_type=row[1], date=row[2], time=row[3],
                provider=row[4], reason=f"From the waiting list (accepted by {by})")
    conn.execute("UPDATE appointment_waitlist SET status = 'booked', booked_appointment_id = ? "
                 "WHERE id = ?", (appt, waitlist_id))
    return appt


def withdraw(conn, waitlist_id) -> bool:
    ensure_schema(conn)
    return conn.execute("UPDATE appointment_waitlist SET status = 'withdrawn' WHERE id = ? AND "
                        "status IN ('waiting', 'offered')", (waitlist_id,)).rowcount > 0


def expire_offers(conn) -> list[tuple]:
    """Lapsed offers are marked expired and their slots offered to the next
    person. Returns the e-mails to send."""
    ensure_schema(conn)
    emails = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for wid, date, time, provider, atype in conn.execute(
            "SELECT id, offered_date, offered_time, offered_provider, appointment_type FROM "
            "appointment_waitlist WHERE status = 'offered' AND offer_expires_at < ?",
            (now,)).fetchall():
        conn.execute("UPDATE appointment_waitlist SET status = 'expired' WHERE id = ?", (wid,))
        emails += offer_freed_slot(conn, date=date, time=time, provider=provider,
                                   appointment_type=atype)
    return emails


# --------------------------------------------------------------- feedback
def submit_feedback(conn, *, source, appointment_id, student_id, rating, comments=None) -> int:
    ensure_schema(conn)
    rating = int(rating)
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be 1-5")
    appt = [a for a in appointments(conn, student_id=student_id, sources=(source,))
            if str(a["id"]) == str(appointment_id)]
    if not appt:
        raise LookupError("That appointment is not this student's")
    if str(appt[0]["status"]).lower() != "completed":
        raise ValueError("Feedback is for completed appointments")
    return conn.execute(
        "INSERT INTO appointment_feedback (source_table, appointment_id, student_id, "
        "provider_name, rating, comments) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (source_table, appointment_id) DO UPDATE SET rating = excluded.rating, "
        "comments = excluded.comments, submitted_at = datetime('now')",
        (source, appointment_id, str(student_id), appt[0]["provider"], rating,
         comments)).lastrowid


def awaiting_feedback(conn, student_id) -> list[dict]:
    """The student's completed appointments (last 60 days) not yet rated."""
    ensure_schema(conn)
    since = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    rated = {(r[0], str(r[1])) for r in conn.execute(
        "SELECT source_table, appointment_id FROM appointment_feedback WHERE student_id = ?",
        (str(student_id),))}
    return [a for a in appointments(conn, student_id=student_id, date_from=since)
            if str(a["status"]).lower() == "completed" and (a["source"], str(a["id"])) not in rated]


def satisfaction(conn, provider=None, since=None) -> dict:
    """Real figures from ``appointment_feedback``: count, average, response
    rate (feedback / completed appointments), share rated 4-5."""
    ensure_schema(conn)
    sql = "SELECT rating FROM appointment_feedback WHERE 1=1"
    args = []
    if provider:
        sql += " AND LOWER(TRIM(provider_name)) = LOWER(TRIM(?))"
        args.append(provider)
    if since:
        sql += " AND submitted_at >= ?"
        args.append(since)
    ratings = [r[0] for r in conn.execute(sql, args)]
    completed = [a for a in appointments(conn, provider=provider, date_from=since)
                 if str(a["status"]).lower() == "completed"]
    return {"responses": len(ratings),
            "average": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "response_rate": round(100 * len(ratings) / len(completed), 1) if completed else None,
            "positive_pct": round(100 * sum(1 for r in ratings if r >= 4) / len(ratings), 1)
            if ratings else None}


# -------------------------------------------------------------- reminders
def _already(conn, source, appt_id, kind) -> bool:
    return conn.execute("SELECT 1 FROM appointment_reminders_sent WHERE source_table = ? AND "
                        "appointment_id = ? AND kind = ?", (source, appt_id, kind)).fetchone() \
        is not None


def _mark(conn, source, appt_id, kind) -> None:
    conn.execute("INSERT OR IGNORE INTO appointment_reminders_sent (source_table, "
                 "appointment_id, kind) VALUES (?, ?, ?)", (source, appt_id, kind))


def _appointment_reminders(conn, now) -> list[tuple]:
    emails = []
    upcoming = appointments(conn, date_from=now.strftime("%Y-%m-%d"),
                            date_to=(now + timedelta(days=1)).strftime("%Y-%m-%d"),
                            include_closed=False)
    for a in upcoming:
        if str(a["status"]).lower() == "completed" or not a["email"] or a["anonymous"]:
            continue
        try:
            at = datetime.strptime(f"{a['date']} {str(a['time'])[:5]}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        hours = (at - now).total_seconds() / 3600
        kind = "2h" if 0 < hours <= 2 else ("24h" if 2 < hours <= 24 else None)
        if not kind or _already(conn, a["source"], a["id"], kind) or \
                (kind == "24h" and _already(conn, a["source"], a["id"], "2h")):
            continue
        _mark(conn, a["source"], a["id"], kind)
        if a["source"] == "dentist_appointments":
            conn.execute("UPDATE dentist_appointments SET reminder_sent = 1 WHERE "
                         "appointment_id = ?", (a["id"],))
        when = ("in two hours" if kind == "2h" else
                "tomorrow" if at.date() > now.date() else "later today")
        emails.append((TEMPLATE_DIR + "appointment_reminder", a["email"], {
            "patient_name": a["name"], "appointment_type": a["type"] or "health",
            "when_label": when, "date": a["date"], "time": a["time"],
            "practitioner": a["provider"] or "the health team"}))
    return emails


def _feedback_requests(conn, now) -> list[tuple]:
    emails = []
    since = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    for a in appointments(conn, date_from=since, date_to=now.strftime("%Y-%m-%d")):
        if str(a["status"]).lower() != "completed" or not a["email"] or \
                a["source"] == "mental_health_appointments" or \
                _already(conn, a["source"], a["id"], "feedback"):
            continue
        _mark(conn, a["source"], a["id"], "feedback")
        emails.append((TEMPLATE_DIR + "appointment_feedback_request", a["email"], {
            "patient_name": a["name"], "appointment_type": a["type"] or "health",
            "date": a["date"], "practitioner": a["provider"] or "the health team"}))
    return emails


def _screening_reminders(conn, now) -> list[tuple]:
    if "screening_schedules" not in _tables(conn):
        return []
    emails = []
    horizon = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    for sid, student_id, first, last, stype, due, provider, email in conn.execute(
            "SELECT ss.id, ss.student_id, s.first_name, s.last_name, ss.screening_type, "
            "ss.due_date, ss.provider, s.email_address FROM screening_schedules ss "
            "JOIN students s ON ss.student_id = s.student_id "
            "WHERE ss.status = 'due' AND ss.due_date <= ?", (horizon,)).fetchall():
        kind = "screening_overdue" if due < today else "screening_due"
        if not email or _already(conn, "screening_schedules", sid, kind):
            continue
        _mark(conn, "screening_schedules", sid, kind)
        emails.append(("screening:" + kind, email, {
            "screening_id": sid, "student_id": student_id,
            "student_name": f"{first or ''} {last or ''}".strip() or student_id,
            "screening_type": stype, "due_date": due, "provider": provider,
            "email": email}))
    return emails


def due_reminders(conn, now=None) -> list[tuple]:
    """The reminder run (hourly): 24-hour and 2-hour reminders for every
    clinic's open appointments, a feedback request after a completed one,
    and screening reminders (due within 7 days / newly overdue). Each is
    sent once (``appointment_reminders_sent``). Returns e-mails to send
    after commit; marks them sent in ``conn``."""
    ensure_schema(conn)
    now = now or datetime.now()
    return (_appointment_reminders(conn, now) + _feedback_requests(conn, now)
            + _screening_reminders(conn, now))


def send_emails(emails) -> tuple[int, int]:
    """Send ``(template, recipient, vars)`` e-mails (after commit) through the
    university e-mail service (outbox). Screening entries go through the
    screening notifiers. Returns ``(sent, failed)``."""
    sent = failed = 0
    for template, recipient, variables in emails:
        try:
            if template.startswith("screening:"):
                from education_system.systems.university.domains.health.domain.health.records.screening import (
                    reminders,
                )
                if template.endswith("overdue"):
                    try:
                        variables["days_overdue"] = (datetime.now() - datetime.strptime(
                            variables["due_date"], "%Y-%m-%d")).days
                    except (ValueError, TypeError):
                        variables["days_overdue"] = 0
                    ok = reminders.notify_screening_overdue(variables)
                else:
                    ok = reminders.notify_screening_due(variables)
            else:
                from education_system.systems.university.infrastructure.email.email_service import (
                    send_template_email,
                )
                ok = send_template_email(template, recipient, variables)
        except Exception:
            ok = False
        if ok:
            sent += 1
        else:
            failed += 1
    return sent, failed
