"""KPI Dashboard for the Secondary School System.

Headline-metric layer. This module owns no schema: each metric is a
read-only roll-up over an existing domain module (students, attendance,
behaviour, fees, bursaries, UCAS, apprenticeships, exam entries, …).

The CLI and GUI both call :func:`snapshot` and render the resulting
:class:`Tile` list. Each tile carries a label, a formatted value, and
a short hint string for context.

Every individual metric is guarded by try/except — a missing dependency
or empty table never breaks the whole dashboard; the offending tile
just renders as ``—``.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Tile:
    label: str
    value: str
    hint: str


@dataclass
class Snapshot:
    generated_at: str
    window_days: int
    tiles: list[Tile]


# ── Helpers ────────────────────────────────────────────────────────

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        logger.debug("KPI metric failed", exc_info=True)
        return default


def _fmt_int(n: int | None) -> str:
    return f"{n:,}" if isinstance(n, int) else "—"


def _fmt_pct(p: float | None) -> str:
    return f"{p:.0f}%" if isinstance(p, (int, float)) else "—"


def _fmt_money(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"£{amount:,.2f}"


def _date_window(days: int) -> tuple[str, str]:
    today = _dt.date.today()
    start = today - _dt.timedelta(days=days)
    return start.isoformat(), today.isoformat()


# ── Individual metric collectors ───────────────────────────────────

def kpi_student_count() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.pastoral import _pupils_bridge as students
        return len(students.list_students())
    n = _safe(_go)
    return Tile("Students", _fmt_int(n), "On roll")


def kpi_staff_count() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.staff import staff
        return len(staff.list_staff())
    n = _safe(_go)
    return Tile("Staff", _fmt_int(n), "Active records")


def kpi_course_count() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.academics.courses import courses
        return len(courses.list_courses())
    n = _safe(_go)
    return Tile("Courses", _fmt_int(n), "Catalogue size")


def kpi_class_groups() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.academics.class_groups import class_groups
        return len(class_groups.list_groups())
    n = _safe(_go)
    return Tile("Class groups", _fmt_int(n), "Teaching cohorts")


def kpi_today_attendance() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.academics.attendance import attendance
        today = _dt.date.today().isoformat()
        rows = attendance.list_records(date=today)
        if not rows:
            return None
        attending = sum(1 for r in rows if r.status in ("Present", "Late"))
        return (attending, len(rows))
    res = _safe(_go)
    if not res:
        return Tile("Today's attendance", "—", "No marks recorded today")
    attending, total = res
    pct = 100.0 * attending / total if total else 0
    return Tile("Today's attendance", _fmt_pct(pct),
                f"{attending}/{total} present or late")


def kpi_window_attendance(window_days: int) -> Tile:
    def _go():
        from education_system.systems.secondary.domain.academics.attendance import attendance
        df, dt_ = _date_window(window_days)
        rows = attendance.list_records(date_from=df, date_to=dt_)
        if not rows:
            return None
        attending = sum(1 for r in rows if r.status in ("Present", "Late"))
        return (attending, len(rows))
    res = _safe(_go)
    if not res:
        return Tile(f"{window_days}d attendance", "—", "No marks in window")
    attending, total = res
    pct = 100.0 * attending / total if total else 0
    return Tile(f"{window_days}d attendance", _fmt_pct(pct),
                f"{attending:,}/{total:,} marks")


def kpi_recent_behaviour(window_days: int) -> Tile:
    def _go():
        from education_system.systems.secondary.domain.pastoral.behaviour import behaviour
        df, dt_ = _date_window(window_days)
        rows = behaviour.list_entries() if hasattr(behaviour, "list_entries") else []
        # filter by date_from/date_to client-side: signature varies
        return [r for r in rows if df <= (r.entry_date or "") <= dt_]
    rows = _safe(_go)
    n = len(rows) if isinstance(rows, list) else None
    negatives = (sum(1 for r in rows if r.entry_type and "neg" in r.entry_type.lower())
                 if isinstance(rows, list) else None)
    hint = f"{negatives} negative" if negatives is not None else "Logged incidents"
    return Tile(f"{window_days}d behaviour", _fmt_int(n), hint)


def kpi_outstanding_fees() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.finance.fees import fees
        views = fees.list_views()
        outstanding = sum(max(0.0, getattr(v, "balance", 0.0) or 0.0)
                          for v in views)
        return outstanding
    amt = _safe(_go)
    return Tile("Outstanding fees", _fmt_money(amt), "Unpaid balance")


def kpi_bursaries_submitted() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.finance.bursaries import bursaries
        apps = bursaries.list_applications()
        pending = sum(1 for a in apps if a.status in ("Submitted", "Under review",
                                                       "Approved"))
        return pending
    n = _safe(_go)
    return Tile("Bursary apps", _fmt_int(n), "Submitted or under review")


def kpi_ucas_submitted() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.progression.ucas import ucas
        apps = ucas.list_applications()
        submitted = sum(1 for a in apps
                        if a.status in ("Submitted", "Replied", "Confirmed", "Clearing"))
        return submitted
    n = _safe(_go)
    return Tile("UCAS submitted", _fmt_int(n), "Applications progressing")


def kpi_apprenticeships_active() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.progression.apprenticeships import apprenticeships
        apps = apprenticeships.list_applications()
        active = sum(1 for a in apps
                     if a.status not in ("Offered – Accepted", "Rejected", "Withdrawn"))
        return active
    n = _safe(_go)
    return Tile("Apprenticeships", _fmt_int(n), "Open applications")


def kpi_exam_entries() -> Tile:
    def _go():
        from education_system.systems.secondary.domain.assessment.exam_entries import exam_entries
        entries = exam_entries.list_entries()
        active = sum(1 for e in entries if e.status == "Entered")
        return active
    n = _safe(_go)
    return Tile("Exam entries", _fmt_int(n), "Currently entered")


def kpi_attendance_at_risk(window_days: int, threshold: float) -> Tile:
    """Count students whose attending-rate over the window is below the threshold."""
    def _go():
        from education_system.systems.secondary.domain.academics.attendance import attendance
        from education_system.systems.secondary.domain.pastoral import _pupils_bridge as students
        df, dt_ = _date_window(window_days)
        rows = attendance.list_records(date_from=df, date_to=dt_)
        by_student: dict[str, list[int]] = {}
        for r in rows:
            stats = by_student.setdefault(r.student_id, [0, 0])
            stats[1] += 1
            if r.status in ("Present", "Late"):
                stats[0] += 1
        at_risk = 0
        for _, (att, tot) in by_student.items():
            if tot == 0:
                continue
            if (100.0 * att / tot) < threshold:
                at_risk += 1
        return at_risk
    n = _safe(_go)
    return Tile("At-risk attendance", _fmt_int(n),
                f"Below {threshold:.0f}% in {window_days}d")


# ── Snapshot ───────────────────────────────────────────────────────

DEFAULT_WINDOW_DAYS = 30
DEFAULT_THRESHOLD = 90.0


def snapshot(*,
             window_days: int = DEFAULT_WINDOW_DAYS,
             threshold_pct: float = DEFAULT_THRESHOLD) -> Snapshot:
    """Collect every KPI tile. Each tile is best-effort: failures show '—'."""
    tiles = [
        kpi_student_count(),
        kpi_staff_count(),
        kpi_course_count(),
        kpi_class_groups(),
        kpi_today_attendance(),
        kpi_window_attendance(window_days),
        kpi_attendance_at_risk(window_days, threshold_pct),
        kpi_recent_behaviour(window_days),
        kpi_outstanding_fees(),
        kpi_bursaries_submitted(),
        kpi_ucas_submitted(),
        kpi_apprenticeships_active(),
        kpi_exam_entries(),
    ]
    return Snapshot(
        generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        window_days=window_days,
        tiles=tiles,
    )
