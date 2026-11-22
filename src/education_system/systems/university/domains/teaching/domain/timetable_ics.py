"""Reusable iCalendar (.ics) export for weekly university timetables.

The scheduling data model stores sessions as a recurring *day-of-week +
time* (e.g. "Monday 09:00-10:00") rather than concrete dates, so each
session is emitted as a single ``VEVENT`` with an ``RRULE:FREQ=WEEKLY``
anchored to the current week's occurrence of that weekday. Importing the
file into Outlook / Google Calendar / Apple Calendar therefore produces a
repeating weekly class.

Shared by the student timetable (``student_timetable_gui``) and the staff
timetable manager so both export identical, standards-compliant files.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Weekday name -> Python weekday() index (Mon=0) and iCal BYDAY token.
_DAY_MAP = {
    "monday": (0, "MO"),
    "tuesday": (1, "TU"),
    "wednesday": (2, "WE"),
    "thursday": (3, "TH"),
    "friday": (4, "FR"),
    "saturday": (5, "SA"),
    "sunday": (6, "SU"),
}


def _escape(text: str) -> str:
    """Escape a value for an iCal TEXT field (RFC 5545 §3.3.11)."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _parse_hhmm(value: str) -> tuple[int, int]:
    """Parse 'HH:MM' (or 'HH:MM:SS') into (hour, minute). Tolerant of junk."""
    parts = str(value or "").strip().split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return (0, 0)
    return (max(0, min(23, hour)), max(0, min(59, minute)))


def _fold(line: str) -> str:
    """Fold a content line to 75 octets per RFC 5545 §3.1."""
    if len(line) <= 75:
        return line
    out = [line[:75]]
    rest = line[75:]
    while rest:
        out.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(out)


def build_weekly_timetable_ics(sessions, calendar_name="Timetable", *, now=None):
    """Build an iCalendar document string from weekly timetable *sessions*.

    Parameters
    ----------
    sessions : iterable of dict
        Each dict may contain: ``day`` (weekday name, required), ``start``
        and ``end`` ('HH:MM', required), ``summary`` (event title),
        ``location``, ``description``, ``uid``.
    calendar_name : str
        X-WR-CALNAME shown by calendar clients.
    now : datetime, optional
        Reference "today" (defaults to ``datetime.now()``); the recurrence
        is anchored to this week's occurrence of each weekday. Injectable
        for deterministic testing.

    Returns
    -------
    str
        A complete ``VCALENDAR`` document with CRLF line endings.
    """
    if now is None:
        now = datetime.now()
    week_monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    stamp = now.strftime("%Y%m%dT%H%M%S")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//University System//Timetable//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
    ]

    seq = 0
    for s in sessions:
        day_key = str(s.get("day", "")).strip().lower()
        if day_key not in _DAY_MAP:
            continue
        weekday_idx, byday = _DAY_MAP[day_key]
        sh, sm = _parse_hhmm(s.get("start"))
        eh, em = _parse_hhmm(s.get("end"))

        event_date = week_monday + timedelta(days=weekday_idx)
        dtstart = event_date.replace(hour=sh, minute=sm)
        dtend = event_date.replace(hour=eh, minute=em)
        # Guard against zero/negative-length or missing end times.
        if dtend <= dtstart:
            dtend = dtstart + timedelta(hours=1)

        seq += 1
        uid = s.get("uid") or f"tt-{seq}-{day_key}-{sh:02d}{sm:02d}@university.edu"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_escape(uid)}")
        lines.append(f"DTSTAMP:{stamp}")
        lines.append(f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"DTEND:{dtend.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"RRULE:FREQ=WEEKLY;BYDAY={byday}")
        lines.append(f"SUMMARY:{_escape(s.get('summary') or 'Class')}")
        if s.get("location"):
            lines.append(f"LOCATION:{_escape(s['location'])}")
        if s.get("description"):
            lines.append(f"DESCRIPTION:{_escape(s['description'])}")
        lines.append("STATUS:CONFIRMED")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def prompt_and_save_ics(parent, sessions, *, calendar_name="Timetable",
                        default_filename="timetable.ics"):
    """Show a save dialog and write the .ics for *sessions*.

    Returns the path written, or ``None`` if the user cancelled or there was
    nothing to export. Any error is surfaced via ``messagebox``.
    """
    from tkinter import filedialog, messagebox

    ics = build_weekly_timetable_ics(sessions, calendar_name)
    # No VEVENTs → nothing worth saving.
    if "BEGIN:VEVENT" not in ics:
        messagebox.showinfo(
            "Export Timetable",
            "There are no scheduled sessions to export.",
            parent=parent,
        )
        return None

    path = filedialog.asksaveasfilename(
        parent=parent,
        title="Export Timetable to Calendar",
        defaultextension=".ics",
        initialfile=default_filename,
        filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
    )
    if not path:
        return None

    try:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(ics)
    except OSError as exc:
        messagebox.showerror(
            "Export Timetable",
            f"Could not write calendar file:\n{exc}",
            parent=parent,
        )
        return None

    messagebox.showinfo(
        "Export Timetable",
        f"Timetable exported to:\n{path}\n\n"
        "Import this file into Outlook, Google Calendar, or Apple Calendar.",
        parent=parent,
    )
    return path
