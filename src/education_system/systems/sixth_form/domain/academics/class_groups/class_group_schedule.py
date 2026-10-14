"""Reading the free-text ``schedule`` field on a class group.

There are two schedules in this system and they are not the same thing.

``timetable_slots`` (in :mod:`...academics.timetable`) is the real one:
structured rows of ``(group_id, day, period, start_time, end_time,
room)``, with its own clash checking at write time. Anything that needs
to *know* when a group meets should read that.

``class_groups.schedule`` is a free-text column somebody types into the
group form. It has no format — the column is nullable, the live data has
none, and nothing validates it. It exists because staff want a
human-readable "Mon & Wed, period 3" on the group card without building
a timetable first.

This module parses that text as well as it honestly can, so the two can
be compared (:func:`reconcile`) and so the validation pass can flag a
group whose typed schedule says one thing and whose timetable says
another. It is deliberately tolerant — a school types ``Mon 9-10``,
``Monday 09:00–09:55`` and ``Tue P3`` and means all three — and
deliberately loud about what it could not read: :func:`parse_report`
returns the fragments it gave up on rather than silently dropping them.

Never treat a parse failure as "no lessons". An unparseable schedule
means *unknown*, which is why :func:`parse_schedule` and
:func:`parse_report` are separate functions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, NamedTuple

from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_logging as cg_log,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as core,
)

logger = cg_log.get_logger(__name__)

ValidationError = core.ValidationError

#: Canonical day names and their timetable day numbers, matching
#: ``timetable.DAYS`` / ``timetable.DAY_NUMBERS``. Kept as a local map so
#: parsing does not drag the timetable module in on import.
DAY_NAMES: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri")
_DAY_FULL = {
    "monday": "Mon", "mon": "Mon", "mo": "Mon", "m": "Mon",
    "tuesday": "Tue", "tues": "Tue", "tue": "Tue", "tu": "Tue",
    "wednesday": "Wed", "weds": "Wed", "wed": "Wed", "we": "Wed",
    "thursday": "Thu", "thurs": "Thu", "thur": "Thu", "thu": "Thu",
    "th": "Thu",
    "friday": "Fri", "fri": "Fri", "fr": "Fri", "f": "Fri",
}
DAY_NUMBER = {name: i + 1 for i, name in enumerate(DAY_NAMES)}

#: Fallback period times, mirroring ``timetable.DEFAULT_PERIOD_TIMES``.
#: Used when a schedule names a period rather than a clock time.
PERIOD_TIMES: dict[int, tuple[str, str]] = {
    1: ("09:00", "09:55"),
    2: ("09:55", "10:50"),
    3: ("11:10", "12:05"),
    4: ("12:05", "13:00"),
    5: ("14:00", "14:55"),
    6: ("14:55", "15:50"),
}

# Entries are separated by commas, semicolons, newlines, or the word
# 'and'. Days *within* one entry by '/', '&', '+' — "Mon/Wed 9-10".
_ENTRY_SPLIT = re.compile(r"[,;\n]+|\band\b", re.IGNORECASE)
_DAY_SPLIT = re.compile(r"[/&+]")
# En dash and em dash are what a word processor produces; 'to' is what a
# person types.
_RANGE_SPLIT = re.compile(r"\s*(?:-|–|—|\bto\b)\s*", re.IGNORECASE)
_PERIOD_RE = re.compile(r"\b(?:p|period)\s*([1-9])\b", re.IGNORECASE)
_BARE_PERIOD_RE = re.compile(r"^([1-9])$")
_TIME_RE = re.compile(
    r"^(\d{1,2})(?::?(\d{2}))?\s*(am|pm)?$", re.IGNORECASE)


class ScheduleWindow(NamedTuple):
    """One day plus a start and end time, as ``(day, start, end)``.

    Exactly three fields so it unpacks the way callers expect::

        for day, start, end in parse_schedule(group.schedule):
            ...

    Times are 24-hour ``HH:MM``. Days are the canonical short names in
    :data:`DAY_NAMES`.
    """
    day: str
    start: str
    end: str

    @property
    def day_number(self) -> int:
        """1-5, matching ``timetable_slots.day``."""
        return DAY_NUMBER[self.day]

    @property
    def start_minutes(self) -> int:
        h, m = self.start.split(":")
        return int(h) * 60 + int(m)

    @property
    def end_minutes(self) -> int:
        h, m = self.end.split(":")
        return int(h) * 60 + int(m)

    def overlaps(self, other: "ScheduleWindow") -> bool:
        """Whether two windows collide.

        Touching windows do not overlap — a lesson ending at 09:55 and
        one starting at 09:55 are back-to-back, not a clash, which is
        exactly how the default period times are laid out.
        """
        if self.day != other.day:
            return False
        return (self.start_minutes < other.end_minutes
                and other.start_minutes < self.end_minutes)

    def __str__(self) -> str:
        return f"{self.day} {self.start}-{self.end}"


@dataclass
class ParseReport:
    """Everything :func:`parse_schedule` found, including what it didn't."""
    raw: str
    windows: list[ScheduleWindow] = field(default_factory=list)
    #: Fragments the parser could not turn into a window, verbatim.
    unparsed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.windows) and not self.unparsed

    @property
    def is_empty(self) -> bool:
        return not self.windows and not self.unparsed

    def __str__(self) -> str:
        if self.is_empty:
            return "(no schedule)"
        parts = [", ".join(str(w) for w in self.windows)] if self.windows else []
        if self.unparsed:
            parts.append(f"unreadable: {'; '.join(self.unparsed)}")
        return " | ".join(parts)


def _normalise_time(token: str) -> str | None:
    """'9' / '9:30' / '0930' / '2pm' -> 'HH:MM', or None if it isn't one."""
    t = token.strip().lower().replace(".", ":")
    m = _TIME_RE.match(t)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = m.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    # A bare '0930' arrives as hour=930 with no minute group; treat any
    # 3-4 digit run without a separator as HHMM.
    if minute == 0 and m.group(2) is None and len(t.rstrip("apm ")) in (3, 4) \
            and t.rstrip("apm ").isdigit():
        digits = t.rstrip("apm ")
        hour, minute = int(digits[:-2]), int(digits[-2:])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _days_in(fragment: str) -> tuple[list[str], str]:
    """Pull day names off the front of a fragment.

    Returns the days found and whatever text is left, so the caller can
    look for a time range in the remainder.
    """
    days: list[str] = []
    remainder = fragment
    # Longest names first, so 'Thursday' is not eaten by 'Thu'.
    tokens = sorted(_DAY_FULL, key=len, reverse=True)
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in tokens) + r")\b",
        re.IGNORECASE)
    # Only treat a run of day names joined by / & + as a single group.
    for chunk in _DAY_SPLIT.split(fragment):
        for m in pattern.finditer(chunk):
            canonical = _DAY_FULL[m.group(1).lower()]
            if canonical not in days:
                days.append(canonical)
    if days:
        remainder = pattern.sub(" ", fragment)
        remainder = _DAY_SPLIT.sub(" ", remainder)
    return days, remainder.strip()


def _window_times(remainder: str) -> tuple[str, str] | None:
    """Turn the non-day part of a fragment into a (start, end) pair."""
    text = remainder.strip()
    if not text:
        return None

    period = _PERIOD_RE.search(text)
    if period:
        p = int(period.group(1))
        return PERIOD_TIMES.get(p)

    parts = [p for p in _RANGE_SPLIT.split(text) if p.strip()]
    if len(parts) >= 2:
        start = _normalise_time(parts[0])
        end = _normalise_time(parts[1])
        if start and end:
            return (start, end)
        return None
    if len(parts) == 1:
        token = parts[0].strip()
        bare = _BARE_PERIOD_RE.match(token)
        if bare:
            # A lone single digit next to a day means a period, not 3am.
            return PERIOD_TIMES.get(int(bare.group(1)))
        start = _normalise_time(token)
        if start:
            # A start with no end: assume a standard 55-minute lesson
            # rather than dropping the entry.
            h, m = (int(x) for x in start.split(":"))
            total = h * 60 + m + 55
            return (start, f"{total // 60 % 24:02d}:{total % 60:02d}")
    return None


# ── 33. Parse a schedule string ─────────────────────────────────────

def parse_report(schedule: str | None) -> ParseReport:
    """Parse a schedule string, reporting fragments that failed.

    Use this wherever a failure matters (validation, reconciliation).
    Use :func:`parse_schedule` when you only want the windows.
    """
    raw = (schedule or "").strip()
    report = ParseReport(raw=raw)
    if not raw:
        return report

    for fragment in _ENTRY_SPLIT.split(raw):
        frag = fragment.strip()
        if not frag:
            continue
        days, remainder = _days_in(frag)
        if not days:
            report.unparsed.append(frag)
            continue
        times = _window_times(remainder)
        if times is None:
            report.unparsed.append(frag)
            continue
        start, end = times
        for day in days:
            window = ScheduleWindow(day=day, start=start, end=end)
            if window not in report.windows:
                report.windows.append(window)

    report.windows.sort(key=lambda w: (w.day_number, w.start_minutes))
    return report


def parse_schedule(schedule: str | None) -> list[ScheduleWindow]:
    """Feature 33 — ``(day, start, end)`` windows from a schedule string.

    Returns an empty list for a blank *or* entirely unreadable schedule.
    Those two are different situations: call :func:`parse_report` if the
    difference matters to you.
    """
    report = parse_report(schedule)
    if report.unparsed:
        cg_log.group_event(
            logger, "Could not parse %d schedule fragment(s) in %r: %s",
            len(report.unparsed), report.raw, "; ".join(report.unparsed),
            level=10,
        )
    return report.windows


def format_schedule(windows: Iterable[ScheduleWindow]) -> str:
    """Render windows back to a canonical string.

    Round-trips through :func:`parse_schedule`, so it is safe to use to
    tidy a hand-typed field.
    """
    ordered = sorted(set(windows), key=lambda w: (w.day_number, w.start_minutes))
    return ", ".join(str(w) for w in ordered)


# ── The structured timetable, as windows ────────────────────────────

def slot_windows(group_id: int) -> list[ScheduleWindow]:
    """The group's real timetable rows, as comparable windows.

    Slots with no explicit times fall back to the standard period times,
    which is what the timetable module itself displays.
    """
    from education_system.systems.sixth_form.domain.academics.timetable \
        import timetable as _tt

    _tt.init_db()
    out: list[ScheduleWindow] = []
    for slot in _tt.list_slots(group_id=int(group_id)):
        start, end = slot.start_time, slot.end_time
        if not start or not end:
            fallback = PERIOD_TIMES.get(slot.period)
            if fallback is None:
                continue
            start, end = fallback
        if 1 <= slot.day <= len(DAY_NAMES):
            out.append(ScheduleWindow(
                day=DAY_NAMES[slot.day - 1], start=start, end=end))
    out.sort(key=lambda w: (w.day_number, w.start_minutes))
    return out


def reconcile(group_id: int) -> dict[str, Any]:
    """Compare a group's typed ``schedule`` against its timetable slots.

    The two drift constantly — somebody edits the timetable and forgets
    the group card, or the reverse — and nothing else in the system
    notices. Returns what each source says and where they disagree.

    A group with a typed schedule and no slots is not an error here; it
    is a group whose timetable has not been built yet. The validation
    pass decides how loudly to say so.
    """
    group = core.get_group(int(group_id))
    if group is None:
        raise ValidationError(f"No class group with id {group_id}")
    report = parse_report(group.schedule)
    slots = slot_windows(group.group_id)
    typed = set(report.windows)
    actual = set(slots)
    return {
        "group_id": group.group_id,
        "group_name": group.group_name,
        "raw_schedule": group.schedule,
        "typed_windows": report.windows,
        "unparsed": report.unparsed,
        "slot_windows": slots,
        "only_in_text": sorted(typed - actual,
                               key=lambda w: (w.day_number, w.start_minutes)),
        "only_in_timetable": sorted(actual - typed,
                                    key=lambda w: (w.day_number,
                                                   w.start_minutes)),
        "agrees": bool(typed) and typed == actual,
        "has_text": bool(report.raw),
        "has_slots": bool(slots),
    }
