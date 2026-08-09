"""Mobile Dashboard aggregation layer for the Sixth Form System.

A compact "home-screen" feed designed for narrow-width / on-the-go
viewing: today's headline tiles (announcements, calendar, attendance
status, open progress alerts, target reminders) plus a 'next actions'
list. Pulls live from the relevant domain modules — no DB of its own.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as _date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Tile:
    key: str
    title: str
    value: str
    subtitle: str = ""
    severity: str = "info"  # info | ok | warn | alert


@dataclass
class FeedItem:
    kind: str       # 'announcement' | 'event' | 'target' | 'alert' | 'review'
    when: str       # iso date or label
    title: str
    detail: str = ""
    severity: str = "info"


@dataclass
class MobileDashboard:
    generated_on: str
    tiles: list[Tile] = field(default_factory=list)
    today_events: list[FeedItem] = field(default_factory=list)
    upcoming_events: list[FeedItem] = field(default_factory=list)
    announcements: list[FeedItem] = field(default_factory=list)
    overdue_targets: list[FeedItem] = field(default_factory=list)
    high_risk_students: list[FeedItem] = field(default_factory=list)
    open_alerts: list[FeedItem] = field(default_factory=list)


# ── Safe-import helpers ──────────────────────────────────────────
# Other domain modules may not yet be fully wired up. The dashboard
# must degrade gracefully — a missing/broken module loses its tile,
# it doesn't blow up the whole view.

def _safe(call):
    """Call ``call()`` and swallow any exception, returning None."""
    try:
        return call()
    except Exception as e:
        logger.debug("mobile_dashboard: safe-call failed: %s", e)
        return None


# ── Builders ─────────────────────────────────────────────────────

def _student_count() -> int | None:
    def _():
        from education_system.systems.sixth_form.domain.learners.students import (
            students,
        )
        return len(students.list_students())
    return _safe(_)


def _today_attendance() -> tuple[int, int, float | None] | None:
    """Return (records_today, attending_today, pct) for today, or None."""
    def _():
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance,
        )
        today = _date.today().isoformat()
        rows = attendance.list_records(date=today)
        total = len(rows)
        attending = sum(1 for r in rows
                         if r.status in attendance.ATTENDING_STATUSES)
        pct = round(100.0 * attending / total, 1) if total else None
        return total, attending, pct
    return _safe(_)


def _progress_snapshot() -> tuple[int, int, int] | None:
    """Return (open_targets, overdue_open, high_risk_active)."""
    def _():
        from education_system.systems.sixth_form.domain.operations.reporting.progress import (
            progress,
        )
        s = progress.summary()
        return (s.open_targets, s.overdue_open_targets,
                s.students_at_high_risk)
    return _safe(_)


def _announcement_feed(limit: int = 5) -> list[FeedItem]:
    def _():
        from education_system.systems.sixth_form.domain.operations.communications.announcements import (
            announcements,
        )
        rows = announcements.list_announcements(status="Published") \
            if hasattr(announcements, "list_announcements") else []
        items: list[FeedItem] = []
        for a in rows[:limit]:
            sev = "alert" if getattr(a, "priority", 0) and a.priority >= 3 \
                else "info"
            items.append(FeedItem(
                kind="announcement",
                when=getattr(a, "published_at", "") or getattr(
                    a, "created_at", "") or "",
                title=getattr(a, "title", "(announcement)"),
                detail=getattr(a, "body", "")[:140] if getattr(
                    a, "body", None) else "",
                severity=sev,
            ))
        return items
    return _safe(_) or []


def _today_and_upcoming_events(
    upcoming_days: int = 7,
) -> tuple[list[FeedItem], list[FeedItem]]:
    def _():
        from education_system.systems.sixth_form.domain.academics.calendar import (
            calendar,
        )
        today_iso = _date.today().isoformat()
        today_evs = calendar.events_on(today_iso) \
            if hasattr(calendar, "events_on") else []
        # Upcoming via list_events between tomorrow and +N days.
        end_iso = (_date.today() + timedelta(days=upcoming_days)).isoformat()
        try:
            upcoming = calendar.list_events(
                date_from=(_date.today() + timedelta(days=1)).isoformat(),
                date_to=end_iso,
            )
        except TypeError:
            upcoming = []
        return today_evs, upcoming
    res = _safe(_)
    if res is None:
        return [], []
    today_evs, upcoming = res

    def _to_item(e) -> FeedItem:
        return FeedItem(
            kind="event",
            when=getattr(e, "start_date", "") or getattr(e, "date", "") or "",
            title=getattr(e, "title", "(event)"),
            detail=getattr(e, "location", "") or "",
            severity="info",
        )
    return ([_to_item(e) for e in today_evs],
            [_to_item(e) for e in upcoming])


def _overdue_target_feed(limit: int = 10) -> list[FeedItem]:
    def _():
        from education_system.systems.sixth_form.domain.operations.reporting.progress import (
            progress,
        )
        today = _date.today().isoformat()
        rows = progress.list_targets(open_only=True, due_before=today)
        rows = [t for t in rows if t.due_date and t.due_date < today]
        # Map review→student for nicer titles.
        review_to_student: dict[int, str] = {}
        for r in progress.list_reviews():
            review_to_student[r.review_id] = r.student_id
        try:
            from education_system.systems.sixth_form.domain.learners.students import (
                students,
            )
            names = {s.student_id: s.full_name
                      for s in students.list_students()}
        except Exception:
            names = {}
        out: list[FeedItem] = []
        for t in rows[:limit]:
            sid = review_to_student.get(t.review_id, "?")
            who = names.get(sid, sid)
            out.append(FeedItem(
                kind="target",
                when=t.due_date or "",
                title=f"{who} — {t.area}",
                detail=t.description[:120],
                severity="warn",
            ))
        return out
    return _safe(_) or []


def _high_risk_feed(limit: int = 10) -> list[FeedItem]:
    def _():
        from education_system.systems.sixth_form.domain.operations.reporting.progress_dashboard import (
            progress_dashboard,
        )
        rows = progress_dashboard.students_at_risk()
        out: list[FeedItem] = []
        for r in rows[:limit]:
            out.append(FeedItem(
                kind="review",
                when=r.latest_date or "",
                title=f"{r.full_name} ({r.student_id})",
                detail=f"{r.risk} risk · {r.overall or '—'}",
                severity="alert" if r.risk == "Critical" else "warn",
            ))
        return out
    return _safe(_) or []


def _open_alerts_feed(limit: int = 10) -> list[FeedItem]:
    def _():
        from education_system.systems.sixth_form.domain.assessment.early_warning import (
            early_warning,
        )
        rows = early_warning.list_alerts(status="Open") \
            if hasattr(early_warning, "list_alerts") else []
        out: list[FeedItem] = []
        for a in rows[:limit]:
            out.append(FeedItem(
                kind="alert",
                when=getattr(a, "raised_on", "") or getattr(
                    a, "created_at", "") or "",
                title=getattr(a, "title", None)
                       or getattr(a, "trigger", "(alert)"),
                detail=getattr(a, "summary", "")
                        or getattr(a, "detail", "")
                        or "",
                severity="alert",
            ))
        return out
    return _safe(_) or []


# ── Public entry point ──────────────────────────────────────────

def build_dashboard() -> MobileDashboard:
    today = _date.today().isoformat()
    d = MobileDashboard(generated_on=today)

    # Tiles ────────────────────────────────────────────────────
    students_n = _student_count()
    if students_n is not None:
        d.tiles.append(Tile("students", "Students",
                              str(students_n), "in cohort", "info"))

    att = _today_attendance()
    if att is not None:
        total, attending, pct = att
        if total == 0:
            d.tiles.append(Tile("attendance", "Today's Attendance",
                                  "—", "no register today", "info"))
        else:
            sev = "ok" if (pct or 0) >= 95.0 \
                else "warn" if (pct or 0) >= 85.0 \
                else "alert"
            d.tiles.append(Tile(
                "attendance", "Today's Attendance",
                f"{pct:.1f}%",
                f"{attending}/{total} attending", sev))

    prog = _progress_snapshot()
    if prog is not None:
        open_n, overdue_n, hr_n = prog
        d.tiles.append(Tile(
            "open_targets", "Open Targets", str(open_n),
            f"{overdue_n} overdue",
            "alert" if overdue_n else "ok"))
        d.tiles.append(Tile(
            "high_risk", "High/Critical Risk", str(hr_n),
            "active reviews",
            "alert" if hr_n else "ok"))

    today_evs, upcoming = _today_and_upcoming_events()
    d.today_events = today_evs
    d.upcoming_events = upcoming
    d.tiles.append(Tile(
        "today_events", "Today's Events", str(len(today_evs)),
        f"{len(upcoming)} in next 7 days", "info"))

    # Feeds ────────────────────────────────────────────────────
    d.announcements = _announcement_feed()
    d.overdue_targets = _overdue_target_feed()
    d.high_risk_students = _high_risk_feed()
    d.open_alerts = _open_alerts_feed()

    return d
