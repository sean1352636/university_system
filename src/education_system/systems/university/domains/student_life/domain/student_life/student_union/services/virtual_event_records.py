"""Virtual and hybrid Student Union events, stored in ``unified_events``.

The Virtual Events screens used to "create" events that were never saved,
generate random Zoom links and list made-up attendees. Calendar and SU
events already live in ``unified_events`` (``source_type = 'union'``),
which has a ``virtual_link`` column, so nothing new is added:

* a virtual event is a ``union`` row with ``event_category = 'virtual'``
  and its meeting link in ``virtual_link``; a hybrid one has
  ``event_category = 'hybrid'``, the venue in ``location`` and the link;
* platform, features and the in-person/online split go in ``notes`` (JSON);
* attendance is read from ``unified_event_registrations`` — only the
  check-in/out times that were actually recorded are shown.

The calendar mirror is the same call the CLI's create flow makes.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

PLATFORMS = ("Zoom", "Microsoft Teams", "Google Meet", "WebEx", "Custom Platform")

# Where a host creates a meeting on each platform. The app has no API
# credentials for these services, so it cannot mint a real meeting itself.
SCHEDULE_PAGES = {
    "Zoom": "https://zoom.us/meeting/schedule",
    "Microsoft Teams": "https://teams.microsoft.com/",
    "Teams": "https://teams.microsoft.com/",
    "Google Meet": "https://meet.google.com/new",
    "WebEx": "https://signin.webex.com/",
}

UNION_SOURCES = ("union", "student_union")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dicts(cur) -> list[dict[str, Any]]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _cols(conn, table: str) -> set[str]:
    # db-audit: ignore[DBW001] - fixed table names only
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _parse(value: str | None, label: str, required: bool = False) -> datetime | None:
    text = (value or "").strip().replace("T", " ")
    if not text:
        if required:
            raise ValueError(f"{label} is required (YYYY-MM-DD HH:MM).")
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"{label} must be YYYY-MM-DD HH:MM.")


def _int(value, label: str) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        n = int(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a whole number.") from exc
    if n < 0:
        raise ValueError(f"{label} cannot be negative.")
    return n


def create_event(conn, *, title: str, start: str, end: str = "", description: str = "",
                 platform: str = "", meeting_link: str = "", virtual_capacity=None,
                 mode: str = "virtual", venue: str = "", in_person_capacity=None,
                 features: list[str] | None = None, organizer_id: str | None = None) -> int:
    """Insert a virtual/hybrid SU event; returns its ``event_id``."""
    title = (title or "").strip()
    if not title:
        raise ValueError("Please enter an event name.")
    if mode not in ("virtual", "hybrid"):
        raise ValueError("Mode must be virtual or hybrid.")
    start_dt = _parse(start, "Date & time", required=True)
    end_dt = _parse(end, "End")
    if end_dt and end_dt <= start_dt:
        raise ValueError("The end must be after the start.")
    link = (meeting_link or "").strip()
    if link and not link.lower().startswith(("http://", "https://")):
        raise ValueError("The meeting link must start with https://.")
    venue = (venue or "").strip()
    if mode == "hybrid" and not venue:
        raise ValueError("A hybrid event needs an in-person venue.")
    v_cap = _int(virtual_capacity, "Virtual capacity")
    p_cap = _int(in_person_capacity, "In-person capacity")
    total = None if v_cap is None and p_cap is None else (v_cap or 0) + (p_cap or 0)
    notes = {"platform": platform or None, "features": list(features or []),
             "virtual_capacity": v_cap, "in_person_capacity": p_cap, "mode": mode}

    cols = _cols(conn, "unified_events")
    values: dict[str, Any] = {
        "source_type": "union", "title": title,
        "description": (description or "").strip() or None,
        "event_type": f"{mode}_event", "event_category": mode,
        "start_datetime": start_dt.strftime("%Y-%m-%d %H:%M"),
        "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M") if end_dt else None,
        "event_date": start_dt.strftime("%Y-%m-%d"),
        "start_time": start_dt.strftime("%H:%M"),
        "end_time": end_dt.strftime("%H:%M") if end_dt else None,
        "location": venue if mode == "hybrid" else (platform or "Online"),
        "virtual_link": link or None, "max_capacity": total,
        "organizer_id": organizer_id, "created_by": organizer_id,
        "status": "upcoming", "is_public": 1, "created_at": _now(),
        "notes": json.dumps(notes),
    }
    values = {k: v for k, v in values.items() if k in cols}
    names = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    # db-audit: ignore[DBW001] - column names filtered against PRAGMA
    cur = conn.execute(f"INSERT INTO unified_events ({names}) VALUES ({marks})",
                       tuple(values.values()))
    event_id = int(cur.lastrowid)
    conn.commit()

    try:
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import (
            mirror,
        )
        mirror(name=f"SU {'Hybrid' if mode == 'hybrid' else 'Virtual'} Event: {title}",
               kind="virtual_event", date=values.get("event_date"),
               start_time=values.get("start_time"), end_time=values.get("end_time"),
               location=values.get("location"), description=values.get("description"),
               created_by=organizer_id, source_table="union_events", source_id=event_id,
               conn=conn)
    except Exception:  # calendar is best-effort; the event is already saved
        pass
    return event_id


def list_events(conn, *, include_past: bool = True) -> list[dict[str, Any]]:
    """Union events that are online: a meeting link, or category virtual/hybrid."""
    cols = _cols(conn, "unified_events")
    start = ("COALESCE(e.start_datetime, e.event_date || ' ' || COALESCE(e.start_time, ''))"
             if "event_date" in cols else "e.start_datetime")
    sql = (f"SELECT e.event_id, e.title, e.organizer_id, e.event_category, e.location, e.virtual_link, "
           f"e.max_capacity, e.status, e.notes, {start} AS starts, "
           f"(SELECT COUNT(*) FROM unified_event_registrations r WHERE r.event_id = e.event_id) AS registered "
           f"FROM unified_events e WHERE e.source_type IN (?, ?) "
           f"AND (COALESCE(e.virtual_link, '') != '' OR LOWER(COALESCE(e.event_category, '')) "
           f"IN ('virtual', 'hybrid'))")
    params: list[Any] = list(UNION_SOURCES)
    if not include_past:
        sql += f" AND COALESCE({start}, '9999') >= ?"
        params.append(datetime.now().strftime("%Y-%m-%d"))
    sql += " ORDER BY starts DESC"
    rows = _dicts(conn.execute(sql, params))
    for r in rows:
        try:
            r["meta"] = json.loads(r.get("notes") or "{}")
            if not isinstance(r["meta"], dict):
                r["meta"] = {}
        except (TypeError, ValueError):
            r["meta"] = {}
    return rows


def set_meeting_link(conn, event_id: int, link: str) -> None:
    link = (link or "").strip()
    if link and not link.lower().startswith(("http://", "https://")):
        raise ValueError("The meeting link must start with https://.")
    sets = "virtual_link = ?"
    if "updated_at" in _cols(conn, "unified_events"):
        sets += ", updated_at = '" + _now() + "'"
    # db-audit: ignore[DBW001] - fixed column names, timestamp generated here
    conn.execute(f"UPDATE unified_events SET {sets} WHERE event_id = ?",
                 (link or None, event_id))
    conn.commit()


def attendance(conn, event_id: int) -> list[dict[str, Any]]:
    """Registrations for an event, with names and recorded join/leave times."""
    cols = _cols(conn, "unified_event_registrations")
    name_expr = "r.attendee_name" if "attendee_name" in cols else "NULL"
    rows = _dicts(conn.execute(
        f"SELECT r.registration_id, r.user_id, {name_expr} AS attendee_name, r.registration_date, "
        f"r.attendance_status, r.checked_in_at, r.check_out_time "
        f"FROM unified_event_registrations r WHERE r.event_id = ? ORDER BY r.registration_date",
        (event_id,)))
    for r in rows:
        r["name"] = r.get("attendee_name") or _name_for(conn, r.get("user_id"))
        r["duration"] = _duration(r.get("checked_in_at"), r.get("check_out_time"))
    return rows


def _name_for(conn, user_id) -> str:
    if user_id in (None, ""):
        return "Unknown"
    uid = str(user_id)
    queries = []
    if uid.startswith("user:"):
        queries.append(("SELECT first_name, last_name, username FROM users WHERE username = ?", uid[5:]))
    else:
        queries.append(("SELECT first_name, last_name, student_id FROM students WHERE student_id = ?", uid))
        if uid.isdigit():
            queries.append(("SELECT first_name, last_name, username FROM users WHERE id = ?", int(uid)))
    for sql, param in queries:
        try:
            row = conn.execute(sql, (param,)).fetchone()
        except Exception:
            continue
        if row:
            return " ".join(p for p in (row[0], row[1]) if p) or str(row[2])
    return uid


def _duration(start, end) -> str:
    if not start or not end:
        return "—"
    def p(v):
        v = str(v).replace("T", " ")
        for text, fmt in ((v[:19], "%Y-%m-%d %H:%M:%S"), (v[:16], "%Y-%m-%d %H:%M")):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None
    a, b = p(start), p(end)
    if not a or not b or b < a:
        return "—"
    m = int((b - a).total_seconds() // 60)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


__all__ = ["PLATFORMS", "SCHEDULE_PAGES", "attendance", "create_event", "list_events",
           "set_meeting_link"]
