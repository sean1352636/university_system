"""KPI Dashboard for the Primary School System.

Headline-metric layer. This module owns no schema: each metric is a
read-only roll-up over an existing domain module (students, attendance,
behaviour, dinner money, Pupil Premium, SEND, …).

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
        from education_system.systems.primary.domain import _pupils_bridge as students
        return len(students.list_students())
    n = _safe(_go)
    return Tile("Students", _fmt_int(n), "On roll")


def kpi_staff_count() -> Tile:
    def _go():
        from education_system.systems.primary.domain.staff import staff
        return len(staff.list_staff())
    n = _safe(_go)
    return Tile("Staff", _fmt_int(n), "Active records")


def kpi_subject_count() -> Tile:
    def _go():
        from education_system.systems.primary.domain.academics.subjects import subjects
        return subjects.counts()["active"]
    n = _safe(_go)
    return Tile("Subjects", _fmt_int(n), "Active in the curriculum")


def kpi_classes() -> Tile:
    def _go():
        from education_system.systems.primary.domain.academics.classes import classes
        return classes.counts()["active"]
    n = _safe(_go)
    return Tile("Classes", _fmt_int(n), "Active classes")


def kpi_today_attendance() -> Tile:
    def _go():
        from education_system.systems.primary.domain.academics.attendance import attendance
        today = _dt.date.today().isoformat()
        rows = [r for r in attendance.list_records(date=today) if r.is_possible]
        if not rows:
            return None
        attending = sum(1 for r in rows if r.is_attending)
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
        from education_system.systems.primary.domain.academics.attendance import attendance
        df, dt_ = _date_window(window_days)
        rows = [r for r in attendance.list_records(date_from=df, date_to=dt_)
                if r.is_possible]
        if not rows:
            return None
        attending = sum(1 for r in rows if r.is_attending)
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
        from education_system.systems.primary.domain.pastoral.behaviour import behaviour
        df, dt_ = _date_window(window_days)
        return behaviour.list_incidents(date_from=df, date_to=dt_)
    rows = _safe(_go)
    n = len(rows) if isinstance(rows, list) else None
    negatives = (sum(1 for r in rows if r.polarity == "negative")
                 if isinstance(rows, list) else None)
    hint = f"{negatives} negative" if negatives is not None else "Logged incidents"
    return Tile(f"{window_days}d behaviour", _fmt_int(n), hint)


def kpi_dinner_money_owed() -> Tile:
    def _go():
        from education_system.systems.primary.domain.finance.dinner_money import dinner_money
        owed = dinner_money.balances(owing_only=True)
        return sum(-bal for _p, bal in owed if bal < 0) / 100.0, len(owed)
    res = _safe(_go)
    amt, n = res if res else (None, None)
    hint = f"{n} pupil(s) in debt" if n is not None else "Dinner money debt"
    return Tile("Dinner money owed", _fmt_money(amt), hint)


def kpi_pupil_premium() -> Tile:
    def _go():
        from education_system.systems.primary.domain.finance.pupil_premium import pupil_premium
        return pupil_premium.cohort_summary()["total"]
    n = _safe(_go)
    return Tile("Pupil Premium", _fmt_int(n), "Eligible pupils on record")


def kpi_send_pupils() -> Tile:
    def _go():
        from education_system.systems.primary.domain.pastoral.send import send
        s = send.cohort_summary()
        return s["total"], s["ehcp_count"]
    res = _safe(_go)
    n, ehcp = res if res else (None, None)
    hint = f"{ehcp} with an EHCP" if ehcp is not None else "SEN register"
    return Tile("SEND pupils", _fmt_int(n), hint)


def kpi_attendance_at_risk(window_days: int, threshold: float) -> Tile:
    """Count students whose attending-rate over the window is below the threshold."""
    def _go():
        from education_system.systems.primary.domain.academics.attendance import attendance
        from education_system.systems.primary.domain import _pupils_bridge as students
        df, dt_ = _date_window(window_days)
        rows = attendance.list_records(date_from=df, date_to=dt_)
        by_student: dict[str, list[int]] = {}
        for r in rows:
            if not r.is_possible:
                continue
            stats = by_student.setdefault(r.pupil_id, [0, 0])
            stats[1] += 1
            if r.is_attending:
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
        kpi_subject_count(),
        kpi_classes(),
        kpi_today_attendance(),
        kpi_window_attendance(window_days),
        kpi_attendance_at_risk(window_days, threshold_pct),
        kpi_recent_behaviour(window_days),
        kpi_dinner_money_owed(),
        kpi_pupil_premium(),
        kpi_send_pupils(),
    ]
    return Snapshot(
        generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        window_days=window_days,
        tiles=tiles,
    )
