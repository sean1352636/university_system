"""Tasks, calendar events, workloads and search results.

These are read models: nothing here is stored. The services assemble
them from every part of the system — a review that is overdue, hours
waiting for approval, an assessment booked next week — so that one
screen can answer "what needs me?" and another "what is happening
when?" without either knowing where each item came from.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from education_system.systems.apprenticeships import config

URGENCIES: tuple[str, ...] = ("Overdue", "Due soon", "Upcoming", "No date")


# ═════════════════════════════════════════════════════════════════════
# Tasks
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Task:
    """Something waiting on the person looking at the list."""

    category: str
    title: str
    detail: str = ""
    due: str | None = None
    apprentice_id: int | None = None
    apprentice_name: str | None = None
    # Where to go to deal with it: (window module, navigation label).
    # None when the actor's role has no screen for it.
    opens: tuple[str, str] | None = None

    def urgency(self, today: date) -> str:
        due = _parse_date(self.due)
        if due is None:
            return "No date"
        if due < today:
            return "Overdue"
        if due <= today + timedelta(days=config.TASK_DUE_SOON_DAYS):
            return "Due soon"
        return "Upcoming"

    def rag(self, today: date) -> str | None:
        return {"Overdue": "Red", "Due soon": "Amber"}.get(self.urgency(today))


def sort_tasks(tasks: Iterable[Task], today: date) -> list[Task]:
    """Most urgent first; within a band, soonest due first."""
    return sorted(
        tasks,
        key=lambda t: (URGENCIES.index(t.urgency(today)), t.due or "9999-12-31",
                       t.category, t.title),
    )


def count_by_urgency(tasks: Iterable[Task], today: date) -> dict[str, int]:
    counts = dict.fromkeys(URGENCIES, 0)
    for task in tasks:
        counts[task.urgency(today)] += 1
    return counts


# ═════════════════════════════════════════════════════════════════════
# Calendar
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CalendarEvent:
    """One dated thing: a review, a session, an assessment, a deadline."""

    day: str
    title: str
    kind: str
    time: str | None = None
    detail: str = ""
    apprentice_id: int | None = None
    opens: tuple[str, str] | None = None
    # Stable across exports, so re-importing a calendar file updates the
    # events already there rather than duplicating them.
    uid: str = ""

    @property
    def weekday(self) -> str:
        day = _parse_date(self.day)
        return day.strftime("%a %d %b %Y") if day else self.day


def within(events: Iterable[CalendarEvent], start: date, end: date) -> list[CalendarEvent]:
    """Events from *start* to *end* inclusive, in the order they happen."""
    kept = [
        e for e in events
        if (day := _parse_date(e.day)) is not None and start <= day <= end
    ]
    return sorted(kept, key=lambda e: (e.day, e.time or "", e.kind, e.title))


def group_by_day(events: Sequence[CalendarEvent]) -> list[tuple[str, list[CalendarEvent]]]:
    """Consecutive events sharing a day, for an agenda view."""
    groups: list[tuple[str, list[CalendarEvent]]] = []
    for event in events:
        if groups and groups[-1][0] == event.day:
            groups[-1][1].append(event)
        else:
            groups.append((event.day, [event]))
    return groups


def to_ics(events: Iterable[CalendarEvent], *, name: str, stamp: datetime) -> str:
    """An iCalendar (RFC 5545) file any calendar application can import.

    Untimed events are all-day; timed ones are "floating" local times,
    which is what a provider's diary means by 10:00.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Education System//Apprenticeships//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape(name)}",
    ]
    for event in events:
        day = _parse_date(event.day)
        if day is None:
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event.uid or _fallback_uid(event)}@apprenticeships",
            f"DTSTAMP:{stamp:%Y%m%dT%H%M%SZ}",
        ]
        starts = _parse_time(event.time)
        if starts is not None:
            lines.append(f"DTSTART:{day:%Y%m%d}T{starts:%H%M}00")
        else:
            lines += [
                f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
                f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            ]
        lines.append(f"SUMMARY:{_escape(event.title)}")
        if event.detail:
            lines.append(f"DESCRIPTION:{_escape(event.detail)}")
        lines.append(f"CATEGORIES:{_escape(event.kind)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Fold a content line at 75 octets, as RFC 5545 requires.

    A continuation line starts with a space, which counts towards its 75,
    and a multi-byte character is never split.
    """
    parts: list[str] = []
    current = ""
    for char in line:
        limit = 75 if not parts else 74
        if len((current + char).encode("utf-8")) > limit:
            parts.append(current)
            current = char
        else:
            current += char
    parts.append(current)
    return "\r\n ".join(parts)


def _fallback_uid(event: CalendarEvent) -> str:
    digest = hashlib.sha1(f"{event.kind}|{event.day}|{event.title}".encode()).hexdigest()
    return digest[:16]


# ═════════════════════════════════════════════════════════════════════
# Workload and search
# ═════════════════════════════════════════════════════════════════════

@dataclass
class Workload:
    """What is on one member of staff's plate."""

    staff_id: int
    name: str
    staff_role: str | None = None
    active: int = 0
    reviews_overdue: int = 0
    reviews_due_soon: int = 0
    evidence_to_assess: int = 0
    hours_to_approve: int = 0
    attendance_concerns: int = 0
    objectives_overdue: int = 0
    # Counts from features that report into the workload, by label.
    other: dict[str, int] = field(default_factory=dict)

    @property
    def open_items(self) -> int:
        return (
            self.reviews_overdue + self.reviews_due_soon + self.evidence_to_assess
            + self.hours_to_approve + self.attendance_concerns + self.objectives_overdue
            + sum(self.other.values())
        )

    @property
    def rag(self) -> str:
        if (self.active >= config.CASELOAD_MAXIMUM
                or self.open_items >= config.WORKLOAD_ITEMS_MAXIMUM):
            return "Red"
        if (self.active >= config.CASELOAD_WARNING_THRESHOLD
                or self.open_items >= config.WORKLOAD_ITEMS_WARNING):
            return "Amber"
        return "Green"


@dataclass(frozen=True)
class SearchResult:
    """One thing that matched a search, and where to look at it."""

    kind: str
    title: str
    subtitle: str = ""
    apprentice_id: int | None = None
    opens: tuple[str, str] | None = None


def matches(text: str, *fields: object) -> bool:
    """Does *text* appear in any of *fields*, ignoring case?"""
    needle = text.casefold()
    return any(needle in str(value).casefold() for value in fields if value)


def _parse_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def _parse_time(text: str | None) -> time | None:
    if not text:
        return None
    try:
        return time.fromisoformat(text.strip()[:5])
    except ValueError:
        return None
