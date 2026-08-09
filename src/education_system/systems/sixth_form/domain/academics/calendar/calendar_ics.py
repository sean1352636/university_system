"""ICS (RFC 5545) export and import for the Sixth Form Calendar.

Sibling to :mod:`calendar`. The single most-asked-for thing a school
calendar can do: appear in the phone people already look at. Nothing
in the whole repository has ever emitted a VCALENDAR.

Handwritten on purpose. The subset of RFC 5545 a college needs —
VEVENT with dates, times, summary, location, description, status,
UID — is a page of code, and a dependency is a decade of upgrades.
The emitter folds long lines at 75 octets and escapes the four magic
characters; the parser unfolds, unescapes, and takes only what it
stores.

Three surfaces:

* :func:`export_events` — a one-off ``.ics`` string for any filtered
  set of events ("this term's trips as a file").
* :func:`feed` — the standing per-audience subscription text an API
  route serves; staff add the URL to Outlook once and never ask for
  the file again. Visibility is enforced here, not at the route.
* :func:`import_ics` — the other direction: an exam board's
  published timetable lands as events instead of an afternoon of
  retyping. Idempotent by UID — re-importing the same file updates
  rather than duplicates.

Times are written as *floating* local times (no TZID, no UTC ``Z``).
The college and its calendar clients are in the same place; naming a
timezone here would mean shipping tzdata for one label.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_governance as governance,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CALENDAR_DB

ValidationError = core.ValidationError

PRODID: str = "-//Sixth Form College//Calendar//EN"
_UID_DOMAIN: str = "calendar.sixthform"

# Where an imported UID is remembered, so the same file twice is an
# update, not a duplicate.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_ics_imports (
    uid         TEXT PRIMARY KEY,
    event_id    INTEGER NOT NULL,
    imported_at TEXT DEFAULT (datetime('now'))
);
"""

_STATUS_MAP: dict[str, str] = {
    "Scheduled": "CONFIRMED",
    "Completed": "CONFIRMED",
    "Draft": "TENTATIVE",
    "Postponed": "TENTATIVE",
    "Cancelled": "CANCELLED",
}


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        tail = f", {len(self.errors)} error(s)" if self.errors else ""
        return (f"{self.created} created, {self.updated} updated, "
                f"{self.skipped} skipped{tail}")


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True


# ── Emitting ────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _unescape(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append({"n": "\n", "N": "\n"}.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _fold(line: str) -> list[str]:
    """RFC 5545 3.1: lines over 75 octets continue on the next line
    after one space. Folding is done on characters, which is close
    enough below the multi-byte pathological cases."""
    if len(line) <= 75:
        return [line]
    out = [line[:75]]
    rest = line[75:]
    while rest:
        out.append(" " + rest[:74])
        rest = rest[74:]
    return out


def _date_value(date_iso: str) -> str:
    return date_iso.replace("-", "")


def _datetime_value(date_iso: str, time_iso: str) -> str:
    return f"{_date_value(date_iso)}T{time_iso.replace(':', '')[:6]}"


def event_uid(event: core.Event) -> str:
    return f"event-{event.event_id}@{_UID_DOMAIN}"


def _vevent_lines(event: core.Event, *, now_stamp: str) -> list[str]:
    lines = ["BEGIN:VEVENT",
             f"UID:{event_uid(event)}",
             f"DTSTAMP:{now_stamp}",
             f"SUMMARY:{_escape(event.title)}"]
    if event.all_day or not event.start_time:
        # All-day: DATE values, DTEND exclusive per the RFC.
        end_next = (_dt.date.fromisoformat(event.end_date)
                    + _dt.timedelta(days=1)).isoformat()
        lines.append(
            f"DTSTART;VALUE=DATE:{_date_value(event.start_date)}")
        lines.append(f"DTEND;VALUE=DATE:{_date_value(end_next)}")
    else:
        start = event.start_time
        end_date = event.end_date
        end = event.end_time
        if not end:
            # An open-ended timed event gets an hour — a zero-length
            # event renders invisibly in most clients.
            t = _dt.datetime.fromisoformat(
                f"{event.start_date}T{start}")
            t += _dt.timedelta(hours=1)
            end_date = t.date().isoformat()
            end = t.time().isoformat()
        lines.append(
            f"DTSTART:{_datetime_value(event.start_date, start)}")
        lines.append(f"DTEND:{_datetime_value(end_date, end)}")
    if event.location:
        lines.append(f"LOCATION:{_escape(event.location)}")
    desc_bits = [b for b in (event.description,
                             f"Organiser: {event.organiser}"
                             if event.organiser else None) if b]
    if desc_bits:
        lines.append(f"DESCRIPTION:{_escape(chr(10).join(desc_bits))}")
    lines.append(f"STATUS:{_STATUS_MAP.get(event.status, 'CONFIRMED')}")
    lines.append(f"CATEGORIES:{_escape(event.event_type)}")
    lines.append("END:VEVENT")
    return lines


def export_events(events: list[core.Event], *,
                  name: str = "Sixth Form Calendar") -> str:
    """The given events as one VCALENDAR string, CRLF line endings
    and all."""
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape(name)}",
    ]
    for event in events:
        lines.extend(_vevent_lines(event, now_stamp=stamp))
    lines.append("END:VCALENDAR")
    folded: list[str] = []
    for line in lines:
        folded.extend(_fold(line))
    return "\r\n".join(folded) + "\r\n"


def export_filtered(**filters: Any) -> str:
    """:func:`calendar.list_events` filters in, ``.ics`` text out."""
    return export_events(core.list_events(**filters))


def feed(*, viewer: str = "public",
         audience: str | None = None,
         days_back: int = 30, days_ahead: int = 365) -> str:
    """The standing subscription: what this viewer may see, a month
    back and a year forward. The API serves this per audience."""
    today = _dt.date.today()
    date_from = (today - _dt.timedelta(days=days_back)).isoformat()
    date_to = (today + _dt.timedelta(days=days_ahead)).isoformat()
    rows = governance.visible_events(viewer, date_from=date_from,
                                     date_to=date_to)
    if audience:
        if audience not in core.AUDIENCES:
            raise ValidationError(
                f"Audience must be one of: {', '.join(core.AUDIENCES)}")
        rows = [e for e in rows if e.audience in (audience, "All")]
    name = ("Sixth Form Calendar" if not audience
            else f"Sixth Form Calendar — {audience}")
    return export_events(rows, name=name)


# ── Parsing ─────────────────────────────────────────────────────────

def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return [ln for ln in lines if ln]


def _parse_prop(line: str) -> tuple[str, dict[str, str], str]:
    """``DTSTART;VALUE=DATE:20260907`` → (name, params, value)."""
    head, _, value = line.partition(":")
    bits = head.split(";")
    name = bits[0].upper()
    params: dict[str, str] = {}
    for p in bits[1:]:
        k, _, v = p.partition("=")
        params[k.upper()] = v
    return name, params, value


def _parse_dt(value: str, params: dict[str, str]) -> tuple[str, str | None]:
    """An ICS date or date-time → (date_iso, time_iso | None).

    A trailing ``Z`` (UTC) is accepted and its clock time kept as-is
    — for school-day events the date is what matters, and guessing
    an offset would move exams across midnight.
    """
    v = value.strip().rstrip("Zz")
    if params.get("VALUE") == "DATE" or ("T" not in v and len(v) == 8):
        d = f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
        return d, None
    date_part, _, time_part = v.partition("T")
    d = f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
    t = f"{time_part[0:2]}:{time_part[2:4]}"
    return d, t


def parse_ics(text: str) -> list[dict[str, Any]]:
    """VEVENTs → payload dicts ready for :func:`calendar.create_event`,
    each carrying its ``uid`` (or None)."""
    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in _unfold(text):
        name, params, value = _parse_prop(line)
        if name == "BEGIN" and value.upper() == "VEVENT":
            current = {"uid": None}
            continue
        if name == "END" and value.upper() == "VEVENT":
            if current is not None and current.get("title") \
                    and current.get("start_date"):
                out.append(current)
            current = None
            continue
        if current is None:
            continue
        if name == "UID":
            current["uid"] = value.strip() or None
        elif name == "SUMMARY":
            current["title"] = _unescape(value).strip()
        elif name == "LOCATION":
            current["location"] = _unescape(value).strip() or None
        elif name == "DESCRIPTION":
            current["description"] = _unescape(value).strip() or None
        elif name == "DTSTART":
            d, t = _parse_dt(value, params)
            current["start_date"] = d
            current["start_time"] = t
            current["all_day"] = t is None
        elif name == "DTEND":
            d, t = _parse_dt(value, params)
            if t is None:
                # DATE-valued DTEND is exclusive; ours is inclusive.
                d = (_dt.date.fromisoformat(d)
                     - _dt.timedelta(days=1)).isoformat()
            current["end_date"] = d
            current["end_time"] = t
        elif name == "STATUS":
            s = value.strip().upper()
            current["status"] = {"CANCELLED": "Cancelled",
                                 "TENTATIVE": "Draft"}.get(
                s, "Scheduled")
        elif name == "CATEGORIES":
            cat = _unescape(value).split(",")[0].strip()
            if cat in core.EVENT_TYPES:
                current["event_type"] = cat
    return out


# ── Import ──────────────────────────────────────────────────────────

def _uid_event(uid: str) -> int | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT event_id FROM calendar_ics_imports WHERE uid = ?",
            (uid,)).fetchone()
    return r["event_id"] if r else None


def import_ics(text: str, *,
               default_event_type: str = "Other",
               audience: str = core.DEFAULT_AUDIENCE,
               actor: str | None = None) -> ImportResult:
    """Bring a file's VEVENTs in. Known UIDs update their event;
    unknown ones create, and remember the UID for next time. A
    malformed VEVENT is an error line, not a lost import."""
    init_db()
    if default_event_type not in core.EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of: "
            f"{', '.join(core.EVENT_TYPES)}")
    if audience not in core.AUDIENCES:
        raise ValidationError(
            f"Audience must be one of: {', '.join(core.AUDIENCES)}")
    result = ImportResult()
    for parsed in parse_ics(text):
        uid = parsed.pop("uid", None)
        payload = dict(parsed)
        payload.setdefault("event_type", default_event_type)
        payload.setdefault("audience", audience)
        try:
            existing_id = _uid_event(uid) if uid else None
            if existing_id is not None:
                if core.get_event(existing_id) is None:
                    # The event was purged since; recreate under the
                    # same UID.
                    event = core.create_event(payload, actor=actor)
                    with _connect() as conn:
                        conn.execute(
                            "UPDATE calendar_ics_imports "
                            "SET event_id = ?, "
                            "imported_at = datetime('now') "
                            "WHERE uid = ?", (event.event_id, uid))
                        conn.commit()
                    result.created += 1
                else:
                    core.update_event(existing_id, payload,
                                      actor=actor)
                    result.updated += 1
            else:
                event = core.create_event(payload, actor=actor)
                if uid:
                    with _connect() as conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO "
                            "calendar_ics_imports (uid, event_id) "
                            "VALUES (?, ?)", (uid, event.event_id))
                        conn.commit()
                result.created += 1
        except ValidationError as e:
            result.errors.append(
                f"{parsed.get('title', '(untitled)')}: {e}")
    logger.info("ICS import: %s", result.summary)
    return result
