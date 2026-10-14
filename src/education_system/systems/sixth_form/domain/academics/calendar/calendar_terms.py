"""Term awareness for the Sixth Form Calendar.

Sibling to :mod:`calendar`. The events calendar has never known what
the college's year looks like: nothing stopped a trip being scheduled
in half term, a rehearsal on an INSET day, or a charity bake sale in
the middle of the mock exam fortnight. The knowledge exists —
:mod:`academic_year` owns terms, breaks and INSET days — but the
events side never asked.

It used to ask :mod:`attendance_calendar`, which keeps its own copy
of the term dates for register purposes. That made three term
tables in one system and no answer to which one was right. These
functions now go through :mod:`academic_year_adapters`, the
academic year's published contract for exactly this question.

:func:`check` asks. For a proposed event it reports, day by day:

* **Closed days** — weekends, holidays, INSET (an event *for* an
  INSET day is fine; the warning tells you what you are doing).
* **Exam windows** — days already carrying an Exam or Mock Exam
  event, where scheduling anything loud is somebody's bad week.
* **Lead time** — trips and parents' evenings announced the night
  before are how a college gets a reputation; the table below says
  how much notice each type deserves.

Like :mod:`calendar_clashes`, everything is a warning, not a veto —
Saturday fixtures and holiday revision schools are real. The views
show the warnings; a human decides.

:func:`week_label` is the college's own dialect for a date — "Week 3
of Autumn Term" — used anywhere staff read dates.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

ValidationError = core.ValidationError


# How many days' notice each event type deserves. Absent types need
# none. Deliberately a table: the argument about trip notice periods
# is a one-line change, not a code review.
LEAD_TIME_DAYS: dict[str, int] = {
    "Trip": 14,
    "Parents' Evening": 14,
    "Open Day": 14,
    "Exam": 7,
    "Mock Exam": 7,
    "Sports Fixture": 5,
    "Social": 5,
}

# Types that legitimately sit on closed days and should not trip the
# closed-day warning: a Holiday event *is* the closure, INSET happens
# on the INSET day, and training often lands there too.
_CLOSURE_TYPES: tuple[str, ...] = ("Holiday", "INSET", "Training")

# Types allowed inside an exam window without a warning.
_EXAM_TYPES: tuple[str, ...] = ("Exam", "Mock Exam")


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class TermWarning:
    """One reason a date is a bad fit."""

    kind: str            # "closed" | "exam-window" | "lead-time"
    date: str
    detail: str

    @property
    def label(self) -> str:
        return f"[{self.kind}] {self.date}: {self.detail}"


@dataclass
class TermReport:
    warnings: list[TermWarning] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.warnings

    @property
    def summary(self) -> str:
        if self.clean:
            return "No term-calendar concerns."
        return "\n".join(w.label for w in self.warnings)


# ── The academic-year bridge ────────────────────────────────────────

def _year_adapters():
    """The terms/closures source, or None where it is not installed.
    Everything here degrades to silence without it — a college that
    has never set its terms up gets no term warnings, not a crash."""
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (  # noqa: E501
            academic_year_adapters as adapters,
        )
        return adapters
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("academic_year_adapters unavailable", exc_info=True)
        return None


def term_for(date_iso: str):
    """The Term covering a date, if the college has one set up."""
    adapters = _year_adapters()
    if adapters is None:
        return None
    try:
        return adapters.term_on(core._validate_date(date_iso, "Date"))
    except Exception:                       # pragma: no cover - defensive
        return None


def week_label(date_iso: str) -> str | None:
    """"Week 3 of Autumn Term" — how the college actually says a date.

    Week 1 is the week containing the term's first day; weeks run
    Monday to Sunday. None outside any term, and the caller shows
    the bare date.
    """
    s = core._validate_date(date_iso, "Date")
    term = term_for(s)
    if term is None:
        return None
    day = _dt.date.fromisoformat(s)
    first = _dt.date.fromisoformat(term.start_date)
    monday_of = lambda d: d - _dt.timedelta(days=d.weekday())  # noqa: E731
    week = ((monday_of(day) - monday_of(first)).days // 7) + 1
    return f"Week {week} of {term.name}"


def _day_status(date_iso: str):
    """The academic year's verdict on one date, or None when it has
    nothing to say."""
    adapters = _year_adapters()
    if adapters is None:
        return None
    try:
        return adapters.day_status(
            core._validate_date(date_iso, "Date"))
    except Exception:                       # pragma: no cover - defensive
        return None


def is_open(date_iso: str) -> bool:
    """Whether the college teaches on this date. Unknown ⇒ assume
    open — a missing term table should not flag every event."""
    status = _day_status(date_iso)
    return True if status is None else status.open


def closure_reason(date_iso: str) -> str | None:
    status = _day_status(date_iso)
    if status is None or status.open:
        return None
    return status.reason or "Closed"


# ── Exam windows ────────────────────────────────────────────────────

def exam_windows(date_from: str, date_to: str) -> set[str]:
    """Dates in the range carrying a live Exam / Mock Exam event."""
    out: set[str] = set()
    for etype in _EXAM_TYPES:
        for e in core.list_events(event_type=etype,
                                  date_from=date_from,
                                  date_to=date_to):
            if e.status in ("Cancelled", "Postponed"):
                continue
            sd = _dt.date.fromisoformat(e.start_date)
            ed = _dt.date.fromisoformat(e.end_date)
            for i in range((ed - sd).days + 1):
                out.add((sd + _dt.timedelta(days=i)).isoformat())
    return out


# ── The check ───────────────────────────────────────────────────────

def check(payload: dict[str, Any], *,
          today: str | None = None,
          exclude_event_id: int | None = None) -> TermReport:
    """Everything the term calendar has to say about a proposed event.

    ``today`` is injectable for tests; ``exclude_event_id`` keeps an
    edit to an exam from warning about its own window.
    """
    core.init_db()
    p = core._validate_payload(payload)
    now = core._validate_date(today, "today") if today \
        else _dt.date.today().isoformat()
    report = TermReport()

    sd = _dt.date.fromisoformat(p["start_date"])
    ed = _dt.date.fromisoformat(p["end_date"])
    dates = [(sd + _dt.timedelta(days=i)).isoformat()
             for i in range((ed - sd).days + 1)]

    # Closed days — unless the event is itself the closure's business.
    if p["event_type"] not in _CLOSURE_TYPES:
        for date in dates:
            # One status per date: is_open() + closure_reason()
            # would resolve the academic year and re-query terms
            # and breaks twice for every day of the event.
            status = _day_status(date)
            if status is not None and not status.open:
                reason = status.reason or "College closed"
                report.warnings.append(TermWarning(
                    kind="closed", date=date,
                    detail=f"{reason} — is this event really "
                           "happening then?"))

    # Exam windows — unless the event is an exam.
    if p["event_type"] not in _EXAM_TYPES:
        windows = exam_windows(p["start_date"], p["end_date"])
        if exclude_event_id is not None:
            own = core.get_event(exclude_event_id)
            if own is not None and own.event_type in _EXAM_TYPES:
                osd = _dt.date.fromisoformat(own.start_date)
                oed = _dt.date.fromisoformat(own.end_date)
                for i in range((oed - osd).days + 1):
                    windows.discard(
                        (osd + _dt.timedelta(days=i)).isoformat())
        for date in dates:
            if date in windows:
                report.warnings.append(TermWarning(
                    kind="exam-window", date=date,
                    detail="Falls inside an exam window"))

    # Lead time — only for events still in the future.
    needed = LEAD_TIME_DAYS.get(p["event_type"], 0)
    if needed and p["start_date"] > now:
        notice = (_dt.date.fromisoformat(p["start_date"])
                  - _dt.date.fromisoformat(now)).days
        if notice < needed:
            report.warnings.append(TermWarning(
                kind="lead-time", date=p["start_date"],
                detail=(f"{p['event_type']} needs {needed} days' "
                        f"notice; this gives {notice}")))

    if report.warnings:
        logger.info("Term check for %r: %d warning(s)", p["title"],
                    len(report.warnings))
    return report
