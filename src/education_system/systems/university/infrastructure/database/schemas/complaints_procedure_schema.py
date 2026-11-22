"""Complaints procedure tables (OIA Good Practice Framework stages).

Applied at runtime by :func:`apply_to_connection` (no Alembic migration).
Idempotent and additive only.

* ``complaints`` — the Complaints Portal's existing table (same DDL as
  ``complaints_portal._COMPLAINTS_SCHEMA``), given the procedure columns:
  the stage (early resolution → formal → review → closed), when the stage
  started and is due, the handler, the stage's outcome and summary, the
  issues considered, when the student may escalate until, the final decision
  and closure dates, the Completion of Procedures letter and the last day a
  deadline reminder went out.
* ``complaint_events`` — the audit trail: every submission, assignment,
  stage change, outcome, escalation, closure, letter and reminder.

Rows that pre-date the procedure get a stage derived from their old status
(Pending / In Progress → early resolution with a deadline counted from the
day they were submitted; Resolved / Rejected → closed).
"""

from __future__ import annotations

from datetime import date, timedelta

COMPLAINTS_DDL = """CREATE TABLE IF NOT EXISTS complaints (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    email       TEXT NOT NULL,
    category    TEXT NOT NULL,
    priority    TEXT NOT NULL,
    subject     TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Pending',
    response    TEXT NOT NULL DEFAULT '',
    submitted   TEXT NOT NULL,
    updated     TEXT NOT NULL,
    submitted_by TEXT
)"""

COLUMNS = (
    ("complaints", "stage", "TEXT"),
    ("complaints", "received_on", "TEXT"),
    ("complaints", "stage_started", "TEXT"),
    ("complaints", "stage_due", "TEXT"),
    ("complaints", "assigned_to", "TEXT"),
    ("complaints", "outcome", "TEXT"),
    ("complaints", "outcome_summary", "TEXT"),
    ("complaints", "issues_considered", "TEXT"),
    ("complaints", "decision_at", "TEXT"),
    ("complaints", "escalation_due", "TEXT"),
    ("complaints", "final_decision_at", "TEXT"),
    ("complaints", "closed_at", "TEXT"),
    ("complaints", "closed_stage", "TEXT"),
    ("complaints", "cop_issued_at", "TEXT"),
    ("complaints", "cop_path", "TEXT"),
    ("complaints", "last_reminder_on", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS complaint_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        stage TEXT,
        detail TEXT,
        actor TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_complaint_events_complaint ON "
    "complaint_events(complaint_id, event_id)",
    "CREATE INDEX IF NOT EXISTS idx_complaints_stage ON complaints(stage, stage_due)",
)

#: Working days allowed for early resolution (kept in step with the procedure module).
EARLY_RESOLUTION_WORKING_DAYS = 10


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _working_days_after(start: date, days: int) -> date:
    current, left = start, days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def _backfill(execute) -> None:
    """Give rows that pre-date the procedure a stage from their old status."""
    rows = execute("SELECT id, status, submitted FROM complaints WHERE stage IS NULL").fetchall()
    for cid, status, submitted in rows:
        try:
            received = date.fromisoformat(str(submitted or "")[:10])
        except ValueError:
            received = date.today()
        if status in ("Resolved", "Rejected"):
            execute("UPDATE complaints SET stage = 'closed', received_on = ?, "
                    "closed_at = COALESCE(closed_at, substr(updated, 1, 10)) WHERE id = ?",
                    (received.isoformat(), cid))
        else:
            execute("UPDATE complaints SET stage = 'early_resolution', received_on = ?, "
                    "stage_started = ?, stage_due = ? WHERE id = ?",
                    (received.isoformat(), received.isoformat(),
                     _working_days_after(received, EARLY_RESOLUTION_WORKING_DAYS).isoformat(),
                     cid))


def apply(execute) -> None:
    execute(COMPLAINTS_DDL)
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in TABLES:
        execute(ddl)
    _backfill(execute)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` on an open connection, once per database file.

    Inside a caller's open transaction it applies without committing (and is
    not remembered), so it can never commit half of someone else's work; the
    caller's commit or rollback decides. In-memory databases are never
    remembered: a connection id can be reused by a new database.
    """
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
