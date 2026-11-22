"""Dataclasses for years, terms, breaks, events, periods, notes; dict converters.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import datetime as _dt

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    DEFAULT_BREAK_AM_PM,
    DEFAULT_CYCLE_WEEKS,
    DEFAULT_INSET_ALLOWANCE,
    DEFAULT_TERM_KIND,
    WEEKDAY_NAMES,
)


@dataclass
class AcademicYear:
    year_id: int
    name: str
    start_date: str
    end_date: str
    is_current: bool
    status: str
    notes: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    campus_id: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None
    cycle_weeks: int = DEFAULT_CYCLE_WEEKS
    cycle_anchor: str | None = None
    inset_allowance: int = DEFAULT_INSET_ALLOWANCE

    @property
    def effective_cycle_anchor(self) -> str:
        """The Monday Week A starts on. Falls back to the Monday of
        the week the year starts in."""
        if self.cycle_anchor:
            return self.cycle_anchor
        try:
            d = _dt.date.fromisoformat(self.start_date)
        except ValueError:
            return self.start_date
        return (d - _dt.timedelta(days=d.weekday())).isoformat()

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


@dataclass
class Term:
    term_id: int
    year_id: int
    name: str
    start_date: str
    end_date: str
    notes: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    kind: str = DEFAULT_TERM_KIND
    group_label: str | None = None
    is_teaching: bool = True

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


@dataclass
class Break:
    break_id: int
    year_id: int
    name: str
    start_date: str
    end_date: str
    type: str
    notes: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    am_pm: str = DEFAULT_BREAK_AM_PM
    group_label: str | None = None

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date or self.start_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0


@dataclass
class YearGroup:
    group_id: int
    year_id: int
    label: str
    notes: str | None
    created_at: str


@dataclass
class CalendarEvent:
    event_id: int
    year_id: int
    name: str
    kind: str
    date: str
    end_date: str | None
    notes: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str
    group_label: str | None = None
    owner: str | None = None
    department: str | None = None
    location: str | None = None
    capacity: int | None = None
    repeat_rule: str | None = None
    repeat_interval: int = 1
    repeat_until: str | None = None

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.date)
            ed = _dt.date.fromisoformat(self.end_date or self.date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0

    @property
    def is_recurring(self) -> bool:
        return bool(self.repeat_rule)


@dataclass
class Period:
    """One slot in the shape of a teaching day."""
    period_id: int
    year_id: int
    name: str
    weekday: int
    start_time: str
    end_time: str
    cycle_week: int | None
    is_teaching: bool
    sort_order: int
    notes: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str

    @property
    def weekday_name(self) -> str:
        return WEEKDAY_NAMES[self.weekday] if 0 <= self.weekday < 7 else "?"

    @property
    def minutes(self) -> int:
        try:
            sh, sm = (int(x) for x in self.start_time.split(":"))
            eh, em = (int(x) for x in self.end_time.split(":"))
            return max(0, (eh * 60 + em) - (sh * 60 + sm))
        except Exception:
            return 0


@dataclass
class EventOccurrence:
    """One materialised instance of a (possibly recurring) event."""
    event: CalendarEvent
    date: str
    end_date: str

    @property
    def name(self) -> str:
        return self.event.name

    @property
    def kind(self) -> str:
        return self.event.kind


@dataclass
class YearNote:
    """A policy note, decision, or risk recorded against a year."""
    note_id: int
    year_id: int
    category: str
    title: str
    body: str | None
    author: str | None
    pinned: bool
    deleted_at: str | None
    created_at: str
    updated_at: str


@dataclass
class InsetStatus:
    """How the year's INSET days stand against its allowance."""
    year_id: int
    allowance: int
    planned: float
    remaining: float

    @property
    def over(self) -> bool:
        return self.planned > self.allowance

    @property
    def under(self) -> bool:
        return self.planned < self.allowance

    @property
    def message(self) -> str:
        if self.over:
            return (f"{self.planned:g} INSET days planned — "
                    f"{abs(self.remaining):g} over the allowance of "
                    f"{self.allowance}")
        if self.under:
            return (f"{self.planned:g} of {self.allowance} INSET days "
                    f"planned — {self.remaining:g} still to schedule")
        return f"All {self.allowance} INSET days scheduled"


@dataclass
class CalendarGap:
    """A stretch of weekdays inside the year covered by no term."""
    start_date: str
    end_date: str
    weekdays: int
    group_label: str | None = None


@dataclass
class YearSummary:
    year: AcademicYear
    terms: list[Term] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    teaching_days: int = 0
    non_teaching_days: int = 0
    weekend_days: int = 0


def _note_to_dict(n: YearNote) -> dict:
    return {
        "note_id": n.note_id, "year_id": n.year_id,
        "category": n.category, "title": n.title, "body": n.body,
        "author": n.author, "pinned": n.pinned,
    }


def _year_to_dict(y: AcademicYear) -> dict:
    return {
        "year_id": y.year_id, "name": y.name,
        "start_date": y.start_date, "end_date": y.end_date,
        "is_current": y.is_current, "status": y.status,
        "notes": y.notes, "campus_id": y.campus_id,
        "cycle_weeks": y.cycle_weeks, "cycle_anchor": y.cycle_anchor,
        "inset_allowance": y.inset_allowance,
    }


def _term_to_dict(t: Term) -> dict:
    return {
        "term_id": t.term_id, "year_id": t.year_id, "name": t.name,
        "start_date": t.start_date, "end_date": t.end_date,
        "kind": t.kind, "notes": t.notes,
        "group_label": t.group_label, "is_teaching": t.is_teaching,
    }


def _break_to_dict(b: Break) -> dict:
    return {
        "break_id": b.break_id, "year_id": b.year_id, "name": b.name,
        "start_date": b.start_date, "end_date": b.end_date,
        "type": b.type, "am_pm": b.am_pm, "notes": b.notes,
        "group_label": b.group_label,
    }


def _event_to_dict(e: CalendarEvent) -> dict:
    return {
        "event_id": e.event_id, "year_id": e.year_id, "name": e.name,
        "kind": e.kind, "date": e.date, "end_date": e.end_date,
        "notes": e.notes, "group_label": e.group_label,
        "owner": e.owner, "department": e.department,
        "location": e.location, "capacity": e.capacity,
        "repeat_rule": e.repeat_rule,
        "repeat_interval": e.repeat_interval,
        "repeat_until": e.repeat_until,
    }


def _period_to_dict(p: Period) -> dict:
    return {
        "period_id": p.period_id, "year_id": p.year_id, "name": p.name,
        "weekday": p.weekday, "start_time": p.start_time,
        "end_time": p.end_time, "cycle_week": p.cycle_week,
        "is_teaching": p.is_teaching, "sort_order": p.sort_order,
        "notes": p.notes,
    }
