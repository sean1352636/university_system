"""Enrolment reports: targets vs actuals, withdrawals, retention, counts.

Everything here except the targets themselves is a read over the live
records — enrolments, their learning aims (through
``enrolments.aims_for_enrolment`` / ``ilr.year_aims``) and the ILR
qualifying-period rule — so the figures cannot drift from the data.
Archived enrolments are always left out.

* **Targets** (``enrolment_targets``): a number of learners staff aim to
  enrol for an academic year and year group, optionally narrowed to a
  programme (a qualification type such as "A Level", "BTEC", "T Level")
  and/or a subject. Actuals are counted from live (Enrolled / Pending)
  enrolments; for a programme or subject target, the learners in that
  year group with an active or completed aim of that type / subject in
  the year.
* **Withdrawals and retention**: by ILR reason, month, year group and
  tutor group; early leavers (withdrawn inside the 42-day qualifying
  period); retention % = (starts − withdrawals) / starts, where both
  starts and withdrawals leave out the early leavers (they never counted
  as starts). Pending enrolments have not started and are not starts.

Every report returns dataclasses (or rows); :func:`to_csv` turns any of
them into CSV text.
"""

from __future__ import annotations

import csv
import dataclasses
import io
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _en,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    ilr as _ilr,
)

ValidationError = _en.ValidationError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_targets (
    target_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year  TEXT NOT NULL,
    year_group     INTEGER NOT NULL,
    programme      TEXT NOT NULL DEFAULT '',
    subject        TEXT NOT NULL DEFAULT '',
    target         INTEGER NOT NULL,
    set_by         TEXT,
    set_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (academic_year, year_group, programme, subject)
);
"""

_READY_PATHS: set[str] = set()


def init_db() -> None:
    key = str(_en.DB_PATH)
    if key in _READY_PATHS:
        return
    _en.init_db()
    with _en._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY_PATHS.add(key)


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return students


# ── Targets ─────────────────────────────────────────────────────────

@dataclass
class EnrolmentTarget:
    target_id: int
    academic_year: str
    year_group: int
    programme: str | None
    subject: str | None
    target: int
    set_by: str | None
    set_at: str | None

    @property
    def label(self) -> str:
        parts = [f"Year {self.year_group}"]
        if self.programme:
            parts.append(self.programme)
        if self.subject:
            parts.append(self.subject)
        return " ".join(parts)


def _target_row(r: Any) -> EnrolmentTarget:
    d = dict(r)
    d["programme"] = d["programme"] or None
    d["subject"] = d["subject"] or None
    return EnrolmentTarget(**d)


def _programme(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    canon = grade_scales.canonical_type(v)
    if canon is None:
        raise ValidationError("Programme must be a qualification type: "
                              + ", ".join(grade_scales.QUALIFICATION_TYPES))
    return canon


def set_target(academic_year: str, year_group: int, target: int, *,
               programme: str | None = None,
               subject: str | None = None) -> EnrolmentTarget:
    """Set (or replace) a target. Needs the enrolment writer capability."""
    _en._require_writer("set enrolment targets")
    init_db()
    _en.academic_year_dates(academic_year)
    try:
        yg = int(year_group)
    except (TypeError, ValueError):
        raise ValidationError("Year group must be 12 or 13") from None
    if yg not in _en.YEAR_GROUPS:
        raise ValidationError("Year group must be 12 or 13")
    try:
        n = int(target)
    except (TypeError, ValueError):
        raise ValidationError("Target must be a whole number") from None
    if n < 0 or n > 100000:
        raise ValidationError("Target must be between 0 and 100,000")
    prog = _programme(programme)
    subj = (subject or "").strip()
    with _en._connect() as conn:
        conn.execute(
            """INSERT INTO enrolment_targets (academic_year, year_group,
                   programme, subject, target, set_by, set_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(academic_year, year_group, programme, subject)
               DO UPDATE SET target = excluded.target, set_by = excluded.set_by,
                   set_at = excluded.set_at""",
            (academic_year, yg, prog, subj, n, _en._actor()))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM enrolment_targets WHERE academic_year = ? AND "
            "year_group = ? AND programme = ? AND subject = ?",
            (academic_year, yg, prog, subj)).fetchone()
    return _target_row(r)


def list_targets(academic_year: str | None = None) -> list[EnrolmentTarget]:
    init_db()
    sql = "SELECT * FROM enrolment_targets"
    args: tuple = ()
    if academic_year:
        sql += " WHERE academic_year = ?"
        args = (academic_year,)
    with _en._connect() as conn:
        rows = conn.execute(sql + " ORDER BY academic_year DESC, year_group, "
                            "programme, subject", args).fetchall()
    return [_target_row(r) for r in rows]


def delete_target(target_id: int) -> bool:
    _en._require_writer("delete enrolment targets")
    init_db()
    with _en._connect() as conn:
        cur = conn.execute("DELETE FROM enrolment_targets WHERE target_id = ?",
                           (int(target_id),))
        conn.commit()
        return cur.rowcount > 0


@dataclass
class TargetRow:
    target_id: int
    academic_year: str
    year_group: int
    programme: str | None
    subject: str | None
    target: int
    actual: int
    variance: int
    pct_of_target: float | None


def _live(academic_year: str, year_group: int | None = None) -> list[_en.Enrolment]:
    return [e for e in _en.list_enrolments(academic_year=academic_year,
                                           year_group=year_group)
            if e.is_live]


def _aims_in_year(e: _en.Enrolment) -> list[Any]:
    return [a for a in _ilr.year_aims(e) if a.status in ("Active", "Completed")]


def targets_vs_actuals(academic_year: str) -> list[TargetRow]:
    """Each target for the year beside the live count it measures."""
    rows: list[TargetRow] = []
    aims_cache: dict[int, list[Any]] = {}
    for t in list_targets(academic_year):
        live = _live(academic_year, t.year_group)
        if t.programme or t.subject:
            actual = 0
            for e in live:
                if e.enrolment_id not in aims_cache:
                    aims_cache[e.enrolment_id] = _aims_in_year(e)
                if any((not t.programme or a.qualification_type == t.programme)
                       and (not t.subject
                            or a.subject.lower() == t.subject.lower())
                       for a in aims_cache[e.enrolment_id]):
                    actual += 1
        else:
            actual = len(live)
        rows.append(TargetRow(
            target_id=t.target_id, academic_year=t.academic_year,
            year_group=t.year_group, programme=t.programme, subject=t.subject,
            target=t.target, actual=actual, variance=actual - t.target,
            pct_of_target=(round(100.0 * actual / t.target, 1)
                           if t.target else None)))
    return rows


@dataclass
class SubjectActual:
    academic_year: str
    year_group: int
    qualification_type: str
    subject: str
    learners: int


def subject_actuals(academic_year: str) -> list[SubjectActual]:
    """Learners on live enrolments per (year group, qualification type,
    subject), from their aims in the year."""
    counts: Counter = Counter()
    for e in _live(academic_year):
        seen = {(a.qualification_type, a.subject) for a in _aims_in_year(e)}
        for qtype, subject in seen:
            counts[(e.year_group, qtype, subject)] += 1
    return [SubjectActual(academic_year, yg, q, s, n)
            for (yg, q, s), n in sorted(counts.items())]


# ── Withdrawals and retention ───────────────────────────────────────

@dataclass
class WithdrawalAnalytics:
    academic_year: str
    starts: int                 # started, less early leavers
    withdrawals: int            # withdrawn after the qualifying period
    early_leavers: int          # withdrawn inside it (not starts)
    retention_pct: float | None
    by_reason: dict[str, int] = field(default_factory=dict)
    by_month: dict[str, int] = field(default_factory=dict)
    by_year_group: dict[str, int] = field(default_factory=dict)
    by_tutor_group: dict[str, int] = field(default_factory=dict)
    early_leaver_rows: list[Any] = field(default_factory=list)

    def breakdown_rows(self) -> list[dict[str, Any]]:
        """Flat rows (dimension, value, withdrawals) for a table or CSV."""
        out: list[dict[str, Any]] = []
        for dim, data in (("ILR reason", self.by_reason),
                          ("Month", self.by_month),
                          ("Year group", self.by_year_group),
                          ("Tutor group", self.by_tutor_group)):
            out.extend({"dimension": dim, "value": k, "withdrawals": v}
                       for k, v in data.items())
        return out


def withdrawal_analytics(academic_year: str) -> WithdrawalAnalytics:
    """Withdrawals for the year by reason / month / year group / tutor
    group (all withdrawals, early leavers included), plus retention."""
    started = [e for e in _en.list_enrolments(academic_year=academic_year)
               if e.status in ("Enrolled", "Withdrawn", "Completed")]
    withdrawn = [e for e in started if e.status == "Withdrawn"]
    early_ids = {e.enrolment_id for e in withdrawn
                 if _ilr.qualifying_status(e)[2]}
    starts = len(started) - len(early_ids)
    later = len(withdrawn) - len(early_ids)
    by_reason: Counter = Counter()
    by_month: Counter = Counter()
    by_year: Counter = Counter()
    by_tutor: Counter = Counter()
    for e in withdrawn:
        by_reason[_en.withdrawal_reason_label(e.withdrawal_reason)
                  or "(no reason)"] += 1
        by_month[(e.withdrawal_date or "")[:7] or "(no date)"] += 1
        by_year[f"Year {e.year_group}"] += 1
        by_tutor[e.tutor_group or "(none)"] += 1
    return WithdrawalAnalytics(
        academic_year=academic_year, starts=starts, withdrawals=later,
        early_leavers=len(early_ids),
        retention_pct=(round(100.0 * (starts - later) / starts, 1)
                       if starts else None),
        by_reason=dict(by_reason.most_common()),
        by_month=dict(sorted(by_month.items())),
        by_year_group=dict(sorted(by_year.items())),
        by_tutor_group=dict(sorted(by_tutor.items())),
        early_leaver_rows=_ilr.early_leavers(academic_year) if early_ids else [])


def return_intentions(academic_year: str) -> list[dict[str, Any]]:
    """Year 12 return intentions (enrolments.reintention_summary) as rows."""
    return [{"intention": k, "learners": v}
            for k, v in _en.reintention_summary(academic_year).items()]


@dataclass
class StatusCount:
    academic_year: str
    year_group: int
    status: str
    count: int


def status_counts(academic_year: str | None = None) -> list[StatusCount]:
    """Enrolments by year, year group and status (archived left out)."""
    counts: Counter = Counter(
        (e.academic_year, e.year_group, e.status)
        for e in _en.list_enrolments(academic_year=academic_year))
    order = {s: i for i, s in enumerate(_en.STATUSES)}
    rows = [StatusCount(y, g, s, n) for (y, g, s), n in counts.items()]
    rows.sort(key=lambda r: (r.year_group, order.get(r.status, 99)))
    rows.sort(key=lambda r: r.academic_year, reverse=True)  # newest first
    return rows


# ── CSV ─────────────────────────────────────────────────────────────

def _cell(v: Any) -> Any:
    if isinstance(v, (list, tuple, set)):
        return "; ".join(_cell(x) if not dataclasses.is_dataclass(x)
                         else str(getattr(x, "student_id", x)) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {x}" for k, x in v.items())
    if dataclasses.is_dataclass(v):
        return str(v)
    return "" if v is None else v


def to_csv(rows: Iterable[Any]) -> str:
    """CSV text for a list of report dataclasses or dicts (columns from
    the first row; lists and dicts are joined with '; '). A row with a
    ``csv_row()`` method (e.g. funding.CofRow) is written as that."""
    items = []
    for r in rows:
        if callable(getattr(r, "csv_row", None)):
            items.append(r.csv_row())
        elif dataclasses.is_dataclass(r) and not isinstance(r, type):
            items.append({f.name: getattr(r, f.name)
                          for f in dataclasses.fields(r)})
        elif isinstance(r, dict):
            items.append(dict(r))
        else:
            raise TypeError(f"Cannot write {type(r).__name__} as CSV")
    buf = io.StringIO()
    if not items:
        return ""
    w = csv.DictWriter(buf, fieldnames=list(items[0]), extrasaction="ignore")
    w.writeheader()
    for item in items:
        w.writerow({k: _cell(v) for k, v in item.items()})
    return buf.getvalue()
