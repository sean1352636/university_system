"""Data Dashboard for the Primary School System.

Tabular breakdown layer. Owns no schema. For each "panel" (Students,
Pupils, Attendance, Behaviour, Dinner money, Pupil Premium, SEND),
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

def panel_pupils_by_year_group() -> Panel:
    panel = Panel("Pupils by year group", ("Year group", "Pupils", "SEND"))

    from education_system.systems.primary.domain.learners.pupils import pupils

    rows = _safe(pupils.list_pupils)
    if rows is None:
        panel.note = "Pupil records unavailable."
        return panel
    if not rows:
        panel.note = "No pupils on roll."
        return panel
    counts: Counter[str] = Counter(p.year_group for p in rows)
    sen: Counter[str] = Counter(p.year_group for p in rows if p.send_status == "yes")
    panel.total = len(rows)
    order = {y: i for i, y in enumerate(pupils.YEAR_GROUPS)}
    for yg in sorted(counts, key=lambda y: (order.get(y, 99), y)):
        label = "Reception" if yg == "R" else f"Year {yg}"
        panel.rows.append(Row(label, counts[yg], str(sen.get(yg, 0))))
    return panel


def panel_attendance_status(window_days: int) -> Panel:
    panel = Panel(f"Attendance status — last {window_days}d",
                  ("Status", "Marks", "Share"))

    def _go():
        from education_system.systems.primary.domain.academics.attendance import attendance
        df, dt_ = _date_window(window_days)
        return attendance.list_records(date_from=df, date_to=dt_)

    rows = _safe(_go)
    if rows is None:
        panel.note = "Attendance data unavailable."
        return panel
    if not rows:
        panel.note = "No attendance marks in window."
        return panel
    labels = {"present": "Present", "late": "Late",
              "auth_absent": "Authorised absence",
              "unauth_absent": "Unauthorised absence", "excluded": "Excluded"}
    counts = Counter(labels.get(r.category, "Other") for r in rows if r.is_possible)
    total = sum(counts.values())
    panel.total = total
    for status in (*labels.values(), "Other"):
        n = counts.get(status, 0)
        if not n and status == "Other":
            continue
        share = f"{(100 * n / total):.0f}%" if total else "—"
        panel.rows.append(Row(status, n, share))
    return panel


def panel_behaviour_by_category(window_days: int) -> Panel:
    panel = Panel(f"Behaviour by type — last {window_days}d",
                  ("Type", "Incidents", "Points"))

    def _go():
        from education_system.systems.primary.domain.pastoral.behaviour import behaviour
        df, dt_ = _date_window(window_days)
        return behaviour.list_incidents(date_from=df, date_to=dt_)

    entries = _safe(_go)
    if entries is None:
        panel.note = "Behaviour data unavailable."
        return panel
    if not entries:
        panel.note = "No behaviour incidents in window."
        return panel
    by_cat: Counter[str] = Counter()
    points: dict[str, int] = {}
    for e in entries:
        cat = e.incident_type or "(untyped)"
        by_cat[cat] += 1
        points[cat] = points.get(cat, 0) + (e.points or 0)
    panel.total = sum(by_cat.values())
    for cat, n in sorted(by_cat.items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(cat, n, str(points.get(cat, 0))))
    return panel


def panel_dinner_money() -> Panel:
    panel = Panel("Dinner money balances", ("Balance", "Pupils", "Total"))

    def _go():
        from education_system.systems.primary.domain.finance.dinner_money import dinner_money
        return dinner_money.balances()

    rows = _safe(_go)
    if rows is None:
        panel.note = "Dinner money data unavailable."
        return panel
    if not rows:
        panel.note = "No dinner money accounts."
        return panel
    groups = {"In debt": [], "Zero": [], "In credit": []}
    for _p, bal in rows:
        groups["In debt" if bal < 0 else "Zero" if bal == 0 else "In credit"].append(bal)
    panel.total = len(rows)
    for label, bals in groups.items():
        if bals:
            panel.rows.append(Row(label, len(bals), f"{'-' if sum(bals) < 0 else ''}£{abs(sum(bals)) / 100:,.2f}"))
    return panel


def panel_pupil_premium() -> Panel:
    panel = Panel("Pupil Premium by category", ("Category", "Pupils", ""))

    def _go():
        from education_system.systems.primary.domain.finance.pupil_premium import pupil_premium
        return pupil_premium.cohort_summary()

    s = _safe(_go)
    if s is None:
        panel.note = "Pupil Premium data unavailable."
        return panel
    if not s["total"]:
        panel.note = "No Pupil Premium records."
        return panel
    panel.total = s["total"]
    for cat, n in sorted(s["by_category"].items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(cat or "—", n))
    return panel


def panel_send_by_stage() -> Panel:
    panel = Panel("SEND register by stage", ("Provision stage", "Pupils", ""))

    def _go():
        from education_system.systems.primary.domain.pastoral.send import send
        return send.cohort_summary()

    s = _safe(_go)
    if s is None:
        panel.note = "SEND data unavailable."
        return panel
    if not s["total"]:
        panel.note = "No pupils on the SEND register."
        return panel
    panel.total = s["total"]
    for stage, n in sorted(s["by_stage"].items(), key=lambda kv: (-kv[1], kv[0])):
        panel.rows.append(Row(stage or "—", n))
    return panel


def panel_attendance_daily(window_days: int) -> Panel:
    """Day-by-day attendance trend (most recent first, truncated to window)."""
    panel = Panel(f"Daily attendance — last {window_days}d",
                  ("Date", "Marks", "% present/late"))

    def _go():
        from education_system.systems.primary.domain.academics.attendance import attendance
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
        if not r.is_possible:
            continue
        stats = by_date.setdefault(r.date, [0, 0])
        stats[1] += 1
        if r.is_attending:
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
        panel_pupils_by_year_group(),
        panel_attendance_status(window_days),
        panel_attendance_daily(window_days),
        panel_behaviour_by_category(window_days),
        panel_dinner_money(),
        panel_pupil_premium(),
        panel_send_by_stage(),
    ]
    return DataSnapshot(
        generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        window_days=window_days,
        panels=panels,
    )
