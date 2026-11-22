"""Scheduled Document Manager reports.

A schedule names one of the Document Manager's standard reports, how often
it goes out (daily, weekly, monthly) and the e-mail addresses it goes to.
The university batch scheduler (``infrastructure/batch/scheduler.run_once``)
calls :func:`run_due_reports` every minute; "Run Now" in the Scheduled
Reports window calls :func:`run_schedule`. Both build the report from the
live document tables at the moment they run and return
``(address, subject, body)`` tuples for the caller to send after commit.

Functions taking a connection do not commit; the caller does.
:func:`run_due_reports` manages its own connection.
"""

from __future__ import annotations

import re
from contextlib import closing
from datetime import datetime, timedelta

REPORTS = {
    "compliance": "Compliance Report",
    "status": "Document Status Report",
    "expiry": "Expiry Report (next 30 days)",
    "pending": "Pending Documents",
    "monthly": "Monthly Summary",
    "statistics": "Document Statistics",
}
FREQUENCIES = {"daily": 1, "weekly": 7, "monthly": 30}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_report_schedules (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    recipients TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    owner TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,
    last_run_at TEXT,
    last_result TEXT
)
"""


def ensure_schema(conn) -> None:
    conn.execute(_SCHEMA)


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(db_path, row_factory=False)
    ensure_schema(conn)
    return conn


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def parse_recipients(text) -> list[str]:
    found = [a.strip() for a in re.split(r"[,;\s]+", str(text or "")) if a.strip()]
    bad = [a for a in found if not _EMAIL.match(a)]
    if bad:
        raise ValueError(f"Not an e-mail address: {', '.join(bad)}")
    if not found:
        raise ValueError("Give at least one e-mail address")
    return found


def _validate(name, report_type, frequency, recipients) -> tuple:
    name = str(name or "").strip()
    if not name:
        raise ValueError("Give the schedule a name")
    if report_type not in REPORTS:
        raise ValueError(f"Report must be one of {', '.join(REPORTS)}")
    if frequency not in FREQUENCIES:
        raise ValueError("Frequency must be daily, weekly or monthly")
    return name, report_type, frequency, ", ".join(parse_recipients(recipients))


# ── schedules ───────────────────────────────────────────────────────────


def list_schedules(conn) -> list[dict]:
    ensure_schema(conn)
    return _dicts(conn.execute(
        "SELECT * FROM document_report_schedules ORDER BY schedule_id"))


def get_schedule(conn, schedule_id) -> dict:
    ensure_schema(conn)
    rows = _dicts(conn.execute(
        "SELECT * FROM document_report_schedules WHERE schedule_id = ?", (schedule_id,)))
    if not rows:
        raise ValueError("No such scheduled report")
    return rows[0]


def add_schedule(conn, owner, name, report_type, frequency, recipients, active=True) -> int:
    ensure_schema(conn)
    values = _validate(name, report_type, frequency, recipients)
    return int(conn.execute(
        "INSERT INTO document_report_schedules (name, report_type, frequency, recipients, "
        "active, owner) VALUES (?, ?, ?, ?, ?, ?)",
        (*values, int(bool(active)), owner)).lastrowid)


def update_schedule(conn, schedule_id, name, report_type, frequency, recipients, active) -> None:
    get_schedule(conn, schedule_id)
    values = _validate(name, report_type, frequency, recipients)
    conn.execute(
        "UPDATE document_report_schedules SET name = ?, report_type = ?, frequency = ?, "
        "recipients = ?, active = ?, updated_at = ? WHERE schedule_id = ?",
        (*values, int(bool(active)), datetime.now().isoformat(timespec="seconds"), schedule_id))


def delete_schedule(conn, schedule_id) -> None:
    get_schedule(conn, schedule_id)
    conn.execute("DELETE FROM document_report_schedules WHERE schedule_id = ?", (schedule_id,))


def describe_frequency(frequency) -> str:
    return {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}.get(frequency, frequency)


def next_run(schedule, now=None) -> str:
    now = now or datetime.now()
    if not schedule["active"]:
        return "paused"
    if not schedule["last_run_at"]:
        return "within the next few minutes"
    due = datetime.fromisoformat(schedule["last_run_at"][:19]) + timedelta(
        days=FREQUENCIES.get(schedule["frequency"], 1))
    return max(due, now).strftime("%Y-%m-%d %H:%M")


# ── report builders (live data, same queries as the report windows) ─────


def _table_exists(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') "
                        "AND name = ?", (name,)).fetchone() is not None


def _compliance(conn):
    rows = conn.execute("""
        SELECT s.student_id, s.first_name || ' ' || s.last_name, s.course,
               COUNT(DISTINCT req_types.type_id) AS required_count,
               COUNT(DISTINCT submitted_docs.document_id) AS submitted_count
        FROM students s
        CROSS JOIN document_types req_types
        LEFT JOIN documents submitted_docs ON s.student_id = submitted_docs.owner_id
            AND submitted_docs.source_type = 'student'
            AND req_types.type_id = CAST(submitted_docs.document_type AS INTEGER)
            AND submitted_docs.is_current_version = 1
        WHERE req_types.is_required = 1
        GROUP BY s.student_id
        ORDER BY s.last_name, s.first_name
    """).fetchall()
    out = [(sid, name, course, "Compliant" if req == sub else "Non-Compliant", f"{sub}/{req}")
           for sid, name, course, req, sub in rows]
    compliant = sum(1 for r in out if r[3] == "Compliant")
    summary = (f"Students: {len(out)}, compliant: {compliant}"
               + (f" ({compliant / len(out) * 100:.1f}%)" if out else ""))
    return ("Student ID", "Name", "Course", "Status", "Progress"), out, summary


def _status(conn):
    rows = conn.execute("""
        SELECT COALESCE(verification_status, '(none)'), COUNT(*)
        FROM documents WHERE is_current_version = 1
        GROUP BY verification_status ORDER BY COUNT(*) DESC
    """).fetchall()
    return ("Status", "Count"), rows, f"Current documents: {sum(r[1] for r in rows)}"


def _expiry(conn):
    rows = conn.execute("""
        SELECT sd.document_id, sd.owner_id, s.first_name || ' ' || s.last_name,
               dt.type_name, sd.expiry_date,
               CAST((julianday(sd.expiry_date) - julianday('now')) AS INTEGER)
        FROM documents sd
        JOIN students s ON sd.owner_id = s.student_id
        JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
        WHERE sd.source_type = 'student' AND sd.expiry_date IS NOT NULL
          AND sd.expiry_date > date('now') AND sd.expiry_date <= date('now', '+30 days')
        ORDER BY sd.expiry_date ASC
    """).fetchall()
    return (("Document ID", "Student ID", "Student", "Type", "Expires", "Days Left"), rows,
            f"Documents expiring in the next 30 days: {len(rows)}")


def _pending(conn):
    rows = conn.execute("""
        SELECT sd.document_id, sd.owner_id,
               COALESCE(s.first_name || ' ' || s.last_name, ''),
               COALESCE(dt.type_name, sd.document_type),
               COALESCE(sd.original_filename, sd.file_name, sd.document_name, ''),
               sd.upload_date,
               CAST((julianday('now') - julianday(sd.upload_date)) AS INTEGER)
        FROM documents sd
        LEFT JOIN students s ON sd.owner_id = s.student_id
        LEFT JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
        WHERE sd.is_current_version = 1
          AND (sd.verification_status = 'Pending' OR sd.status = 'Pending')
        ORDER BY sd.upload_date ASC
    """).fetchall()
    return (("Document ID", "Owner", "Student", "Type", "File", "Uploaded", "Days Waiting"), rows,
            f"Documents waiting for verification: {len(rows)}")


def _monthly(conn):
    total, verified, pending, rejected = conn.execute("""
        SELECT COUNT(*),
               COALESCE(SUM(verification_status = 'Verified'), 0),
               COALESCE(SUM(verification_status = 'Pending'), 0),
               COALESCE(SUM(verification_status = 'Rejected'), 0)
        FROM documents
        WHERE strftime('%Y-%m', upload_date) = strftime('%Y-%m', 'now')
    """).fetchone()
    rows = [("Uploads this month", total), ("Verified", verified),
            ("Pending", pending), ("Rejected", rejected)]
    return ("Measure", "Value"), rows, f"Month: {datetime.now():%B %Y}"


def _statistics(conn):
    stats = conn.execute("""
        SELECT COUNT(*), COUNT(DISTINCT owner_id), COUNT(DISTINCT document_type),
               COALESCE(SUM(verification_status = 'Pending'), 0),
               COALESCE(SUM(verification_status = 'Verified'), 0),
               COALESCE(SUM(verification_status = 'Rejected'), 0),
               COALESCE(SUM(expiry_date IS NOT NULL AND DATE(expiry_date) < DATE('now')), 0),
               COALESCE(SUM(file_size), 0)
        FROM documents WHERE is_current_version = 1
    """).fetchone()
    labels = ("Current documents", "Owners", "Document types in use", "Pending",
              "Verified", "Rejected", "Expired", "Total size (bytes)")
    return ("Measure", "Value"), list(zip(labels, stats)), ""


_BUILDERS = {"compliance": _compliance, "status": _status, "expiry": _expiry,
             "pending": _pending, "monthly": _monthly, "statistics": _statistics}


def build_report(conn, report_type) -> dict:
    """``{"title", "columns", "rows", "summary"}`` built from live data."""
    if report_type not in _BUILDERS:
        raise ValueError(f"Unknown report {report_type!r}")
    for table in ("documents", "document_types", "students"):
        if not _table_exists(conn, table):
            raise ValueError(f"The {table} table does not exist yet")
    columns, rows, summary = _BUILDERS[report_type](conn)
    return {"title": REPORTS[report_type], "columns": tuple(columns),
            "rows": [tuple(r) for r in rows], "summary": summary}


def as_text(report, now=None) -> str:
    now = now or datetime.now()
    lines = [report["title"], f"Generated {now:%Y-%m-%d %H:%M} by the Document Manager", ""]
    if report["summary"]:
        lines += [report["summary"], ""]
    if not report["rows"]:
        lines.append("Nothing to report.")
        return "\n".join(lines)
    cells = [tuple("" if v is None else str(v) for v in r) for r in report["rows"]]
    widths = [max(len(str(c)), *(len(r[i]) for r in cells)) for i, c in enumerate(report["columns"])]
    lines.append("  ".join(str(c).ljust(w) for c, w in zip(report["columns"], widths)))
    lines.append("  ".join("-" * w for w in widths))
    lines += ["  ".join(v.ljust(w) for v, w in zip(r, widths)) for r in cells]
    return "\n".join(lines)


# ── running ─────────────────────────────────────────────────────────────


def run_schedule(conn, schedule, now=None) -> list[tuple]:
    """Build one schedule's report now, mark it run; returns e-mails to send."""
    now = now or datetime.now()
    try:
        report = build_report(conn, schedule["report_type"])
        text = as_text(report, now)
        result = f"built, {len(report['rows'])} rows"
    except Exception as exc:  # noqa: BLE001 - a broken report still tells its readers
        text = f"The report could not be built: {exc}"
        result = f"failed: {exc}"
    recipients = parse_recipients(schedule["recipients"])
    subject = (f"{schedule['name']} — {REPORTS.get(schedule['report_type'], schedule['report_type'])} "
               f"({schedule['frequency']}), {now:%d %B %Y}")
    conn.execute("UPDATE document_report_schedules SET last_run_at = ?, last_result = ? "
                 "WHERE schedule_id = ?",
                 (now.isoformat(timespec="seconds"), f"{result}; to {len(recipients)}",
                  schedule["schedule_id"]))
    return [(a, subject, text) for a in recipients]


def _is_due(schedule, now) -> bool:
    last = schedule["last_run_at"]
    if not last:
        return True
    return datetime.fromisoformat(last[:19]) <= now - timedelta(
        days=FREQUENCIES.get(schedule["frequency"], 1)) + timedelta(minutes=5)


def run_due_reports(now=None, *, db_path=None) -> list[tuple]:
    """E-mails for every active schedule that is due; marks them run.
    Called by the university batch scheduler every minute."""
    now = now or datetime.now()
    emails: list[tuple] = []
    with closing(_connect(db_path)) as conn:
        if not _table_exists(conn, "documents"):
            return emails
        for schedule in _dicts(conn.execute(
                "SELECT * FROM document_report_schedules WHERE active = 1")):
            if _is_due(schedule, now):
                try:
                    emails += run_schedule(conn, schedule, now)
                except ValueError:
                    continue   # bad recipients saved earlier; the window shows them
        conn.commit()
    return emails
