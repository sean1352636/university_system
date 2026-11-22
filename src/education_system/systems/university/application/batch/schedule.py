"""Scheduled batch work.

* **Watched folders at a set time** — a watched folder with ``run_at``
  ("HH:MM") is imported once a day after that time by the background
  worker (``infrastructure/batch_scheduler``); without one it runs only
  when someone presses Run, as before.
* **Scheduled reports** — a batch report (success rates, error analysis,
  performance, comprehensive, enrolment statistics) e-mailed daily, weekly
  or monthly to the addresses given, built with the owner's rights.
* :func:`scheduled_tasks` lists both with when each runs next.

Functions taking a connection do not commit; the caller does. The
``run_due_*`` functions manage their own connections.
"""

from __future__ import annotations

import re
from contextlib import closing
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.schemas import (
    batch_jobs_schema as schema,
)

REPORTS = {"success": "Batch success rates", "errors": "Batch error analysis",
           "performance": "Batch performance", "comprehensive": "Comprehensive batch report",
           "statistics": "Enrolment statistics"}
FREQUENCIES = {"daily": 1, "weekly": 7, "monthly": 30}
_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ADMIN_ROLES = ("admin", "administrator", "superadmin")


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(db_path, row_factory=False)
    schema.apply_to_connection(conn)
    return conn


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


# ── watched folders at a time ───────────────────────────────────────────


def set_watch_time(conn, viewer, watch_id, run_at) -> None:
    """``run_at`` "HH:MM" for a daily run, or blank for manual only."""
    from education_system.systems.university.application.batch import jobs as batch_jobs
    schema.apply_to_connection(conn)
    batch_jobs._own_watch(conn, viewer, watch_id)
    value = str(run_at or "").strip()
    if value:
        m = _TIME.match(value)
        if not m:
            raise ValueError("Give the time as HH:MM (24-hour)")
        value = f"{int(m.group(1)):02d}:{m.group(2)}"
    conn.execute("UPDATE batch_watch_folders SET run_at = ? WHERE id = ?",
                 (value or None, watch_id))


def _due_watches(conn, now):
    today, clock = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
    return _dicts(conn.execute(
        "SELECT * FROM batch_watch_folders WHERE active = 1 AND run_at IS NOT NULL AND "
        "run_at <= ? AND COALESCE(last_scheduled_on, '') < ?", (clock, today)))


def run_due_watches(now=None, *, db_path=None, auth_db_path=None) -> list:
    """Run every watched folder whose time has come today (once a day)."""
    from education_system.systems.university.application.batch import imports as batch_imports
    now = now or datetime.now()
    with closing(_connect(db_path)) as conn:
        due = _due_watches(conn, now)
        for w in due:                      # claim first, so two workers never double-run
            conn.execute("UPDATE batch_watch_folders SET last_scheduled_on = ? WHERE id = ?",
                         (now.strftime("%Y-%m-%d"), w["id"]))
        conn.commit()
    ran = []
    for w in due:
        try:
            result = batch_imports._run_watch(w, db_path, auth_db_path)
        except Exception as exc:
            result = f"failed: {exc}"
        with closing(_connect(db_path)) as conn:
            conn.execute("UPDATE batch_watch_folders SET last_run_at = datetime('now'), "
                         "last_result = ? WHERE id = ?", (f"scheduled: {result}", w["id"]))
            conn.commit()
        ran.append((w["id"], result))
    return ran


# ── scheduled reports ───────────────────────────────────────────────────


def _recipients(text) -> list[str]:
    found = [a.strip() for a in re.split(r"[,;\s]+", str(text or "")) if a.strip()]
    bad = [a for a in found if not _EMAIL.match(a)]
    if bad:
        raise ValueError(f"Not an e-mail address: {', '.join(bad)}")
    if not found:
        raise ValueError("Give at least one e-mail address")
    return found


def add_report_schedule(conn, viewer, report, frequency, recipients) -> int:
    schema.apply_to_connection(conn)
    if report not in REPORTS:
        raise ValueError(f"Report must be one of {', '.join(REPORTS)}")
    if frequency not in FREQUENCIES:
        raise ValueError("Frequency must be daily, weekly or monthly")
    if report == "statistics":
        if not (viewer.can_view_all or viewer.can_export):
            raise ValueError("You do not have permission to see university-wide statistics")
    elif not (viewer.can_update or viewer.can_mark or viewer.can_manage_users):
        raise ValueError("Batch reports are for staff who run batch work")
    return int(conn.execute(
        "INSERT INTO batch_report_schedules (owner, report, frequency, recipients) VALUES "
        "(?, ?, ?, ?)", (viewer.username, report, frequency,
                         ", ".join(_recipients(recipients)))).lastrowid)


def report_schedules(conn, viewer) -> list[dict]:
    schema.apply_to_connection(conn)
    if viewer.role in ADMIN_ROLES:
        return _dicts(conn.execute("SELECT * FROM batch_report_schedules ORDER BY id"))
    return _dicts(conn.execute("SELECT * FROM batch_report_schedules WHERE owner = ? "
                               "ORDER BY id", (viewer.username,)))


def _own(conn, viewer, schedule_id):
    row = conn.execute("SELECT owner FROM batch_report_schedules WHERE id = ?",
                       (schedule_id,)).fetchone()
    if not row:
        raise ValueError("No such scheduled report")
    if row[0] != viewer.username and viewer.role not in ADMIN_ROLES:
        raise ValueError("Only its owner (or an admin) can change this")


def set_report_active(conn, viewer, schedule_id, active) -> None:
    schema.apply_to_connection(conn)
    _own(conn, viewer, schedule_id)
    conn.execute("UPDATE batch_report_schedules SET active = ? WHERE id = ?",
                 (int(bool(active)), schedule_id))


def remove_report_schedule(conn, viewer, schedule_id) -> None:
    schema.apply_to_connection(conn)
    _own(conn, viewer, schedule_id)
    conn.execute("DELETE FROM batch_report_schedules WHERE id = ?", (schedule_id,))


def build_report(conn, viewer, report, db_path=None) -> dict:
    from education_system.systems.university.application.batch import reports as batch_reports
    if report == "success":
        return batch_reports.success_rates(conn, viewer)
    if report == "errors":
        return batch_reports.error_analysis(conn, viewer)
    if report == "performance":
        return batch_reports.performance(conn, viewer)
    if report == "comprehensive":
        return batch_reports.comprehensive(conn, viewer, db_path=db_path)
    if report == "statistics":
        return batch_reports.enrolment_statistics(conn, viewer)
    raise ValueError(f"Unknown report {report!r}")


def run_due_reports(now=None, *, db_path=None) -> list[tuple]:
    """E-mails for every scheduled report that is due; marks them sent.
    Returns ``(address, subject, body)`` tuples to send."""
    from education_system.systems.university.application.batch import reports as batch_reports
    from education_system.systems.university.application.students.search_saved import (
        owner_viewer,
    )
    now = now or datetime.now()
    emails = []
    with closing(_connect(db_path)) as conn:
        for s in _dicts(conn.execute("SELECT * FROM batch_report_schedules WHERE active = 1")):
            last = s["last_sent_at"]
            if last and datetime.fromisoformat(last[:19]) > now - timedelta(
                    days=FREQUENCIES[s["frequency"]]) + timedelta(minutes=5):
                continue
            viewer = owner_viewer(conn, s["owner"])
            try:
                text = batch_reports.as_text(build_report(conn, viewer, s["report"], db_path))
            except ValueError as exc:
                text = f"The report could not be built: {exc}"
            subject = f"{REPORTS[s['report']]} ({s['frequency']}), {now:%d %B %Y}"
            emails += [(a, subject, text) for a in _recipients(s["recipients"])]
            conn.execute("UPDATE batch_report_schedules SET last_sent_at = ? WHERE id = ?",
                         (now.isoformat(timespec="seconds"), s["id"]))
        conn.commit()
    return emails


# ── everything scheduled ────────────────────────────────────────────────


def _next_watch(w, now):
    if not w["active"] or not w["run_at"]:
        return "when someone presses Run" if w["active"] else "paused"
    hour, minute = map(int, w["run_at"].split(":"))
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if w["last_scheduled_on"] == now.strftime("%Y-%m-%d"):
        at += timedelta(days=1)            # already run today
    elif at < now:
        at = now                           # due now; the worker checks every minute
    return at.strftime("%Y-%m-%d %H:%M")


def _next_report(s, now):
    if not s["active"]:
        return "paused"
    if not s["last_sent_at"]:
        return "within the next few minutes"
    due = datetime.fromisoformat(s["last_sent_at"][:19]) + timedelta(
        days=FREQUENCIES[s["frequency"]])
    return max(due, now).strftime("%Y-%m-%d %H:%M")


def scheduled_tasks(conn, viewer, now=None) -> list[dict]:
    from education_system.systems.university.application.batch import jobs as batch_jobs
    now = now or datetime.now()
    out = []
    for w in batch_jobs.watches(conn, viewer):
        out.append({"type": "watched folder", "id": w["id"], "owner": w["owner"],
                    "what": f"import {w['kind']} from {w['folder']}",
                    "when": f"daily at {w['run_at']}" if w.get("run_at") else "manual",
                    "next": _next_watch(w, now), "last": w["last_run_at"],
                    "result": w["last_result"]})
    for s in report_schedules(conn, viewer):
        out.append({"type": "report", "id": s["id"], "owner": s["owner"],
                    "what": f"{REPORTS[s['report']]} to {s['recipients']}",
                    "when": s["frequency"], "next": _next_report(s, now),
                    "last": s["last_sent_at"], "result": None})
    return out
