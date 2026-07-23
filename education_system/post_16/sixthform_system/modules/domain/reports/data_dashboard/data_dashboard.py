"""Data Dashboard for the Sixth Form System.

Tabular breakdown layer. Owns no schema. For each "panel" (Students,
Attendance, Behaviour, Finance, UCAS, Apprenticeships, Exam Entries),
it returns a list of ``(label, count[, extra])`` rows suitable for a
simple two- or three-column table.

The CLI and GUI both consume :func:`build_panels`, which calls every
panel collector and gracefully degrades when a domain module is empty
or unavailable.
"""

from __future__ import annotations

import datetime as _dt
import logging
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Row:
    label: str
    count: int
    extra: str = ""


@dataclass
class Panel:
    name: str
    columns: tuple[str, str, str]   # (label-col, count-col, extra-col)
    rows: list[Row] = field(default_factory=list)
    note: str = ""                   # shown under the panel (e.g. "no data")
    total: int | None = None


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        logger.debug("Data dashboard panel failed", exc_info=True)
        return default


def _date_window(days: int) -> tuple[str, str]:
    today = _dt.date.today()
    return (today - _dt.timedelta(days=days)).isoformat(), today.isoformat()


# ── Panel collectors ───────────────────────────────────────────────

def panel_students_by_subject() -> Panel:
    panel = Panel("Students by subject", ("Subject", "Students", ""))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.students.students import students
        rows = students.list_students()
        counts: Counter[str] = Counter()
        for s in rows:
            for subj in s.subjects:
                counts[subj] += 1
        return rows, counts

    res = _safe(_go)
    if not res:
        panel.note = "No student records available."
        return panel
    rows, counts = res
    panel.total = len(rows)
    if not counts:
        panel.note = "No subjects recorded on student records."
        return panel
    for subject, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(subject, n))
    return panel


def panel_attendance_status(window_days: int) -> Panel:
    panel = Panel(f"Attendance status — last {window_days}d",
                  ("Status", "Marks", "Share"))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.academics.attendance import attendance
        df, dt_ = _date_window(window_days)
        return attendance.list_records(date_from=df, date_to=dt_)

    rows = _safe(_go)
    if rows is None:
        panel.note = "Attendance data unavailable."
        return panel
    if not rows:
        panel.note = "No attendance marks in window."
        return panel
    counts = Counter(r.status for r in rows)
    total = sum(counts.values())
    panel.total = total
    for status in ("Present", "Late", "Absent", "Authorised"):
        n = counts.get(status, 0)
        share = f"{(100 * n / total):.0f}%" if total else "—"
        panel.rows.append(Row(status, n, share))
    return panel


def panel_behaviour_by_category(window_days: int) -> Panel:
    panel = Panel(f"Behaviour by category — last {window_days}d",
                  ("Category", "Entries", "Points"))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.pastoral.behaviour import behaviour
        df, dt_ = _date_window(window_days)
        entries = behaviour.list_entries()
        return [e for e in entries if df <= (e.entry_date or "") <= dt_]

    entries = _safe(_go)
    if entries is None:
        panel.note = "Behaviour data unavailable."
        return panel
    if not entries:
        panel.note = "No behaviour entries in window."
        return panel
    by_cat: Counter[str] = Counter()
    points: dict[str, int] = {}
    for e in entries:
        cat = e.category or "(uncategorised)"
        by_cat[cat] += 1
        points[cat] = points.get(cat, 0) + (e.points or 0)
    panel.total = sum(by_cat.values())
    for cat, n in sorted(by_cat.items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(cat, n, str(points.get(cat, 0))))
    return panel


def panel_fees_status() -> Panel:
    panel = Panel("Fees status", ("Status", "Items", "Total balance"))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.finance.fees import fees
        return fees.list_views()

    views = _safe(_go)
    if views is None:
        panel.note = "Fee data unavailable."
        return panel
    if not views:
        panel.note = "No fee items on record."
        return panel
    counts: Counter[str] = Counter()
    balance: dict[str, float] = {}
    for v in views:
        status = getattr(v, "status", None) or getattr(v, "stored_status", None) \
                 or "Unknown"
        counts[status] += 1
        balance[status] = balance.get(status, 0.0) + (getattr(v, "balance", 0.0) or 0.0)
    panel.total = sum(counts.values())
    for status, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        bal = balance.get(status, 0.0)
        panel.rows.append(Row(status, n, f"£{bal:,.2f}"))
    return panel


def panel_bursaries_status() -> Panel:
    panel = Panel("Bursary applications", ("Status", "Applications", ""))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.finance.bursaries import bursaries
        return bursaries.list_applications()

    apps = _safe(_go)
    if apps is None:
        panel.note = "Bursary data unavailable."
        return panel
    if not apps:
        panel.note = "No bursary applications."
        return panel
    counts = Counter(a.status for a in apps)
    panel.total = sum(counts.values())
    for status, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(status, n))
    return panel


def panel_ucas_status() -> Panel:
    panel = Panel("UCAS applications", ("Status", "Applications", ""))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.progression.ucas import ucas
        return ucas.list_applications()

    apps = _safe(_go)
    if apps is None:
        panel.note = "UCAS data unavailable."
        return panel
    if not apps:
        panel.note = "No UCAS applications."
        return panel
    counts = Counter(a.status for a in apps)
    panel.total = sum(counts.values())
    for status, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(status, n))
    return panel


def panel_apprenticeships_status() -> Panel:
    panel = Panel("Apprenticeship applications", ("Status", "Applications", ""))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.progression.apprenticeships import apprenticeships
        return apprenticeships.list_applications()

    apps = _safe(_go)
    if apps is None:
        panel.note = "Apprenticeship data unavailable."
        return panel
    if not apps:
        panel.note = "No apprenticeship applications."
        return panel
    counts = Counter(a.status for a in apps)
    panel.total = sum(counts.values())
    for status, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(status, n))
    return panel


def panel_exam_entries_by_season() -> Panel:
    panel = Panel("Exam entries by season", ("Season / year", "Entries", "Active"))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.assessment.exam_entries import exam_entries
        return exam_entries.list_entries()

    entries = _safe(_go)
    if entries is None:
        panel.note = "Exam entries unavailable."
        return panel
    if not entries:
        panel.note = "No exam entries."
        return panel
    by_series: Counter[str] = Counter()
    active: Counter[str] = Counter()
    for e in entries:
        key = f"{e.season} {e.year}"
        by_series[key] += 1
        if e.status == "Entered":
            active[key] += 1
    panel.total = sum(by_series.values())
    for key, n in sorted(by_series.items(), key=lambda kv: kv[0]):
        panel.rows.append(Row(key, n, str(active.get(key, 0))))
    return panel


def panel_attendance_daily(window_days: int) -> Panel:
    """Day-by-day attendance trend (most recent first, truncated to window)."""
    panel = Panel(f"Daily attendance — last {window_days}d",
                  ("Date", "Marks", "% present/late"))

    def _go():
        from education_system.post_16.sixthform_system.modules.domain.academics.attendance import attendance
        df, dt_ = _date_window(window_days)
        return attendance.list_records(date_from=df, date_to=dt_)

    rows = _safe(_go)
    if rows is None:
        panel.note = "Attendance data unavailable."
        return panel
    if not rows:
        panel.note = "No attendance marks in window."
        return panel
    by_date: dict[str, list[int]] = {}
    for r in rows:
        stats = by_date.setdefault(r.date, [0, 0])
        stats[1] += 1
        if r.status in ("Present", "Late"):
            stats[0] += 1
    panel.total = sum(s[1] for s in by_date.values())
    for d in sorted(by_date.keys(), reverse=True):
        att, tot = by_date[d]
        pct = f"{(100 * att / tot):.0f}%" if tot else "—"
        panel.rows.append(Row(d, tot, pct))
    return panel


# ── Snapshot ───────────────────────────────────────────────────────

DEFAULT_WINDOW_DAYS = 30


@dataclass
class DataSnapshot:
    generated_at: str
    window_days: int
    panels: list[Panel]


def build_panels(*, window_days: int = DEFAULT_WINDOW_DAYS) -> DataSnapshot:
    panels = [
        panel_students_by_subject(),
        panel_attendance_status(window_days),
        panel_attendance_daily(window_days),
        panel_behaviour_by_category(window_days),
        panel_fees_status(),
        panel_bursaries_status(),
        panel_ucas_status(),
        panel_apprenticeships_status(),
        panel_exam_entries_by_season(),
    ]
    return DataSnapshot(
        generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        window_days=window_days,
        panels=panels,
    )
