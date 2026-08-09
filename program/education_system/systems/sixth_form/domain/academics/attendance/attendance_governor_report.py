"""Governor and SLT attendance report for the Sixth Form System.

Sibling to :mod:`attendance`. Everything needed for the termly
attendance report already exists somewhere in this package. Assembling
it is a morning's work every term, done by hand, and the figures never
quite match the ones in the last report because somebody used a
different window.

So the report is a function. :func:`build` gathers the same figures the
same way every time, and :func:`render_text` lays them out on one page.

**What goes on the page is a deliberate editorial choice:**

* The headline figure, and the change on the same point last year — a
  percentage with nothing to compare it to tells a governing body
  nothing.
* Persistent and severe absence as counts *and* as a share, because a
  count going up in a growing cohort may be a share going down.
* What the college did about it — letters, cases, contracts, calls.
  Governors ask "and what are you doing?", and the answer should not be
  assembled in the meeting.
* An honest data-quality line. A report built on 84% register coverage
  should say so on the same page as its headline figure, not in a
  footnote nobody reads.

Nothing here computes a new number. Every figure comes from the module
that owns it, so the report and the screens can never disagree.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_analytics as analytics,
    attendance_calendar as calendar,
    attendance_cohorts as cohorts,
    attendance_sessions as sessions,
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Headline:
    """The figures at the top of the page."""

    attendance_pct: float | None
    previous_pct: float | None
    target_pct: float | None
    unauthorised_pct: float | None
    learners: int
    sessions_possible: int
    sessions_recorded: int

    @property
    def change(self) -> float | None:
        if self.attendance_pct is None or self.previous_pct is None:
            return None
        return round(self.attendance_pct - self.previous_pct, 1)

    @property
    def against_target(self) -> float | None:
        if self.attendance_pct is None or self.target_pct is None:
            return None
        return round(self.attendance_pct - self.target_pct, 1)

    @property
    def coverage_pct(self) -> float | None:
        if self.sessions_possible == 0:
            return None
        return round(100.0 * self.sessions_recorded
                     / self.sessions_possible, 1)

    @property
    def direction(self) -> str:
        change = self.change
        if change is None:
            return "no comparison available"
        if change >= 0.5:
            return "up"
        if change <= -0.5:
            return "down"
        return "broadly flat"


@dataclass
class CohortLine:
    """One band, with its share of the cohort."""

    band: str
    count: int
    share_pct: float | None
    previous_count: int | None = None

    @property
    def change(self) -> int | None:
        if self.previous_count is None:
            return None
        return self.count - self.previous_count


@dataclass
class ActionLine:
    """One thing the college did, and how much of it."""

    action: str
    count: int
    detail: str | None = None


@dataclass
class GovernorReport:
    """The whole page."""

    title: str
    period_label: str
    date_from: str
    date_to: str
    generated_on: str
    headline: Headline
    cohorts: list[CohortLine] = field(default_factory=list)
    by_year_group: list[tuple[str, float | None]] = field(default_factory=list)
    actions: list[ActionLine] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    data_quality: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "period": self.period_label,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "generated_on": self.generated_on,
            "headline": {
                "attendance_pct": self.headline.attendance_pct,
                "previous_pct": self.headline.previous_pct,
                "change": self.headline.change,
                "target_pct": self.headline.target_pct,
                "against_target": self.headline.against_target,
                "unauthorised_pct": self.headline.unauthorised_pct,
                "learners": self.headline.learners,
                "coverage_pct": self.headline.coverage_pct,
            },
            "cohorts": [{"band": c.band, "count": c.count,
                         "share_pct": c.share_pct, "change": c.change}
                        for c in self.cohorts],
            "by_year_group": [{"year_group": y, "attendance_pct": p}
                              for y, p in self.by_year_group],
            "actions": [{"action": a.action, "count": a.count,
                         "detail": a.detail} for a in self.actions],
            "concerns": self.concerns,
            "strengths": self.strengths,
            "data_quality": self.data_quality,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ── Gathering ───────────────────────────────────────────────────────

def _term_window(date: str) -> tuple[str, str, str]:
    """The term containing a date, or a rolling term if none is set up."""
    term = calendar.term_for(date)
    if term is not None:
        return term.start_date, min(term.end_date, date), term.name
    anchor = _dt.date.fromisoformat(date)
    start = (anchor - _dt.timedelta(days=90)).isoformat()
    return start, date, "Last 90 days"


def _headline(date_from: str, date_to: str) -> Headline:
    benchmark = analytics.benchmark(date_from=date_from, date_to=date_to)
    unauthorised = _unauthorised_share(date_from, date_to)
    coverage = sessions.coverage(date_from=date_from, date_to=date_to)
    return Headline(
        attendance_pct=benchmark.current_pct,
        previous_pct=benchmark.previous_pct,
        target_pct=benchmark.target_pct,
        unauthorised_pct=unauthorised,
        learners=benchmark.learners,
        sessions_possible=coverage.expected,
        sessions_recorded=coverage.recorded)


def _unauthorised_share(date_from: str, date_to: str) -> float | None:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_codes as codes,
    )
    possible = unauthorised = 0
    for record in core.list_records(date_from=date_from, date_to=date_to):
        if not codes.counts_toward_possible(record.code):
            continue
        possible += 1
        if codes.is_unauthorised_absence(record.code):
            unauthorised += 1
    return round(100.0 * unauthorised / possible, 1) if possible else None


def _cohort_lines(date_from: str, date_to: str,
                  learners: int) -> list[CohortLine]:
    window_days = max(1, (_dt.date.fromisoformat(date_to)
                          - _dt.date.fromisoformat(date_from)).days)
    counts = cohorts.band_counts(window_days=window_days, date_to=date_to)
    out: list[CohortLine] = []
    for band in (cohorts.SEVERE, cohorts.PERSISTENT, cohorts.AT_RISK):
        count = counts.get(band, 0)
        out.append(CohortLine(
            band=band, count=count,
            share_pct=(round(100.0 * count / learners, 1)
                       if learners else None)))
    return out


def _year_group_lines(date_from: str,
                      date_to: str) -> list[tuple[str, float | None]]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    tally: dict[str, list[int]] = {}
    year_of: dict[str, str] = {}
    for student in _students.list_students():
        year = getattr(student, "year_group", None)
        year_of[student.student_id] = (f"Year {year}" if year not in (None, "")
                                       else "Unknown")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_codes as codes,
    )
    for record in core.list_records(date_from=date_from, date_to=date_to):
        if not codes.counts_toward_possible(record.code):
            continue
        key = year_of.get(record.student_id, "Unknown")
        entry = tally.setdefault(key, [0, 0])
        entry[0] += 1
        if codes.counts_as_present(record.code) or \
                record.status in core.ATTENDING_STATUSES:
            entry[1] += 1
    return [(year, round(100.0 * attending / total, 1) if total else None)
            for year, (total, attending) in sorted(tally.items())]


def _actions(date_from: str, date_to: str) -> list[ActionLine]:
    """What the college actually did. Each source is optional."""
    out: list[ActionLine] = []

    def add(label: str, fn, detail: str | None = None) -> None:
        try:
            count = fn()
            if count:
                out.append(ActionLine(action=label, count=count,
                                      detail=detail))
        except Exception:                   # pragma: no cover - optional dep
            logger.debug("Governor report: %s unavailable", label,
                         exc_info=True)

    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_calling as _calling,
        attendance_escalation as _escalation,
        attendance_letters as _letters,
        attendance_rewards as _rewards,
        attendance_safeguarding as _safeguarding,
    )
    add("Attendance letters sent",
        lambda: sum(_letters.stage_counts().values()))
    add("First-day calls made",
        lambda: len(_calling.list_calls(date_from=date_from, date_to=date_to,
                                        limit=5000)))
    add("Cases opened",
        lambda: len([c for c in _escalation.list_cases(limit=2000)
                     if date_from <= c.opened_on <= date_to]))
    add("Attendance contracts agreed",
        lambda: len([c for c in _escalation.list_contracts(limit=2000)
                     if date_from <= c.start_date <= date_to]))
    add("Safeguarding alerts raised",
        lambda: len([a for a in _safeguarding.list_alerts(limit=2000)
                     if date_from <= a.raised_on <= date_to]))
    add("Attendance awards given",
        lambda: sum(_rewards.counts().values()))
    return out


def _data_quality(headline: Headline, date_from: str,
                  date_to: str) -> list[str]:
    """Say plainly how trustworthy the figures are.

    On the same page as the headline. A report whose caveats live in an
    appendix is a report whose caveats do not exist.
    """
    notes: list[str] = []
    coverage = headline.coverage_pct
    if coverage is None:
        notes.append("Register coverage could not be calculated — the "
                     "figures below are based on the marks that exist.")
    elif coverage < 95:
        notes.append(
            f"Register coverage is {coverage:.1f}%: "
            f"{headline.sessions_possible - headline.sessions_recorded} "
            "expected session(s) were never marked. Unmarked lessons are "
            "excluded, so the headline figure is likely to be flattering.")
    else:
        notes.append(f"Register coverage is {coverage:.1f}%.")

    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_anomalies as _anomalies,
        )
        report = _anomalies.sweep(date_from=date_from, date_to=date_to)
        high = len(report.high_confidence)
        if high:
            notes.append(
                f"{high} register(s) show marking patterns worth reviewing "
                "(all-present runs, heavy prefill, or late marking).")
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Anomaly sweep unavailable for the report",
                     exc_info=True)
    return notes


def _narrative(headline: Headline,
               cohort_lines: list[CohortLine]) -> tuple[list[str], list[str]]:
    """Two short lists: what is going well, what is not.

    Generated from the figures rather than written, so they cannot
    quietly disagree with the table above them.
    """
    strengths: list[str] = []
    concerns: list[str] = []

    change = headline.change
    if change is not None and change >= 0.5:
        strengths.append(
            f"Attendance is up {change:.1f} percentage points on the same "
            "point last year.")
    elif change is not None and change <= -0.5:
        concerns.append(
            f"Attendance is down {abs(change):.1f} percentage points on the "
            "same point last year.")

    against = headline.against_target
    if against is not None and against >= 0:
        strengths.append(
            f"The college is {against:.1f} points above its "
            f"{headline.target_pct:g}% target.")
    elif against is not None:
        concerns.append(
            f"The college is {abs(against):.1f} points below its "
            f"{headline.target_pct:g}% target.")

    for line in cohort_lines:
        if line.band == cohorts.SEVERE and line.count:
            concerns.append(
                f"{line.count} learner(s) are severely absent "
                f"({line.share_pct:.1f}% of the cohort) — each is an "
                "individual safeguarding case rather than an attendance one.")
        if line.band == cohorts.PERSISTENT and line.share_pct is not None:
            if line.share_pct >= 15:
                concerns.append(
                    f"Persistent absence stands at {line.share_pct:.1f}% of "
                    "the cohort.")
            elif line.share_pct <= 8:
                strengths.append(
                    f"Persistent absence is {line.share_pct:.1f}% of the "
                    "cohort.")

    if headline.unauthorised_pct is not None \
            and headline.unauthorised_pct >= 3:
        concerns.append(
            f"Unauthorised absence is {headline.unauthorised_pct:.1f}% of "
            "possible sessions.")
    return strengths, concerns


# ── Building ────────────────────────────────────────────────────────

def build(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    period_label: str | None = None,
    title: str = "Attendance report",
) -> GovernorReport:
    """Assemble the report.

    Defaults to the current term, which is what a termly report means
    and what nobody can be bothered to type.
    """
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    if date_from is None:
        date_from, date_to, label = _term_window(date_to)
    else:
        date_from = core._validate_date(date_from)
        label = period_label or f"{date_from} to {date_to}"
    label = period_label or label

    headline = _headline(date_from, date_to)
    cohort_lines = _cohort_lines(date_from, date_to, headline.learners)
    strengths, concerns = _narrative(headline, cohort_lines)

    report = GovernorReport(
        title=title, period_label=label, date_from=date_from,
        date_to=date_to, generated_on=_dt.date.today().isoformat(),
        headline=headline, cohorts=cohort_lines,
        by_year_group=_year_group_lines(date_from, date_to),
        actions=_actions(date_from, date_to),
        concerns=concerns, strengths=strengths,
        data_quality=_data_quality(headline, date_from, date_to))
    logger.info("Governor report built for %s (%s → %s)", label, date_from,
                date_to)
    return report


# ── Rendering ───────────────────────────────────────────────────────

def _pct(value: float | None, *, places: int = 1) -> str:
    return "—" if value is None else f"{value:.{places}f}%"


def render_text(report: GovernorReport, *, width: int = 72) -> str:
    """The one-page version, as plain text.

    Plain text on purpose: it pastes into a board paper, an email and a
    minute without anybody fighting a template.
    """
    rule = "─" * width
    lines: list[str] = [
        report.title.upper(),
        f"{report.period_label}  ({report.date_from} to {report.date_to})",
        f"Generated {report.generated_on}",
        rule,
        "",
        "HEADLINE",
    ]
    headline = report.headline
    change = ("" if headline.change is None
              else f"  ({headline.change:+.1f} on last year)")
    lines += [
        f"  Attendance            {_pct(headline.attendance_pct)}{change}",
        f"  Target                {_pct(headline.target_pct, places=0)}"
        + ("" if headline.against_target is None
           else f"  ({headline.against_target:+.1f})"),
        f"  Unauthorised absence  {_pct(headline.unauthorised_pct)}",
        f"  Learners              {headline.learners}",
        "",
        "COHORTS",
    ]
    for line in report.cohorts:
        lines.append(f"  {line.band:<22}{line.count:>5}"
                     f"   ({_pct(line.share_pct)} of cohort)")

    if report.by_year_group:
        lines += ["", "BY YEAR GROUP"]
        for year, percentage in report.by_year_group:
            lines.append(f"  {year:<22}{_pct(percentage):>8}")

    if report.actions:
        lines += ["", "WHAT THE COLLEGE DID"]
        for action in report.actions:
            lines.append(f"  {action.action:<34}{action.count:>5}")

    if report.strengths:
        lines += ["", "STRENGTHS"]
        lines += [f"  • {s}" for s in report.strengths]
    if report.concerns:
        lines += ["", "CONCERNS"]
        lines += [f"  • {c}" for c in report.concerns]

    lines += ["", "DATA QUALITY"]
    lines += [f"  • {note}" for note in report.data_quality]
    lines += ["", rule]
    return "\n".join(lines)


def render_markdown(report: GovernorReport) -> str:
    """The same page as Markdown, for a board pack or a wiki."""
    headline = report.headline
    lines = [
        f"# {report.title}",
        "",
        f"**{report.period_label}** · {report.date_from} to {report.date_to} "
        f"· generated {report.generated_on}",
        "",
        "## Headline",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Attendance | {_pct(headline.attendance_pct)} |",
        f"| Change on last year | "
        f"{'—' if headline.change is None else f'{headline.change:+.1f} pts'} |",
        f"| Target | {_pct(headline.target_pct, places=0)} |",
        f"| Unauthorised absence | {_pct(headline.unauthorised_pct)} |",
        f"| Learners | {headline.learners} |",
        f"| Register coverage | {_pct(headline.coverage_pct)} |",
        "",
        "## Cohorts",
        "",
        "| Band | Learners | Share |",
        "| --- | ---: | ---: |",
    ]
    for line in report.cohorts:
        lines.append(f"| {line.band} | {line.count} | "
                     f"{_pct(line.share_pct)} |")

    if report.by_year_group:
        lines += ["", "## By year group", "",
                  "| Year group | Attendance |", "| --- | ---: |"]
        for year, percentage in report.by_year_group:
            lines.append(f"| {year} | {_pct(percentage)} |")

    if report.actions:
        lines += ["", "## What the college did", "",
                  "| Action | Count |", "| --- | ---: |"]
        for action in report.actions:
            lines.append(f"| {action.action} | {action.count} |")

    if report.strengths:
        lines += ["", "## Strengths", ""]
        lines += [f"- {s}" for s in report.strengths]
    if report.concerns:
        lines += ["", "## Concerns", ""]
        lines += [f"- {c}" for c in report.concerns]

    lines += ["", "## Data quality", ""]
    lines += [f"- {note}" for note in report.data_quality]
    return "\n".join(lines)


def save(report: GovernorReport, path: str, *,
         fmt: str = "text") -> str:
    """Write the report to a file and return the path."""
    from pathlib import Path
    renderers = {"text": render_text, "markdown": render_markdown,
                 "json": lambda r: r.to_json()}
    if fmt not in renderers:
        raise ValidationError(
            f"Format must be one of: {', '.join(renderers)}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(renderers[fmt](report), encoding="utf-8")
    logger.info("Governor report written to %s", target)
    return str(target)


def termly_series(*, terms: int = 6) -> list[tuple[str, float | None]]:
    """The headline figure over recent terms, for a trend line.

    A single term's figure invites an argument about whether it is
    seasonal. Six of them do not.
    """
    out: list[tuple[str, float | None]] = []
    for term in calendar.list_terms()[-max(1, terms):]:
        percentage, _learners = analytics._window_percentage(
            term.start_date, term.end_date)
        out.append((term.label, percentage))
    return out
