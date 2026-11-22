"""Sixth Form bulk operations — shared plumbing: schema, structured logging,
result/job dataclasses, DB access, validation and the job audit log.

Owns the mutable module state (``DB_PATH``, ``_DB_READY``, ``_LOG_HANDLER``);
the ``bulk_operations`` facade forwards reads and writes of those names here.

Split out of ``bulk_operations.py``, which re-exports every name defined here."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
import datetime as _dt
import json
import logging
from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as db

# Same logger object as before the split (named after the original module).
logger = logging.getLogger("education_system.systems.sixth_form.domain.learners.bulk_operations.bulk_operations")

DB_PATH = paths.SIXTH_FORM_BULK_OPERATIONS_DB


OPERATIONS: tuple[str, ...] = (
    "log_behaviour",
    "add_accommodation",
    "update_student",
    "message",
    "archive_to_alumni",
    "mark_attendance",
    "authorise_absences",
    "apply_lateness",
    "import_attendance_csv",
    "recalc_attendance",
    "flag_low_attendance",
    "signoff_register",
    "enrol",
    "move_class_group",
    "assign_predicted_grades",
    "import_assessment_marks",
    "recalc_grade_reports",
    "export_progress_reports",
    "publish_report_cards",
    "apply_grade_boundaries",
    "issue_detentions",
    "award_merits",
    "escalate_behaviour",
    "safeguarding_flag",
    "assign_mentors",
    "reset_behaviour_points",
    "send_sms",
    "send_letters",
    "meeting_invites",
    "ucas_reference_reminders",
    "password_reset_emails",
    "schedule_message",
    "bursary_award",
    "raise_invoices",
    "fee_discount",
    "import_payments",
    "financial_statements",
    "exam_entries",
    "exam_access_arrangements",
    "exam_timetables",
    "ucas_export_predictions",
    "ucas_update_status",
    "promote_year_group",
    "mark_leavers",
    "reinstate_alumni",
    "gdpr_redact",
    "export_student_records",
    "anonymise_alumni",
    "assign_inventory",
    "upload_photos",
    "import_contacts_csv",
    "force_password_reset",
    "undo_job",
    "schedule_recurring",
    # Attendance & registers
    "mark_holiday",
    "clear_attendance",
    "late_to_unauth",
    "attendance_letters",
    "punctuality_report",
    "register_closure",
    # Academic / teaching
    "assign_subjects",
    "withdraw_subjects",
    "set_teaching_set",
    "import_timetable_csv",
)

# Fields safe to bulk-update on the students table. Everything else
# (student_id, email, full_name) is locked down to avoid mass damage.
SAFE_STUDENT_FIELDS: tuple[str, ...] = (
    "phone",
    "emergency_contact_name",
    "emergency_contact_phone",
    "emergency_contact_relation",
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS bulk_jobs (
    job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    operation       TEXT NOT NULL,
    summary         TEXT NOT NULL,
    target_count    INTEGER NOT NULL DEFAULT 0,
    success_count   INTEGER NOT NULL DEFAULT 0,
    failure_count   INTEGER NOT NULL DEFAULT 0,
    parameters      TEXT,
    success_ids     TEXT,
    failures        TEXT,
    ran_by          TEXT,
    ran_at          TEXT NOT NULL,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_bj_op    ON bulk_jobs(operation);
CREATE INDEX IF NOT EXISTS idx_bj_ts    ON bulk_jobs(ran_at DESC);

CREATE TABLE IF NOT EXISTS report_card_publications (
    student_id    TEXT NOT NULL,
    period        TEXT NOT NULL,
    published_at  TEXT NOT NULL DEFAULT (datetime('now')),
    published_by  TEXT,
    PRIMARY KEY (student_id, period)
);

CREATE TABLE IF NOT EXISTS student_inventory (
    inv_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,
    identifier    TEXT NOT NULL,
    assigned_at   TEXT NOT NULL DEFAULT (datetime('now')),
    assigned_by   TEXT,
    UNIQUE (kind, identifier)
);
CREATE INDEX IF NOT EXISTS idx_sinv_student ON student_inventory(student_id);

CREATE TABLE IF NOT EXISTS password_reset_required (
    student_id    TEXT PRIMARY KEY,
    flagged_at    TEXT NOT NULL DEFAULT (datetime('now')),
    flagged_by    TEXT,
    reason        TEXT
);

CREATE TABLE IF NOT EXISTS bulk_operation_logs (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    level         TEXT NOT NULL,
    logger        TEXT,
    operation     TEXT,
    job_id        INTEGER,
    message       TEXT NOT NULL,
    exc_info      TEXT
);
CREATE INDEX IF NOT EXISTS idx_bol_ts    ON bulk_operation_logs(ts DESC);
CREATE INDEX IF NOT EXISTS idx_bol_level ON bulk_operation_logs(level);
CREATE INDEX IF NOT EXISTS idx_bol_op    ON bulk_operation_logs(operation);

CREATE TABLE IF NOT EXISTS register_closures (
    slot_id      INTEGER NOT NULL,
    date         TEXT NOT NULL,
    closed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    closed_by    TEXT,
    notes        TEXT,
    PRIMARY KEY (slot_id, date)
);
CREATE INDEX IF NOT EXISTS idx_rc_date ON register_closures(date);

CREATE TABLE IF NOT EXISTS bulk_schedules (
    schedule_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    operation     TEXT NOT NULL,
    parameters    TEXT,
    cron_expr     TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    next_run_at   TEXT,
    last_run_at   TEXT,
    last_job_id   INTEGER,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


# Added after the first release — applied with ALTER TABLE.
_SCHEDULE_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("last_status", "TEXT"),
    ("last_error", "TEXT"),
)


# ── Logging: shared structured logger + SQLite persistence ────────

class _SQLiteLogHandler(logging.Handler):
    """Persist every emitted record into ``bulk_operation_logs``.

    Safe against re-entrancy (handler errors never call back into the
    same logger). DB connect failures are reported via
    ``self.handleError`` rather than raised — losing a log line is
    preferable to crashing the operation.
    """

    def __init__(self, db_path: Any) -> None:
        super().__init__(level=logging.DEBUG)
        self._db_path = db_path

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            exc = None
            if record.exc_info:
                import traceback as _tb
                exc = "".join(_tb.format_exception(*record.exc_info))
            ts = _dt.datetime.fromtimestamp(
                record.created).isoformat(sep=" ", timespec="seconds")
            with db.connect(str(self._db_path)) as conn:
                conn.execute(
                    """INSERT INTO bulk_operation_logs
                          (ts, level, logger, operation, job_id,
                           message, exc_info)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ts, record.levelname, record.name,
                     getattr(record, "bulk_operation", None),
                     getattr(record, "bulk_job_id", None),
                     msg, exc),
                )
                conn.commit()
        except Exception:  # noqa: BLE001 — handler must not raise
            self.handleError(record)


_LOG_HANDLER: _SQLiteLogHandler | None = None


def _install_logging() -> None:
    """Attach the SQLite handler and configure the shared structured
    logger. Idempotent."""
    global _LOG_HANDLER
    if _LOG_HANDLER is not None:
        return
    try:
        from education_system.platform.kernel.core.structured_logging import (
            setup_structured_logging,
        )
        setup_structured_logging(system="sixthform-bulk")
    except Exception:  # noqa: BLE001 — never fail because of logging
        logging.basicConfig(level=logging.INFO)
    handler = _SQLiteLogHandler(DB_PATH)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = True
    _LOG_HANDLER = handler


def log_event(level: int, message: str, *,
               operation: str | None = None,
               job_id: int | None = None,
               exc_info: bool = False) -> None:
    """Emit a structured log record tagged with the bulk operation +
    job_id so the SQLite handler can index it."""
    logger.log(level, message,
               extra={"bulk_operation": operation,
                      "bulk_job_id": job_id},
               exc_info=exc_info)


@dataclass
class LogRecord:
    log_id: int
    ts: str
    level: str
    logger: str | None
    operation: str | None
    job_id: int | None
    message: str
    exc_info: str | None


def list_logs(
    *,
    level: str | None = None,
    operation: str | None = None,
    limit: int = 200,
) -> list[LogRecord]:
    init_db()
    clauses, args = [], []
    if level:
        clauses.append("level = ?")
        args.append(level.upper())
    if operation:
        clauses.append("operation = ?")
        args.append(operation)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    try:
        n = int(limit)
    except (TypeError, ValueError):
        raise ValidationError("limit must be a number") from None
    if n <= 0 or n > 10000:
        raise ValidationError("limit must be 1..10000")
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM bulk_operation_logs {where} "
            f"ORDER BY ts DESC, log_id DESC LIMIT {n}",
            args).fetchall()
    return [LogRecord(
        log_id=r["log_id"], ts=r["ts"], level=r["level"],
        logger=r["logger"], operation=r["operation"],
        job_id=r["job_id"], message=r["message"],
        exc_info=r["exc_info"],
    ) for r in rows]


def clear_logs(*, older_than_days: int | None = None) -> int:
    init_db()
    with _connect() as conn:
        if older_than_days is None:
            cur = conn.execute("DELETE FROM bulk_operation_logs")
        else:
            try:
                n = int(older_than_days)
            except (TypeError, ValueError):
                raise ValidationError(
                    "older_than_days must be numeric") from None
            cur = conn.execute(
                "DELETE FROM bulk_operation_logs "
                "WHERE ts < datetime('now', ?)",
                (f"-{n} days",),
            )
        conn.commit()
        return cur.rowcount


@dataclass
class BulkResult:
    operation: str
    target_count: int
    success_ids: list[str] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)
    job_id: int | None = None

    @property
    def success_count(self) -> int:
        return len(self.success_ids)

    @property
    def failure_count(self) -> int:
        return len(self.failures)


@dataclass
class Job:
    job_id: int
    operation: str
    summary: str
    target_count: int
    success_count: int
    failure_count: int
    parameters: dict[str, Any]
    success_ids: list[str]
    failures: list[tuple[str, str]]
    ran_by: str | None
    ran_at: str
    notes: str | None


@dataclass
class Summary:
    total_jobs: int
    by_operation: dict[str, int]
    total_targets: int
    total_successes: int
    total_failures: int
    most_recent_ts: str | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(DB_PATH))
    conn.row_factory = db.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
            have = {r[1] for r in conn.execute(
                "PRAGMA table_info(bulk_schedules)").fetchall()}
            for col, decl in _SCHEDULE_NEW_COLUMNS:
                if col not in have:
                    conn.execute(
                        f"ALTER TABLE bulk_schedules ADD COLUMN {col} {decl}")
    except db.Error as e:
        # Without a DB we can't even persist logs, so fall back to
        # stderr and re-raise so callers know the module is unusable.
        logging.getLogger("education_system.systems.sixth_form.domain.learners.bulk_operations.bulk_operations").exception(
            "Bulk-operations schema init failed at %s", DB_PATH)
        raise ValidationError(f"Database init failed: {e}") from e
    _DB_READY = True
    _install_logging()
    log_event(logging.DEBUG,
              f"Bulk-operations schema ready at {DB_PATH}")


def _row_job(r: db.Row) -> Job:
    try:
        params = json.loads(r["parameters"]) if r["parameters"] else {}
    except (TypeError, ValueError):
        params = {}
    try:
        sids = json.loads(r["success_ids"]) if r["success_ids"] else []
    except (TypeError, ValueError):
        sids = []
    try:
        fails = json.loads(r["failures"]) if r["failures"] else []
        fails = [(p[0], p[1]) for p in fails if isinstance(p, list)]
    except (TypeError, ValueError):
        fails = []
    return Job(
        job_id=r["job_id"], operation=r["operation"],
        summary=r["summary"],
        target_count=r["target_count"],
        success_count=r["success_count"],
        failure_count=r["failure_count"],
        parameters=params, success_ids=sids, failures=fails,
        ran_by=r["ran_by"], ran_at=r["ran_at"], notes=r["notes"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _preview_targets(result: BulkResult, targets: list[str],
                       verb: str) -> BulkResult:
    """Helper for ops that don't otherwise produce diff info during
    dry-run: stamp ``sid: would-<verb>`` into ``success_ids`` so the
    GUI/CLI preview dialog shows real per-target lines."""
    for sid in targets:
        result.success_ids.append(f"{sid}: would {verb}")
    return result


def _validate_targets(student_ids: Any) -> list[str]:
    if not student_ids:
        raise ValidationError("Pick at least one student")
    if not isinstance(student_ids, (list, tuple)):
        raise ValidationError("student_ids must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for s in student_ids:
        sid = str(s or "").strip()
        if not sid:
            continue
        if sid in seen:
            continue
        out.append(sid)
        seen.add(sid)
    if not out:
        raise ValidationError("Pick at least one student")
    return out


# ── Audit-log helpers ─────────────────────────────────────────────

def _log_job(*, operation: str, summary: str, params: dict[str, Any],
              result: BulkResult, ran_by: str | None,
              notes: str | None = None) -> int:
    init_db()
    ts = _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO bulk_jobs
                       (operation, summary, target_count, success_count,
                        failure_count, parameters, success_ids, failures,
                        ran_by, ran_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (operation, summary, result.target_count,
                 result.success_count, result.failure_count,
                 json.dumps(params, default=str),
                 json.dumps(result.success_ids),
                 json.dumps([list(p) for p in result.failures]),
                 ran_by, ts, notes),
            )
            conn.commit()
            job_id = cur.lastrowid
    except db.Error as e:
        log_event(logging.ERROR,
                  f"Failed to record job for {operation}: {e}",
                  operation=operation, exc_info=True)
        raise ValidationError(f"Database error: {e}") from e
    level = logging.WARNING if result.failure_count else logging.INFO
    log_event(level,
              f"{operation} ok={result.success_count}/"
              f"{result.target_count} fail={result.failure_count}"
              + (f" ran_by={ran_by}" if ran_by else "")
              + f" — {summary}",
              operation=operation, job_id=job_id)
    return job_id


def get_job(job_id: int) -> Job | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM bulk_jobs WHERE job_id = ?",
            (job_id,)).fetchone()
        return _row_job(r) if r else None


def list_jobs(*, operation: str | None = None,
               limit: int = 100) -> list[Job]:
    init_db()
    clauses, args = [], []
    if operation:
        if operation not in OPERATIONS:
            raise ValidationError(
                f"Operation must be one of: {', '.join(OPERATIONS)}")
        clauses.append("operation = ?")
        args.append(operation)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    try:
        n = int(limit)
    except (TypeError, ValueError):
        raise ValidationError("limit must be a number") from None
    if n <= 0 or n > 10000:
        raise ValidationError("limit must be 1..10000")
    sql = (f"SELECT * FROM bulk_jobs {where} "
           f"ORDER BY ran_at DESC, job_id DESC LIMIT {n}")
    with _connect() as conn:
        return [_row_job(r) for r in conn.execute(sql, args).fetchall()]


def delete_job(job_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM bulk_jobs WHERE job_id = ?", (job_id,))
        conn.commit()
        return bool(cur.rowcount)


# ── Helper: percentage → letter (for predicted-from-baseline) ─────

def _pct_to_letter(pct: float | None) -> str | None:
    if pct is None:
        return None
    if pct >= 90: return "A*"
    if pct >= 80: return "A"
    if pct >= 70: return "B"
    if pct >= 60: return "C"
    if pct >= 50: return "D"
    if pct >= 40: return "E"
    return "U"
