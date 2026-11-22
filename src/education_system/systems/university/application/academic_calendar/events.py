"""What each person sees in the calendar, their personal calendar feed,
event reminders, and repairing events that have no start date.

* **Visibility**: an event is shown when its audience suits the person
  (all / public, students, staff), or it names them as a participant, or
  they organised it. Private events — like the security-training
  invitations, one per invitee — reach only the people they name.
  Published key dates are shown by audience.
* **Feeds**: a person makes a private feed link (a random token, stored as
  SHA-256) to subscribe from Outlook or Google: published key dates, the
  events they can see, and their own timetable.
* **Reminders**: chosen per event; :func:`send_due` delivers the due ones
  (inbox + e-mail).

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import date, datetime, timedelta

from education_system.systems.university.application.academic_calendar import access as ca
from education_system.systems.university.application.academic_calendar import year as cy

FEED_DAYS_BACK, FEED_DAYS_AHEAD = 30, 400


def _hash(token) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _start(row) -> str | None:
    value = row.get("start_datetime") or row.get("event_date")
    if not value:
        return None
    value = str(value)
    if len(value) == 10 and row.get("start_time"):
        value = f"{value}T{row['start_time']}"
    return value


def _names_person(row, who) -> bool:
    if row.get("organizer_id") in (who.username,) or str(row.get("created_by") or "") == \
            who.username:
        return True
    raw = row.get("participants")
    if not raw:
        return False
    try:
        people = json.loads(raw)
    except (TypeError, ValueError):
        return who.username in str(raw)
    ids = {who.username, who.student_id}
    for p in people if isinstance(people, list) else [people]:
        if isinstance(p, dict) and ({str(p.get("username")), str(p.get("user_id")),
                                     str(p.get("student_id"))} & {str(i) for i in ids if i}):
            return True
        if isinstance(p, str) and p in ids:
            return True
    return False


def can_see(row, who) -> bool:
    audience = str(row.get("audience") or "").strip().lower()
    if audience == "private":
        return _names_person(row, who)
    return audience in who.audiences or _names_person(row, who)


def visible_events(conn, who, start, end) -> list[dict]:
    """Events between ``start`` and ``end`` (dates) that ``who`` may see,
    plus published key dates, sorted by start."""
    ca.ensure(conn)
    start = ca.iso_date(start, "From", True)
    end = ca.iso_date(end, "To", True)
    out = []
    if ca.has_table(conn, "unified_events"):
        rows = ca.dicts(conn.execute(
            "SELECT * FROM unified_events WHERE COALESCE(is_active, 1) = 1 AND LOWER(COALESCE("
            "status, '')) NOT IN ('cancelled', 'deleted') AND COALESCE(start_datetime, "
            "event_date) BETWEEN ? AND ?", (start, end + "T23:59:59")))
        for r in rows:
            if can_see(r, who):
                out.append({"id": r.get("source_event_id") or r.get("event_id"),
                            "title": r.get("title") or r.get("event_name"), "start": _start(r),
                            "end": r.get("end_datetime"), "kind": r.get("event_type"),
                            "location": r.get("location"), "source": "event"})
    audience = "students" if who.is_student else ("staff" if not who.is_admin else None)
    for y in ca.dicts(conn.execute("SELECT year_code FROM calendar_years WHERE status = "
                                   "'published' AND start_date <= ? AND end_date >= ?",
                                   (end, start))):
        for d in cy.key_dates(conn, y["year_code"], audience):
            if start <= d["start_date"] <= end or (d["end_date"] and d["start_date"] <= end and
                                                    d["end_date"] >= start):
                out.append({"id": f"key{d['key_date_id']}", "title": d["title"],
                            "start": d["start_date"], "end": d["end_date"],
                            "kind": cy.KINDS.get(d["kind"], d["kind"]), "location": None,
                            "source": "key date"})
    return sorted(out, key=lambda e: e["start"] or "")


# ── personal feeds ──────────────────────────────────────────────────────


def feed_url(token) -> str:
    base = os.environ.get("UNIVERSITY_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    return f"{base}/api/v1/university/calendar/feed/{token}.ics"


def create_feed(conn, who) -> dict:
    """A new private feed link (any older one stops working)."""
    ca.ensure(conn)
    ca.require(who is not None, "Sign in first")
    conn.execute("UPDATE calendar_feed_tokens SET revoked_at = ? WHERE username = ? AND "
                 "revoked_at IS NULL", (ca.now(), who.username))
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO calendar_feed_tokens (token_hash, username, role, student_id) "
                 "VALUES (?, ?, ?, ?)", (_hash(token), who.username, who.role, who.student_id))
    ca.audit(conn, who, "feed", who.username, "created")
    return {"token": token, "url": feed_url(token)}


def revoke_feed(conn, who) -> int:
    ca.ensure(conn)
    return conn.execute("UPDATE calendar_feed_tokens SET revoked_at = ? WHERE username = ? AND "
                        "revoked_at IS NULL", (ca.now(), who.username)).rowcount


def _ics(value) -> str:
    return str(value or "").replace("\\", "\\\\").replace(",", "\\,").replace(
        ";", "\\;").replace("\n", "\\n")


def _ics_when(value) -> str:
    value = str(value or "")
    if len(value) <= 10:
        return f";VALUE=DATE:{value.replace('-', '')}"
    return ":" + value[:16].replace("-", "").replace(":", "").replace(" ", "T") + "00"


def _timetable(conn, who, start, end) -> list[dict]:
    try:
        from education_system.systems.university.application.teaching import occurrences as tt
        if who.is_student and who.student_id:
            return tt.for_student(conn, who.student_id, start, end)
        row = conn.execute("SELECT id FROM instructors WHERE staff_id = ?",
                           (who.username,)).fetchone() if ca.has_table(conn, "instructors") \
            else None
        return tt.for_instructor(conn, row[0], start, end) if row else []
    except Exception:
        return []


def feed_ics(conn, token) -> str | None:
    """The iCalendar text behind a feed link, or None if the link is dead."""
    ca.ensure(conn)
    row = ca.one(conn, "SELECT * FROM calendar_feed_tokens WHERE token_hash = ? AND revoked_at "
                       "IS NULL", (_hash(token),))
    if not row:
        return None
    who = ca.user(conn, row["username"], row["role"], row["student_id"])
    conn.execute("UPDATE calendar_feed_tokens SET last_used_at = ? WHERE token_hash = ?",
                 (ca.now(), row["token_hash"]))
    start = date.today() - timedelta(days=FEED_DAYS_BACK)
    end = date.today() + timedelta(days=FEED_DAYS_AHEAD)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//University//Academic calendar//EN",
             "X-WR-CALNAME:University calendar"]
    for e in visible_events(conn, who, start.isoformat(), end.isoformat()):
        if not e["start"]:
            continue
        lines += ["BEGIN:VEVENT", f"UID:{_ics(e['id'])}@calendar", f"DTSTAMP:{stamp}",
                  f"DTSTART{_ics_when(e['start'])}", f"SUMMARY:{_ics(e['title'])}"]
        if e.get("end"):
            lines.append(f"DTEND{_ics_when(e['end'])}")
        if e.get("location"):
            lines.append(f"LOCATION:{_ics(e['location'])}")
        lines += [f"CATEGORIES:{_ics(e.get('kind') or '')}", "END:VEVENT"]
    for o in _timetable(conn, who, start, end):
        if o.get("status") == "cancelled":
            continue
        day = o["date"].replace("-", "")
        lines += ["BEGIN:VEVENT", f"UID:slot{o['id']}-{o['date']}@timetable", f"DTSTAMP:{stamp}",
                  f"DTSTART:{day}T{o['start_time'].replace(':', '')[:4]}00",
                  f"DTEND:{day}T{o['end_time'].replace(':', '')[:4]}00",
                  f"SUMMARY:{_ics(o['module_code'] + ' ' + (o.get('session_type') or ''))}",
                  f"LOCATION:{_ics(o.get('room') or '')}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ── reminders ───────────────────────────────────────────────────────────


def _event(conn, event_id) -> dict | None:
    return ca.one(conn, "SELECT * FROM unified_events WHERE source_event_id = ? OR "
                        "CAST(event_id AS TEXT) = ?", (str(event_id), str(event_id)))


def add_reminder(conn, who, event_id, minutes_before=60) -> int:
    ca.ensure(conn)
    ca.require(who is not None, "Sign in first")
    row = _event(conn, event_id)
    if not row or not can_see(row, who):
        raise ValueError("No such event")
    begins = _start(row)
    if not begins:
        raise ValueError("That event has no start date")
    when = datetime.fromisoformat(begins if len(begins) > 10 else begins + "T09:00")
    remind_at = when - timedelta(minutes=int(minutes_before))
    if remind_at <= datetime.now():
        raise ValueError("That reminder time has already passed")
    rid = conn.execute("INSERT OR IGNORE INTO calendar_reminders (username, event_id, remind_at) "
                       "VALUES (?, ?, ?)", (who.username, str(event_id),
                                            remind_at.isoformat(timespec="minutes"))).lastrowid
    return int(rid or 0)


def my_reminders(conn, who) -> list[dict]:
    ca.ensure(conn)
    return ca.dicts(conn.execute("SELECT * FROM calendar_reminders WHERE username = ? AND "
                                 "sent_at IS NULL ORDER BY remind_at", (who.username,)))


def cancel_reminder(conn, who, reminder_id) -> None:
    if not conn.execute("DELETE FROM calendar_reminders WHERE reminder_id = ? AND username = ? "
                        "AND sent_at IS NULL", (reminder_id, who.username)).rowcount:
        raise ValueError("No such reminder")


def send_due(conn, as_of=None) -> dict:
    """Deliver every reminder that is due. Returns ``{"sent", "emails"}``."""
    ca.ensure(conn)
    when = (as_of or datetime.now()).isoformat(timespec="minutes") if not isinstance(
        as_of, str) else as_of
    emails, sent = [], 0
    for r in ca.dicts(conn.execute("SELECT * FROM calendar_reminders WHERE sent_at IS NULL AND "
                                   "remind_at <= ?", (when,))):
        event = _event(conn, r["event_id"])
        if event:
            emails += ca.notify(conn, [r["username"]], f"Reminder: {event.get('title')}",
                                f"{event.get('title')} starts {_start(event)}"
                                + (f" at {event['location']}" if event.get("location") else ""))
        conn.execute("UPDATE calendar_reminders SET sent_at = ? WHERE reminder_id = ?",
                     (ca.now(), r["reminder_id"]))
        sent += 1
    return {"sent": sent, "emails": emails}


# ── events without a start date ─────────────────────────────────────────


def undated_events(conn) -> list[dict]:
    ca.ensure(conn)
    return ca.dicts(conn.execute(
        "SELECT event_id, source_event_id, title, event_date, start_time, created_by, "
        "created_at FROM unified_events WHERE start_datetime IS NULL OR start_datetime = ''"))


def repair_undated(conn, who, delete_undateable=False) -> dict:
    """Give undated events the start their ``event_date`` implies; those
    with no date at all are deleted only when asked."""
    ca.require_admin(who)
    fixed = removed = 0
    for r in undated_events(conn):
        if r["event_date"]:
            start = str(r["event_date"])[:10] + (f"T{r['start_time']}" if r.get("start_time")
                                                  else "")
            conn.execute("UPDATE unified_events SET start_datetime = ? WHERE event_id = ?",
                         (start, r["event_id"]))
            fixed += 1
        elif delete_undateable:
            conn.execute("DELETE FROM unified_events WHERE event_id = ?", (r["event_id"],))
            removed += 1
    ca.audit(conn, who, "events", "undated", "repaired", {"fixed": fixed, "removed": removed})
    return {"fixed": fixed, "removed": removed}
