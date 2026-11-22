"""Student Union recurring event series, stored the way the database has them.

A series is one ``recurring_events`` row plus a parent ``unified_events`` row
titled ``"<name> (Series)"``. The individual sessions are ordinary
``unified_events`` rows titled ``"<name> #<n>"``. ``recurring_events`` is shared
with the academic calendar, which links its rows through ``base_event_id`` ->
``unified_events.source_event_id``; union series fill that link as well as
``parent_event_id`` so the foreign key holds and the two sets stay separate
(calendar rows have no ``parent_event_id``).

Functions take an open cursor and do not commit; the caller does.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta

from education_system.systems.university.infrastructure.sql_safety import escape_like

SERIES_SUFFIX = " (Series)"

# The dialogs' pattern names -> (frequency, interval).
PATTERNS = {
    "daily": ("daily", 1),
    "weekly": ("weekly", 1),
    "biweekly": ("weekly", 2),
    "monthly": ("monthly", 1),
}


def pattern_parts(pattern: str) -> tuple[str, int]:
    """``(frequency, interval)`` for a pattern name; ValueError if unknown."""
    try:
        return PATTERNS[(pattern or "").strip().lower()]
    except KeyError:
        raise ValueError(f"Unknown recurrence pattern: {pattern}") from None


def pattern_name(frequency: str | None, interval: int | None) -> str:
    """The pattern name for stored frequency/interval values."""
    if frequency == "weekly" and (interval or 1) == 2:
        return "biweekly"
    return frequency or ""


def _parse_date(value: str, label: str) -> date:
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{label} must be in YYYY-MM-DD format.") from None


def end_time_for(start_time: str, hours: float) -> str:
    """``HH:MM`` end of a session; ValueError on a bad time or duration."""
    if hours <= 0:
        raise ValueError("Duration must be greater than zero.")
    try:
        start = datetime.strptime((start_time or "").strip(), "%H:%M")
    except ValueError:
        raise ValueError("Event time must be in HH:MM format.") from None
    return (start + timedelta(hours=hours)).strftime("%H:%M")


def duration_hours(start_time: str | None, end_time: str | None) -> float:
    """Hours between two ``HH:MM`` times (1 when either is unusable)."""
    try:
        start = datetime.strptime(start_time or "", "%H:%M")
        end = datetime.strptime(end_time or "", "%H:%M")
    except ValueError:
        return 1.0
    minutes = (end - start).total_seconds() / 60
    if minutes <= 0:
        minutes += 24 * 60
    return round(minutes / 60, 2)


def nth_date(first: date, frequency: str, interval: int, n: int) -> date:
    """The ``n``-th session date (0-based) counted from ``first``."""
    if frequency == "daily":
        return first + timedelta(days=interval * n)
    if frequency == "weekly":
        return first + timedelta(weeks=interval * n)
    if frequency == "monthly":
        months = first.month - 1 + interval * n
        year, month = first.year + months // 12, months % 12 + 1
        return first.replace(year=year, month=month,
                             day=min(first.day, calendar.monthrange(year, month)[1]))
    raise ValueError(f"Unknown recurrence frequency: {frequency}")


def create_series(cursor, *, name, frequency, interval=1, start_date, end_date,
                  start_time=None, end_time=None, description=None, location=None,
                  organizer_id=None, category=None, max_capacity=None, event_fee=None,
                  days_of_week="", day_of_month=None, max_occurrences=0,
                  created_by=None) -> tuple[str, int]:
    """Insert the parent event and series row; ``(series id, parent event id)``."""
    first, last = _parse_date(start_date, "Start date"), _parse_date(end_date, "End date")
    if last < first:
        raise ValueError("End date cannot be before the start date.")
    if int(interval) < 1:
        raise ValueError("Recurrence interval must be at least 1.")
    nth_date(first, frequency, int(interval), 0)  # rejects an unknown frequency

    base_event_id = str(uuid.uuid4())
    day = first.isoformat()
    cursor.execute(
        "INSERT INTO unified_events (source_type, source_event_id, title, description, "
        "event_date, start_time, end_time, start_datetime, end_datetime, location, "
        "organizer_id, club_id, event_category, max_capacity, event_fee, status, "
        "created_by, recurrence) "
        "VALUES ('union', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?, ?)",
        (base_event_id, f"{name}{SERIES_SUFFIX}", description, day, start_time, end_time,
         f"{day} {start_time}" if start_time else day,
         f"{day} {end_time}" if end_time else None,
         location, organizer_id, organizer_id, category, max_capacity, event_fee or 0,
         created_by, frequency))
    parent_event_id = cursor.lastrowid

    series_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO recurring_events (id, base_event_id, frequency, interval_count, "
        "days_of_week, day_of_month, end_date, date_added, max_occurrences, parent_event_id, "
        "recurrence_interval, recurrence_type, status, current_occurrences) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0)",
        (series_id, base_event_id, frequency, int(interval), days_of_week or "", day_of_month,
         last.isoformat(), datetime.now().isoformat(), max_occurrences or 0, parent_event_id,
         int(interval), frequency))
    return series_id, parent_event_id


def generate_occurrences(cursor, series_id: str, from_date: date | None = None) -> int:
    """Create the series' sessions that fall on or after ``from_date``.

    Numbering carries on from ``current_occurrences``. Returns how many were made.
    """
    row = cursor.execute(
        "SELECT r.frequency, COALESCE(r.interval_count, 1), r.end_date, "
        "COALESCE(r.max_occurrences, 0), COALESCE(r.current_occurrences, 0), "
        "e.title, e.description, e.event_date, e.start_time, e.end_time, e.location, "
        "e.organizer_id, e.club_id, e.event_category, e.max_capacity, e.event_fee, e.created_by "
        "FROM recurring_events r JOIN unified_events e ON e.event_id = r.parent_event_id "
        "WHERE r.id = ?", (series_id,)).fetchone()
    if not row:
        raise ValueError("That recurring series no longer exists.")
    (frequency, interval, end_date, max_occurrences, number, title, description, first_date,
     start_time, end_time, location, organizer_id, club_id, category, capacity, fee,
     created_by) = tuple(row)
    first, last = _parse_date(first_date, "Start date"), _parse_date(end_date, "End date")
    base = _base_name(title)

    made, n = 0, 0
    while True:
        day = nth_date(first, frequency, interval, n)
        n += 1
        if day > last or (max_occurrences and number >= max_occurrences):
            break
        if from_date is not None and day < from_date:
            continue
        number += 1
        made += 1
        iso = day.isoformat()
        cursor.execute(
            "INSERT INTO unified_events (source_type, title, description, event_date, "
            "start_time, end_time, start_datetime, end_datetime, location, organizer_id, "
            "club_id, event_category, max_capacity, event_fee, status, created_by) "
            "VALUES ('union', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?)",
            (f"{base} #{number}", description, iso, start_time, end_time,
             f"{iso} {start_time}" if start_time else iso,
             f"{iso} {end_time}" if end_time else None,
             location, organizer_id, club_id, category, capacity, fee, created_by))
    cursor.execute("UPDATE recurring_events SET current_occurrences = ? WHERE id = ?",
                   (number, series_id))
    return made


def _base_name(title: str | None) -> str:
    title = title or ""
    return title[:-len(SERIES_SUFFIX)] if title.endswith(SERIES_SUFFIX) else title


_SERIES_SQL = (
    "SELECT r.id, e.title, r.frequency, COALESCE(r.interval_count, 1), e.event_date, "
    "r.end_date, r.status FROM recurring_events r "
    "JOIN unified_events e ON e.event_id = r.parent_event_id "
    "WHERE e.source_type = 'union' ORDER BY e.event_date DESC")


def list_series(cursor) -> list[tuple]:
    """``(id, name, pattern, start date, end date, status)`` for every union series."""
    return [(r[0], _base_name(r[1]), pattern_name(r[2], r[3]), r[4], r[5], r[6])
            for r in cursor.execute(_SERIES_SQL).fetchall()]


def get_series(cursor, series_id: str) -> tuple | None:
    """``(name, description, location, pattern, start, end, time, duration hours)``."""
    row = cursor.execute(
        "SELECT e.title, e.description, e.location, r.frequency, "
        "COALESCE(r.interval_count, 1), e.event_date, r.end_date, e.start_time, e.end_time "
        "FROM recurring_events r JOIN unified_events e ON e.event_id = r.parent_event_id "
        "WHERE r.id = ?", (series_id,)).fetchone()
    if not row:
        return None
    return (_base_name(row[0]), row[1], row[2], pattern_name(row[3], row[4]), row[5], row[6],
            row[7], duration_hours(row[7], row[8]))


def _session_filter(base: str) -> tuple[str, tuple]:
    """Where-clause matching a series' own sessions by their ``<name> #<n>`` title."""
    return ("source_type = 'union' AND title LIKE ? ESCAPE '\\'",
            (f"{escape_like(base.replace(chr(92), chr(92) * 2))} #%",))


def cancel_future_sessions(cursor, parent_event_id: int) -> int:
    """Cancel the sessions still to come. Past ones stay as the record of what ran."""
    row = cursor.execute(
        "SELECT title, COALESCE(organizer_id, '') FROM unified_events WHERE event_id = ?",
        (parent_event_id,)).fetchone()
    if not row:
        return 0
    where, params = _session_filter(_base_name(row[0]))
    # db-audit: ignore[DBW001] - _session_filter returns literal SQL and placeholders
    cursor.execute(
        f"UPDATE unified_events SET status = 'cancelled' WHERE {where} "
        "AND COALESCE(organizer_id, '') = ? AND event_date > date('now') "
        "AND status = 'upcoming'", params + (row[1],))
    return cursor.rowcount


def update_series(cursor, series_id: str, *, name, description, location, pattern,
                  start_date, end_date, start_time, hours) -> None:
    """Save an edited series. Details carry to the sessions still to come; a new
    pattern or date range replaces them."""
    row = cursor.execute(
        "SELECT r.parent_event_id, e.title, r.frequency, COALESCE(r.interval_count, 1), "
        "e.event_date, r.end_date, COALESCE(e.organizer_id, '') "
        "FROM recurring_events r JOIN unified_events e ON e.event_id = r.parent_event_id "
        "WHERE r.id = ?", (series_id,)).fetchone()
    if not row:
        raise ValueError("That recurring series no longer exists.")
    parent_event_id, old_title, old_freq, old_interval, old_start, old_end, organizer = tuple(row)

    frequency, interval = pattern_parts(pattern)
    first, last = _parse_date(start_date, "Start date"), _parse_date(end_date, "End date")
    if last < first:
        raise ValueError("End date cannot be before the start date.")
    end_time = end_time_for(start_time, hours)
    reschedule = ((frequency, interval, first.isoformat(), last.isoformat())
                  != (old_freq, old_interval, old_start, old_end))

    if reschedule:
        cancel_future_sessions(cursor, parent_event_id)
    else:
        where, params = _session_filter(_base_name(old_title))
        # db-audit: ignore[DBW001] - _session_filter returns literal SQL and placeholders
        cursor.execute(
            "UPDATE unified_events SET "
            "title = ? || substr(title, ?), description = ?, location = ?, start_time = ?, "
            "end_time = ?, start_datetime = event_date || ' ' || ?, "
            f"end_datetime = event_date || ' ' || ? WHERE {where} "
            "AND COALESCE(organizer_id, '') = ? AND event_date > date('now') "
            "AND status = 'upcoming'",
            (name, len(_base_name(old_title)) + 1, description, location, start_time,
             end_time, start_time, end_time) + params + (organizer,))

    cursor.execute(
        "UPDATE unified_events SET title = ?, description = ?, location = ?, event_date = ?, "
        "start_time = ?, end_time = ?, start_datetime = ?, end_datetime = ?, recurrence = ? "
        "WHERE event_id = ?",
        (f"{name}{SERIES_SUFFIX}", description, location, first.isoformat(), start_time,
         end_time, f"{first.isoformat()} {start_time}", f"{first.isoformat()} {end_time}",
         frequency, parent_event_id))
    cursor.execute(
        "UPDATE recurring_events SET frequency = ?, interval_count = ?, recurrence_type = ?, "
        "recurrence_interval = ?, end_date = ? WHERE id = ?",
        (frequency, interval, frequency, interval, last.isoformat(), series_id))
    if reschedule:
        generate_occurrences(cursor, series_id, from_date=date.today() + timedelta(days=1))


def delete_series(cursor, series_id: str) -> None:
    """Remove a series: future sessions and the parent entry are cancelled, past
    sessions (and anyone's registration on them) stay."""
    row = cursor.execute("SELECT parent_event_id FROM recurring_events WHERE id = ?",
                         (series_id,)).fetchone()
    if row and row[0] is not None:
        cancel_future_sessions(cursor, row[0])
        cursor.execute("UPDATE unified_events SET status = 'cancelled' WHERE event_id = ?",
                       (row[0],))
    cursor.execute("DELETE FROM recurring_events WHERE id = ?", (series_id,))
