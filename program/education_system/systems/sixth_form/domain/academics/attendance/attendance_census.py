"""Statutory attendance returns for the Sixth Form System.

Sibling to :mod:`attendance`. Attendance data leaves the college twice a
year in a shape nobody enjoys: a census return, and — for a sixth-form
or FE college — an ILR-style record of the guided learning hours a
learner actually attended, which is what the funding is calculated on.

Both are built from the same marks, and both are usually assembled in a
spreadsheet under time pressure. This module builds them from the data
and, more importantly, **validates them before they go**.

Three parts:

* **Code mapping** (:data:`NATIONAL_CODES`). The internal vocabulary in
  :mod:`attendance_codes` is already the sector's, but a return needs
  each mark classified as present / approved / authorised absence /
  unauthorised absence / not counted, and needs it consistently.
* **The extract** (:func:`census_extract`, :func:`ilr_extract`). One row
  per learner with the counts a return asks for, plus the derived
  figures — percentage attended, sessions possible, hours qualifying.
* **Validation** (:func:`validate`). The step that matters. A return
  with unmarked sessions, uncoded marks or learners with no timetable
  will be rejected or, worse, accepted and wrong. Every check says what
  is wrong and what to do about it.

**Nothing is submitted from here.** The output is a file and a report;
submitting it remains a deliberate act by somebody who has read the
validation output.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_codes as codes,
    attendance_sessions as sessions,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# How each internal code is classified in a return. Derived from the
# code's meaning so the two can never drift, with the letter kept
# because a return reports the letter.
PRESENT: str = "Present"
APPROVED: str = "Approved education activity"
AUTHORISED: str = "Authorised absence"
UNAUTHORISED: str = "Unauthorised absence"
NOT_COUNTED: str = "Not counted"

NATIONAL_CLASSES: tuple[str, ...] = (PRESENT, APPROVED, AUTHORISED,
                                     UNAUTHORISED, NOT_COUNTED)

_MEANING_TO_CLASS: dict[str, str] = {
    codes.PRESENT: PRESENT,
    codes.APPROVED: APPROVED,
    codes.AUTHORISED: AUTHORISED,
    codes.UNAUTHORISED: UNAUTHORISED,
    codes.NOT_COUNTED: NOT_COUNTED,
}

# Return kinds this module can build.
CENSUS: str = "census"
ILR: str = "ilr"
RETURN_KINDS: tuple[str, ...] = (CENSUS, ILR)

# Severity of a validation finding.
ERROR: str = "Error"
WARNING: str = "Warning"
INFO: str = "Info"
SEVERITIES: tuple[str, ...] = (ERROR, WARNING, INFO)

# Guided learning hours are counted from lesson length; where a slot has
# no times, this is assumed.
DEFAULT_LESSON_HOURS: float = 1.0

# A return with coverage below this should not be submitted.
MIN_COVERAGE_PCT: float = 95.0


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class CodeMapping:
    """One internal code and how a return classifies it."""

    code: str
    label: str
    national_class: str
    counts_as_attended: bool
    counts_as_possible: bool

    @property
    def label_line(self) -> str:
        return f"{self.code} — {self.label} → {self.national_class}"


@dataclass
class LearnerRow:
    """One learner's line in a return."""

    student_id: str
    student_name: str | None
    year_group: int | None
    sessions_possible: int = 0
    sessions_attended: int = 0
    present: int = 0
    approved: int = 0
    authorised: int = 0
    unauthorised: int = 0
    not_counted: int = 0
    unmarked: int = 0
    hours_possible: float = 0.0
    hours_attended: float = 0.0

    @property
    def attendance_pct(self) -> float | None:
        if self.sessions_possible == 0:
            return None
        return round(100.0 * self.sessions_attended
                     / self.sessions_possible, 1)

    @property
    def absence_pct(self) -> float | None:
        pct = self.attendance_pct
        return None if pct is None else round(100.0 - pct, 1)

    @property
    def unauthorised_pct(self) -> float | None:
        if self.sessions_possible == 0:
            return None
        return round(100.0 * self.unauthorised / self.sessions_possible, 1)

    @property
    def complete(self) -> bool:
        return self.unmarked == 0


@dataclass
class Finding:
    """One thing wrong with the return."""

    severity: str
    check: str
    detail: str
    student_id: str | None = None
    count: int = 0
    fix: str | None = None

    @property
    def label(self) -> str:
        who = f" ({self.student_id})" if self.student_id else ""
        fix = f" → {self.fix}" if self.fix else ""
        return f"[{self.severity}] {self.check}{who}: {self.detail}{fix}"


@dataclass
class Return:
    """A built return, before anybody sends it."""

    kind: str
    date_from: str
    date_to: str
    generated_on: str
    rows: list[LearnerRow] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def submittable(self) -> bool:
        return not self.errors

    @property
    def sessions_possible(self) -> int:
        return sum(r.sessions_possible for r in self.rows)

    @property
    def sessions_attended(self) -> int:
        return sum(r.sessions_attended for r in self.rows)

    @property
    def attendance_pct(self) -> float | None:
        if self.sessions_possible == 0:
            return None
        return round(100.0 * self.sessions_attended
                     / self.sessions_possible, 1)

    @property
    def summary(self) -> str:
        return (f"{self.kind.upper()} {self.date_from}→{self.date_to}: "
                f"{len(self.rows)} learner(s), "
                f"{self.attendance_pct or 0:.1f}% attendance, "
                f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)")


# ── Code mapping ────────────────────────────────────────────────────

def mapping() -> list[CodeMapping]:
    """Every internal code and how a return classifies it."""
    out: list[CodeMapping] = []
    for mark in codes.MARK_CODES:
        out.append(CodeMapping(
            code=mark.code, label=mark.label,
            national_class=_MEANING_TO_CLASS.get(mark.meaning, NOT_COUNTED),
            counts_as_attended=mark.attending,
            counts_as_possible=mark.possible))
    return out


def classify(code: str | None) -> str:
    """How a return classifies one mark.

    An unknown or missing code classifies as unauthorised absence, which
    is deliberately the unflattering choice: a return should never be
    improved by a gap in the data.
    """
    mark = codes.get_code(code)
    if mark is None:
        return UNAUTHORISED
    return _MEANING_TO_CLASS.get(mark.meaning, NOT_COUNTED)


def mapping_table() -> str:
    """The mapping as a printable table, for a return's documentation."""
    lines = [f"{'Code':<6}{'Meaning':<34}{'Return class':<28}Counts"]
    lines.append("-" * 78)
    for entry in mapping():
        counts = ("attended" if entry.counts_as_attended
                  else ("possible" if entry.counts_as_possible else "—"))
        lines.append(f"{entry.code:<6}{entry.label[:33]:<34}"
                     f"{entry.national_class:<28}{counts}")
    return "\n".join(lines)


# ── Hours ───────────────────────────────────────────────────────────

def _slot_hours(slot_id: int, slot_cache: dict[int, float]) -> float:
    """How many hours one lesson is worth."""
    if slot_id in slot_cache:
        return slot_cache[slot_id]
    hours = DEFAULT_LESSON_HOURS
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_register as _reg,
        )
        start, end = _reg.slot_window(slot_id)
        start_minutes = int(start[:2]) * 60 + int(start[3:5])
        end_minutes = int(end[:2]) * 60 + int(end[3:5])
        if end_minutes > start_minutes:
            hours = round((end_minutes - start_minutes) / 60.0, 2)
    except Exception:                       # pragma: no cover - defensive
        logger.debug("Could not derive hours for slot #%d", slot_id,
                     exc_info=True)
    slot_cache[slot_id] = hours
    return hours


# ── Building ────────────────────────────────────────────────────────

def _learner_rows(date_from: str, date_to: str, *,
                  include_hours: bool) -> list[LearnerRow]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    slot_cache: dict[int, float] = {}
    rows: dict[str, LearnerRow] = {}
    for student in _students.list_students():
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        year = getattr(student, "year_group", None)
        rows[student.student_id] = LearnerRow(
            student_id=student.student_id, student_name=student.full_name,
            year_group=int(year) if year not in (None, "") else None)

    for record in core.list_records(date_from=date_from, date_to=date_to):
        row = rows.get(record.student_id)
        if row is None:
            continue
        national = classify(record.code)
        hours = (_slot_hours(record.slot_id, slot_cache)
                 if include_hours else 0.0)

        if national == NOT_COUNTED:
            row.not_counted += 1
            continue
        row.sessions_possible += 1
        row.hours_possible += hours
        if national == PRESENT:
            row.present += 1
            row.sessions_attended += 1
            row.hours_attended += hours
        elif national == APPROVED:
            row.approved += 1
            row.sessions_attended += 1
            row.hours_attended += hours
        elif national == AUTHORISED:
            row.authorised += 1
        else:
            row.unauthorised += 1

    # Expected-but-unmarked sessions, which are the reason a return can
    # look excellent and be wrong.
    for student_id, row in rows.items():
        try:
            expected = sessions.expected_count(student_id=student_id,
                                               date_from=date_from,
                                               date_to=date_to)
        except Exception:                   # pragma: no cover - defensive
            continue
        marked = (row.sessions_possible + row.not_counted)
        row.unmarked = max(0, expected - marked)
        row.hours_possible = round(row.hours_possible, 2)
        row.hours_attended = round(row.hours_attended, 2)

    return [row for row in rows.values()
            if row.sessions_possible or row.not_counted or row.unmarked]


def census_extract(*, date_from: str, date_to: str) -> Return:
    """Build a census-shaped return: sessions, by classification."""
    return _build(CENSUS, date_from=date_from, date_to=date_to,
                  include_hours=False)


def ilr_extract(*, date_from: str, date_to: str) -> Return:
    """Build an ILR-shaped return: guided learning hours attended.

    Funding follows hours, not sessions, so a learner with six long
    lessons a week and one with ten short ones are not equivalent — and
    a session-based figure quietly treats them as if they were.
    """
    return _build(ILR, date_from=date_from, date_to=date_to,
                  include_hours=True)


def _build(kind: str, *, date_from: str, date_to: str,
           include_hours: bool) -> Return:
    date_from = core._validate_date(date_from)
    date_to = core._validate_date(date_to)
    if date_to < date_from:
        raise ValidationError("A return cannot end before it starts")
    out = Return(kind=kind, date_from=date_from, date_to=date_to,
                 generated_on=_dt.date.today().isoformat(),
                 rows=_learner_rows(date_from, date_to,
                                    include_hours=include_hours))
    out.findings = validate(out)
    logger.info("Built return: %s", out.summary)
    return out


# ── Validation ──────────────────────────────────────────────────────

def validate(return_: Return) -> list[Finding]:
    """Everything wrong with a return, worst first.

    The most valuable function in the module. A return that is merely
    *produced* is a liability; one that has been checked against the
    things that make returns wrong is worth submitting.
    """
    findings: list[Finding] = []
    date_from, date_to = return_.date_from, return_.date_to

    # 1. Register coverage.
    try:
        coverage = sessions.coverage(date_from=date_from, date_to=date_to)
        if coverage.expected and coverage.percentage is not None:
            if coverage.percentage < MIN_COVERAGE_PCT:
                findings.append(Finding(
                    severity=ERROR, check="Register coverage",
                    count=coverage.missing,
                    detail=(f"{coverage.missing} expected session(s) were "
                            f"never marked ({coverage.percentage:.1f}% "
                            "coverage)"),
                    fix="Take the outstanding registers before submitting"))
            else:
                findings.append(Finding(
                    severity=INFO, check="Register coverage",
                    detail=f"{coverage.percentage:.1f}% of expected sessions "
                           "are marked"))
    except Exception:                       # pragma: no cover - defensive
        logger.debug("Coverage check unavailable", exc_info=True)

    # 2. Uncoded marks.
    try:
        uncoded = codes.uncoded_count(date_from=date_from, date_to=date_to)
        if uncoded:
            findings.append(Finding(
                severity=ERROR, check="Uncoded marks", count=uncoded,
                detail=f"{uncoded} mark(s) have no statutory code",
                fix="Backfill codes from statuses, then re-run"))
    except Exception:                       # pragma: no cover - defensive
        logger.debug("Uncoded check unavailable", exc_info=True)

    # 3. Marks still sitting on `N` — "no reason yet" is not a return
    #    category, it is an admission that nobody chased it.
    stale_n = len(core.list_records(code="N", date_from=date_from,
                                    date_to=date_to))
    if stale_n:
        findings.append(Finding(
            severity=WARNING, check="Undecided absences", count=stale_n,
            detail=f"{stale_n} absence(s) are still coded N (no reason "
                   "established)",
            fix="Recode as authorised or unauthorised before submitting"))

    # 4. Learners with unmarked sessions.
    incomplete = [r for r in return_.rows if r.unmarked]
    if incomplete:
        findings.append(Finding(
            severity=WARNING, check="Incomplete learner records",
            count=len(incomplete),
            detail=(f"{len(incomplete)} learner(s) have expected sessions "
                    "with no mark"),
            fix="These learners' percentages are calculated on the marks "
                "that exist"))

    # 5. Learners with no sessions at all.
    empty = [r for r in return_.rows if r.sessions_possible == 0]
    for row in empty[:20]:
        findings.append(Finding(
            severity=WARNING, check="No countable sessions",
            student_id=row.student_id,
            detail="learner has no sessions counting toward the return",
            fix="Check they are timetabled and still enrolled"))

    # 6. Impossible percentages.
    for row in return_.rows:
        if row.attendance_pct is not None and row.attendance_pct > 100:
            findings.append(Finding(
                severity=ERROR, check="Impossible percentage",
                student_id=row.student_id,
                detail=f"attendance calculates as {row.attendance_pct}%",
                fix="Look for duplicate marks on the same session"))

    # 7. Calendar sanity — a return over a period with no teaching days
    #    is almost always the wrong date range.
    try:
        teaching = calendar.teaching_days(date_from, date_to)
        if not teaching:
            findings.append(Finding(
                severity=ERROR, check="Date range",
                detail="the period contains no teaching days",
                fix="Check the dates, and that term dates are set up"))
        elif len(teaching) < 5:
            findings.append(Finding(
                severity=WARNING, check="Date range",
                detail=f"only {len(teaching)} teaching day(s) in the period"))
    except Exception:                       # pragma: no cover - defensive
        logger.debug("Calendar check unavailable", exc_info=True)

    # 8. Voided marks in the window, which somebody should have a reason
    #    for if there are many.
    voided = len(core.list_records(date_from=date_from, date_to=date_to,
                                   voided_only=True))
    if voided:
        findings.append(Finding(
            severity=INFO, check="Voided marks", count=voided,
            detail=f"{voided} mark(s) were voided in this period and are "
                   "excluded"))

    order = {ERROR: 0, WARNING: 1, INFO: 2}
    findings.sort(key=lambda f: (order.get(f.severity, 3), -f.count))
    return findings


def validation_report(return_: Return) -> str:
    """The validation output as text, to read before submitting."""
    lines = [f"VALIDATION — {return_.kind.upper()} "
             f"{return_.date_from} to {return_.date_to}",
             "-" * 72]
    if not return_.findings:
        lines.append("  No issues found.")
    for finding in return_.findings:
        lines.append(f"  {finding.label}")
    lines.append("-" * 72)
    lines.append("  SUBMITTABLE" if return_.submittable
                 else f"  NOT SUBMITTABLE — {len(return_.errors)} error(s) "
                      "must be fixed first")
    return "\n".join(lines)


# ── Export ──────────────────────────────────────────────────────────

_CENSUS_COLUMNS: tuple[str, ...] = (
    "student_id", "student_name", "year_group", "sessions_possible",
    "sessions_attended", "attendance_pct", "present", "approved",
    "authorised", "unauthorised", "not_counted", "unmarked",
)

_ILR_COLUMNS: tuple[str, ...] = (
    "student_id", "student_name", "year_group", "hours_possible",
    "hours_attended", "attendance_pct", "sessions_possible",
    "sessions_attended", "unauthorised", "unmarked",
)


def to_csv(return_: Return) -> str:
    """The return as CSV.

    Refuses to render a return with errors: producing a file that looks
    submittable is the one thing this module must not do.
    """
    if not return_.submittable:
        raise ValidationError(
            f"{len(return_.errors)} validation error(s) must be fixed "
            "before this return can be exported — see validation_report()")
    columns = _ILR_COLUMNS if return_.kind == ILR else _CENSUS_COLUMNS
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in return_.rows:
        writer.writerow([_value(row, column) for column in columns])
    return buffer.getvalue()


def _value(row: LearnerRow, column: str) -> Any:
    if column == "attendance_pct":
        return "" if row.attendance_pct is None else row.attendance_pct
    return getattr(row, column, "")


def save(return_: Return, path: str) -> str:
    """Write the return to a CSV file and return the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_csv(return_), encoding="utf-8")
    logger.info("Return written to %s", target)
    return str(target)


def summary_by_year_group(return_: Return) -> dict[str, dict[str, Any]]:
    """The return aggregated by year group, which is how it is reported."""
    out: dict[str, dict[str, Any]] = {}
    for row in return_.rows:
        key = (f"Year {row.year_group}" if row.year_group is not None
               else "Unknown")
        entry = out.setdefault(key, {"learners": 0, "possible": 0,
                                     "attended": 0, "unauthorised": 0})
        entry["learners"] += 1
        entry["possible"] += row.sessions_possible
        entry["attended"] += row.sessions_attended
        entry["unauthorised"] += row.unauthorised
    for entry in out.values():
        entry["attendance_pct"] = (
            round(100.0 * entry["attended"] / entry["possible"], 1)
            if entry["possible"] else None)
    return out


def code_usage(*, date_from: str, date_to: str) -> dict[str, int]:
    """How often each code was used — read before every return.

    A college whose `O` count is zero is not a college with no truancy;
    it is a college coding everything `C`, and a return built on that is
    wrong in a way nobody downstream can detect.
    """
    out: dict[str, int] = {}
    for record in core.list_records(date_from=date_from, date_to=date_to):
        key = record.code or "(uncoded)"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda item: -item[1]))
