"""Bulk Operations — mass actions across many student records.

Concrete operations each take a list of student ids + a small
parameters dict and return a :class:`BulkResult` (success ids and
``(target, reason)`` failures). Every run is appended to the
``bulk_jobs`` audit table so admins can see what was run, by whom,
and how many rows it touched. Every emitted log record is also
persisted to ``bulk_operation_logs`` so failures can be inspected
offline.

Operations:

* ``bulk_log_behaviour``       — same behaviour entry against many students.
* ``bulk_add_accommodation``   — same accommodation against many students.
* ``bulk_update_student``      — set a single editable field on many.
* ``bulk_message``             — send the same message to many students.
* ``bulk_archive_to_alumni``   — convert many students to alumni rows.

All operations are best-effort per row: a failure on one target does
not roll back the rest. Successes and failures land in the same
:class:`BulkResult`.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.learners.bulk_operations import (
    bulk_operations as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.BULK_OPERATIONS_DB


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
            with sqlite3.connect(str(self._db_path)) as conn:
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

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error as e:
        # Without a DB we can't even persist logs, so fall back to
        # stderr and re-raise so callers know the module is unusable.
        logging.getLogger(__name__).exception(
            "Bulk-operations schema init failed at %s", DB_PATH)
        raise ValidationError(f"Database init failed: {e}") from e
    _DB_READY = True
    _install_logging()
    log_event(logging.DEBUG,
              f"Bulk-operations schema ready at {DB_PATH}")


def _row_job(r: sqlite3.Row) -> Job:
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
    except sqlite3.Error as e:
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


# ── Operation: bulk log behaviour ──────────────────────────────────

def bulk_log_behaviour(
    student_ids: list[str],
    *,
    entry_date: str,
    entry_type: str,
    category: str,
    description: str,
    severity: str | None = None,
    points: int = 0,
    location: str | None = None,
    recorded_by: str | None = None,
    action_taken: str | None = None,
    follow_up_required: bool = False,
    parent_contacted: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="log_behaviour",
                          target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":         sid,
                "entry_date":         entry_date,
                "entry_type":         entry_type,
                "category":           category,
                "description":        description,
                "severity":           severity,
                "points":             points,
                "location":           location,
                "recorded_by":        recorded_by,
                "action_taken":       action_taken,
                "follow_up_required": follow_up_required,
                "parent_contacted":   parent_contacted,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Logged {entry_type}/{category} behaviour against "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="log_behaviour", summary=summary,
        params={"entry_date": entry_date, "entry_type": entry_type,
                "category": category, "severity": severity,
                "points": points, "location": location,
                "recorded_by": recorded_by,
                "description": description},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk add accommodation ─────────────────────────────

def bulk_add_accommodation(
    student_ids: list[str],
    *,
    name: str,
    category: str = "Exam Access",
    description: str | None = None,
    status: str = "Active",
    start_date: str | None = None,
    end_date: str | None = None,
    approved_by: str | None = None,
    approved_date: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.accessibility import (
        accessibility as _ax,
    )
    result = BulkResult(operation="add_accommodation",
                          target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _ax.create_accommodation({
                "student_id":    sid,
                "name":          name,
                "category":      category,
                "description":   description,
                "status":        status,
                "start_date":    start_date,
                "end_date":      end_date,
                "approved_by":   approved_by,
                "approved_date": approved_date,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Added accommodation {name!r} ({category}) to "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="add_accommodation", summary=summary,
        params={"name": name, "category": category,
                "status": status, "start_date": start_date,
                "end_date": end_date, "approved_by": approved_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk update student field ───────────────────────────

def bulk_update_student(
    student_ids: list[str],
    *,
    field: str,
    value: Any,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    if field not in SAFE_STUDENT_FIELDS:
        raise ValidationError(
            f"Field {field!r} cannot be bulk-updated. "
            f"Allowed: {', '.join(SAFE_STUDENT_FIELDS)}")
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="update_student",
                          target_count=len(targets))
    if dry_run:
        # Diff preview: surface before→after per student in success_ids.
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        for sid in targets:
            try:
                existing = _students.get_student(sid)
                if existing is None:
                    result.failures.append(
                        (sid, f"No student with id {sid}"))
                    continue
                before = getattr(existing, field, None)
                if before == value:
                    result.success_ids.append(f"{sid}: (no change)")
                else:
                    result.success_ids.append(
                        f"{sid}: {before!r} → {value!r}")
            except Exception as e:
                result.failures.append((sid, str(e)))
        return result
    for sid in targets:
        try:
            existing = _students.get_student(sid)
            if existing is None:
                raise ValidationError(f"No student with id {sid}")
            # students.update_student re-validates the whole record,
            # so we have to merge the changed field onto the full
            # payload rather than passing a sparse dict.
            payload: dict[str, Any] = {
                "first_name":                 existing.first_name,
                "middle_name":                existing.middle_name,
                "last_name":                  existing.last_name,
                "phone":                      existing.phone,
                "emergency_contact_name":     existing.emergency_contact_name,
                "emergency_contact_phone":    existing.emergency_contact_phone,
                "emergency_contact_relation": existing.emergency_contact_relation,
                "subject_1":                  existing.subject_1,
                "subject_2":                  existing.subject_2,
                "subject_3":                  existing.subject_3,
            }
            payload[field] = value
            _students.update_student(sid, payload)
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Set {field}={value!r} on "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="update_student", summary=summary,
        params={"field": field, "value": value},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk message ───────────────────────────────────────

def bulk_message(
    student_ids: list[str],
    *,
    subject: str,
    body: str,
    channel: str = "Email",
    category: str = "General",
    priority: str = "Normal",
    status: str = "Sent",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    result = BulkResult(operation="message",
                          target_count=len(targets))
    if dry_run:
        return result
    try:
        sent = _msg.bulk_send(
            subject=subject, body=body,
            student_ids=targets,
            channel=channel, category=category,
            priority=priority, status=status,
        )
        for m in sent.created:
            sid = getattr(m, "student_id", None)
            if sid:
                result.success_ids.append(sid)
        for label, reason in sent.failed:
            result.failures.append((label, reason))
    except Exception as e:
        # Total failure (e.g. messages module rejected payload). Mark
        # all targets as failed so the job log is honest.
        for sid in targets:
            result.failures.append((sid, str(e)))
    summary = (f"Sent {subject!r} to "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="message", summary=summary,
        params={"subject": subject, "channel": channel,
                "category": category, "priority": priority,
                "status": status},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk archive to alumni ─────────────────────────────

def bulk_archive_to_alumni(
    student_ids: list[str],
    *,
    leaving_year: str | None = None,
    leaving_date: str | None = None,
    leaving_reason: str | None = None,
    destination_type: str = "Unknown",
    delete_students: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.learners.alumni import (
        alumni as _al,
    )
    result = BulkResult(operation="archive_to_alumni",
                          target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _al.archive_student(
                sid,
                leaving_year=leaving_year,
                leaving_date=leaving_date,
                leaving_reason=leaving_reason,
                destination_type=destination_type,
                delete_student=delete_students,
            )
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary = (f"Archived {result.success_count}/{result.target_count} "
               f"students → alumni (year={leaving_year or 'auto'}, "
               f"delete={delete_students})")
    result.job_id = _log_job(
        operation="archive_to_alumni", summary=summary,
        params={"leaving_year": leaving_year,
                "leaving_date": leaving_date,
                "leaving_reason": leaving_reason,
                "destination_type": destination_type,
                "delete_students": delete_students},
        result=result, ran_by=ran_by,
    )
    return result


# ── Attendance helpers ────────────────────────────────────────────

def _daterange(date_from: str, date_to: str) -> list[str]:
    """Inclusive list of YYYY-MM-DD strings between two dates (weekdays only)."""
    try:
        d0 = _dt.date.fromisoformat(date_from)
        d1 = _dt.date.fromisoformat(date_to)
    except ValueError as e:
        raise ValidationError(f"Invalid date: {e}") from e
    if d1 < d0:
        raise ValidationError("date_to must be on or after date_from")
    if (d1 - d0).days > 366:
        raise ValidationError("Date range too wide (max 366 days)")
    out: list[str] = []
    cur = d0
    one = _dt.timedelta(days=1)
    while cur <= d1:
        if cur.weekday() < 5:  # Mon–Fri
            out.append(cur.isoformat())
        cur += one
    return out


# ── Operation: bulk mark attendance ───────────────────────────────

def bulk_mark_attendance(
    student_ids: list[str],
    *,
    slot_id: int,
    date: str,
    status: str = "Present",
    minutes_late: int | None = None,
    notes: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Stamp the same status against many students on one slot+date."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="mark_attendance",
                         target_count=len(targets))
    if dry_run:
        return result
    entries = {
        sid: {"status": status, "minutes_late": minutes_late, "notes": notes}
        for sid in targets
    }
    try:
        _att.save_register(slot_id, date, entries)
        result.success_ids.extend(targets)
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, str(e)))
    summary_text = (f"Marked {status} for "
                    f"{result.success_count}/{result.target_count} students "
                    f"on slot #{slot_id} ({date})")
    result.job_id = _log_job(
        operation="mark_attendance", summary=summary_text,
        params={"slot_id": slot_id, "date": date, "status": status,
                "minutes_late": minutes_late, "notes": notes},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk authorise absences ────────────────────────────

def bulk_authorise_absences(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    target_status: str = "Authorised",
    reason: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flip Absent rows → Authorised (or reverse) across a date window.

    Only rows currently in the opposite state are touched. ``reason``,
    if given, is appended to each row's notes column.
    """
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    if target_status not in ("Authorised", "Absent"):
        raise ValidationError("target_status must be Authorised or Absent")
    source_status = "Absent" if target_status == "Authorised" else "Authorised"
    result = BulkResult(operation="authorise_absences",
                         target_count=len(targets))
    if dry_run:
        return result
    touched = 0
    for sid in targets:
        try:
            rows = _att.list_records(
                student_id=sid,
                date_from=date_from, date_to=date_to,
                status=source_status,
            )
            for rec in rows:
                merged_notes = rec.notes or ""
                if reason:
                    merged_notes = (
                        f"{merged_notes} | {reason}".strip(" |")
                        if merged_notes else reason
                    )
                _att.update_record(rec.record_id, {
                    "status": target_status,
                    "minutes_late": rec.minutes_late,
                    "notes": merged_notes or None,
                })
                touched += 1
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Re-flagged {source_status}→{target_status} on {touched} row(s) "
        f"across {result.success_count}/{result.target_count} students "
        f"({date_from}..{date_to})"
    )
    result.job_id = _log_job(
        operation="authorise_absences", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "target_status": target_status, "reason": reason,
                "rows_touched": touched},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk apply lateness ────────────────────────────────

def bulk_apply_lateness(
    student_ids: list[str],
    *,
    slot_id: int,
    date: str,
    minutes_late: int,
    auto_log_behaviour_over: int | None = None,
    behaviour_recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Mark all listed students Late with the same minutes_late.

    If ``auto_log_behaviour_over`` is set and ``minutes_late`` is at or
    above it, a negative behaviour entry is also logged for each student
    (acts as the "auto-detention threshold" trigger).
    """
    targets = _validate_targets(student_ids)
    try:
        minutes_late = int(minutes_late)
    except (TypeError, ValueError):
        raise ValidationError("minutes_late must be a number") from None
    if minutes_late < 0 or minutes_late > 1000:
        raise ValidationError("minutes_late must be 0..1000")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="apply_lateness",
                         target_count=len(targets))
    if dry_run:
        return result
    entries = {
        sid: {"status": "Late", "minutes_late": minutes_late, "notes": None}
        for sid in targets
    }
    try:
        _att.save_register(slot_id, date, entries)
        result.success_ids.extend(targets)
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, str(e)))

    behaviour_logged = 0
    if (result.success_ids and auto_log_behaviour_over is not None
            and minutes_late >= auto_log_behaviour_over):
        from education_system.systems.sixth_form.domain.pastoral.behaviour import (
            behaviour as _bh,
        )
        for sid in list(result.success_ids):
            try:
                _bh.create_entry({
                    "student_id":   sid,
                    "entry_date":   date,
                    "entry_type":   "Negative",
                    "category":     "Lateness",
                    "description":  (f"Auto-flag: {minutes_late} min late "
                                     f"(threshold {auto_log_behaviour_over})"),
                    "severity":     "Low",
                    "points":       1,
                    "recorded_by":  behaviour_recorded_by,
                    "action_taken": "Detention threshold reached",
                })
                behaviour_logged += 1
            except Exception:  # noqa: BLE001 — best-effort secondary log
                logger.exception("auto-log behaviour failed for %s", sid)

    summary_text = (
        f"Marked Late ({minutes_late} min) on slot #{slot_id} ({date}) for "
        f"{result.success_count}/{result.target_count}"
        + (f"; behaviour logged ×{behaviour_logged}"
           if behaviour_logged else "")
    )
    result.job_id = _log_job(
        operation="apply_lateness", summary=summary_text,
        params={"slot_id": slot_id, "date": date,
                "minutes_late": minutes_late,
                "auto_log_behaviour_over": auto_log_behaviour_over,
                "behaviour_logged": behaviour_logged},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk import attendance CSV ─────────────────────────

def bulk_import_attendance_csv(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Import attendance rows from a CSV.

    Required headers: ``student_id, slot_id, date, status``.
    Optional: ``minutes_late, notes``. One row per record; failures are
    reported per-line so partial imports are kept.
    """
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        required = {"student_id", "slot_id", "date", "status"}
        missing = required - set(h.strip() for h in (reader.fieldnames or []))
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})

    result = BulkResult(operation="import_attendance_csv",
                         target_count=len(rows))
    if dry_run:
        return result
    # Group by (slot_id, date) so save_register can upsert in one tx.
    grouped: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
    line_tags: dict[tuple[int, str, str], int] = {}
    for i, r in enumerate(rows, start=2):  # +2 to account for header line
        sid = r.get("student_id", "")
        try:
            slot_id = int(r.get("slot_id", ""))
        except ValueError:
            result.failures.append(
                (f"line {i}", f"slot_id not numeric: {r.get('slot_id')!r}"))
            continue
        date = r.get("date", "")
        status = r.get("status", "")
        minutes = r.get("minutes_late") or None
        if minutes:
            try:
                minutes = int(minutes)
            except ValueError:
                result.failures.append(
                    (f"line {i}", f"minutes_late not numeric: {minutes!r}"))
                continue
        notes = r.get("notes") or None
        key = (slot_id, date)
        grouped.setdefault(key, {})[sid] = {
            "status": status, "minutes_late": minutes, "notes": notes,
        }
        line_tags[(slot_id, date, sid)] = i

    for (slot_id, date), entries in grouped.items():
        try:
            _att.save_register(slot_id, date, entries)
            for sid in entries:
                result.success_ids.append(
                    f"L{line_tags[(slot_id, date, sid)]}:{sid}")
        except Exception as e:
            for sid in entries:
                result.failures.append(
                    (f"line {line_tags[(slot_id, date, sid)]}:{sid}",
                     str(e)))
    summary_text = (f"Imported {result.success_count}/{result.target_count} "
                    f"attendance rows from {os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_attendance_csv", summary=summary_text,
        params={"csv_path": csv_path, "groups": len(grouped)},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk recalculate attendance % ──────────────────────

def bulk_recalc_attendance(
    student_ids: list[str],
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Compute attendance summary % for each student in the window.

    Successes carry an ``sid:pct`` token so the job log is auditable; this
    is a read-only operation that exists primarily to bookkeep "we
    recalculated cohort X on date Y".
    """
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="recalc_attendance",
                         target_count=len(targets))
    if dry_run:
        return result
    samples: list[tuple[str, float | None, int]] = []
    for sid in targets:
        try:
            s = _att.summary_for_student(
                sid, date_from=date_from, date_to=date_to)
            samples.append((sid, s.percentage, s.total))
            tag = f"{sid}:{'—' if s.percentage is None else f'{s.percentage}%'}"
            result.success_ids.append(tag)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Recalculated attendance for "
        f"{result.success_count}/{result.target_count} students "
        f"({date_from or 'all'}..{date_to or 'all'})"
    )
    result.job_id = _log_job(
        operation="recalc_attendance", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "samples": [[sid, pct, total]
                            for sid, pct, total in samples]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk flag students below attendance threshold ──────

def bulk_flag_low_attendance(
    student_ids: list[str],
    *,
    threshold_pct: float = 90.0,
    window_days: int = 28,
    level: str = "Medium",
    reason: str = "Low overall attendance",
    raised_by: str | None = None,
    skip_if_open_concern: bool = True,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each student, compute % over the window and open an
    attendance_concern row if below ``threshold_pct``."""
    targets = _validate_targets(student_ids)
    try:
        threshold_pct = float(threshold_pct)
    except (TypeError, ValueError):
        raise ValidationError("threshold_pct must be numeric") from None
    if not (0.0 <= threshold_pct <= 100.0):
        raise ValidationError("threshold_pct must be 0..100")
    try:
        window_days = int(window_days)
    except (TypeError, ValueError):
        raise ValidationError("window_days must be numeric") from None
    if window_days <= 0 or window_days > 365:
        raise ValidationError("window_days must be 1..365")

    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import (
        attendance_concerns as _ac,
    )
    end = _dt.date.today()
    start = end - _dt.timedelta(days=window_days)
    df, dt = start.isoformat(), end.isoformat()

    result = BulkResult(operation="flag_low_attendance",
                         target_count=len(targets))
    if dry_run:
        return result
    flagged = 0
    for sid in targets:
        try:
            summ = _att.summary_for_student(
                sid, date_from=df, date_to=dt)
            pct = summ.percentage
            if summ.total == 0 or pct is None or pct >= threshold_pct:
                result.success_ids.append(f"{sid}:skip")
                continue
            if skip_if_open_concern:
                existing = _ac.list_concerns(
                    student_id=sid, open_only=True)
                if existing:
                    result.success_ids.append(f"{sid}:has-open")
                    continue
            _ac.create_concern({
                "student_id":    sid,
                "raised_date":   dt,
                "reason":        reason,
                "level":         level,
                "status":        "Open",
                "threshold_pct": threshold_pct,
                "observed_pct":  pct,
                "window_days":   window_days,
                "description":   (f"Auto-flagged: {pct}% over last "
                                  f"{window_days} days "
                                  f"(threshold {threshold_pct}%)"),
                "raised_by":     raised_by,
            })
            flagged += 1
            result.success_ids.append(f"{sid}:flagged@{pct}%")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Reviewed {result.success_count}/{result.target_count}; "
                    f"opened {flagged} concern(s) under {threshold_pct}% "
                    f"({window_days}-day window)")
    result.job_id = _log_job(
        operation="flag_low_attendance", summary=summary_text,
        params={"threshold_pct": threshold_pct, "window_days": window_days,
                "level": level, "reason": reason,
                "flagged": flagged},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk close-of-day register sign-off ────────────────

def bulk_signoff_register(
    slot_ids: list[int],
    *,
    date: str,
    default_status: str = "Present",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each slot, fill any student who has no record on ``date``
    with ``default_status``. Existing records are left untouched."""
    if not slot_ids:
        raise ValidationError("Pick at least one slot")
    # Reuse target validation on stringified slot ids so the BulkResult
    # contract holds (success_ids are strings).
    str_targets = _validate_targets([str(s) for s in slot_ids])
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="signoff_register",
                         target_count=len(str_targets))
    if dry_run:
        return result
    filled_total = 0
    for tag in str_targets:
        try:
            slot_id = int(tag)
            roster = _att.register_view(slot_id, date)
            missing = {
                entry.student_id: {"status": default_status,
                                    "minutes_late": None,
                                    "notes": "Signed off (default)"}
                for entry in roster if entry.record is None
            }
            if missing:
                _att.save_register(slot_id, date, missing)
            filled_total += len(missing)
            result.success_ids.append(f"slot#{slot_id}:+{len(missing)}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (f"Signed off {result.success_count}/"
                    f"{result.target_count} slots on {date}; "
                    f"filled {filled_total} blank entry(ies) as "
                    f"{default_status}")
    result.job_id = _log_job(
        operation="signoff_register", summary=summary_text,
        params={"date": date, "default_status": default_status,
                "slot_ids": [int(t) for t in str_targets],
                "filled": filled_total},
        result=result, ran_by=ran_by,
    )
    return result


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


# ── Operation: bulk enrol ─────────────────────────────────────────

def bulk_enrol(
    student_ids: list[str],
    *,
    academic_year: str,
    year_group: int,
    tutor_group: str | None = None,
    start_date: str | None = None,
    status: str = "Enrolled",
    notes: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _en,
    )
    result = BulkResult(operation="enrol", target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _en.create_enrolment({
                "student_id":    sid,
                "academic_year": academic_year,
                "year_group":    year_group,
                "tutor_group":   tutor_group,
                "start_date":    start_date,
                "status":        status,
                "notes":         notes,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Enrolled {result.success_count}/{result.target_count} "
                    f"students for {academic_year} Y{year_group}")
    result.job_id = _log_job(
        operation="enrol", summary=summary_text,
        params={"academic_year": academic_year, "year_group": year_group,
                "tutor_group": tutor_group, "start_date": start_date,
                "status": status},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk move class group ──────────────────────────────

def bulk_move_class_group(
    student_ids: list[str],
    *,
    from_group_id: int | None = None,
    to_group_id: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Remove students from one group and/or add them to another.

    Either ``from_group_id`` or ``to_group_id`` must be set; both is the
    common "transfer" case.
    """
    if from_group_id is None and to_group_id is None:
        raise ValidationError("Set from_group_id, to_group_id, or both")
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    result = BulkResult(operation="move_class_group",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            actions: list[str] = []
            if from_group_id is not None:
                if _cg.remove_member(from_group_id, sid):
                    actions.append(f"−{from_group_id}")
            if to_group_id is not None:
                _cg.add_member(to_group_id, sid)
                actions.append(f"+{to_group_id}")
            result.success_ids.append(f"{sid}:{','.join(actions) or 'noop'}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Moved {result.success_count}/{result.target_count} students "
        f"(from={from_group_id}, to={to_group_id})"
    )
    result.job_id = _log_job(
        operation="move_class_group", summary=summary_text,
        params={"from_group_id": from_group_id,
                "to_group_id": to_group_id},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk assign predicted grades ───────────────────────

def bulk_assign_predicted_grades(
    student_ids: list[str],
    *,
    subject: str,
    grade: str | None = None,
    from_baseline: bool = False,
    confidence: str = "Medium",
    predicted_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Save a predicted grade for many students on the same subject.

    If ``from_baseline`` is True, each student's grade is derived from
    their primary baseline percentage for the subject; otherwise the
    fixed ``grade`` is used for everyone.
    """
    targets = _validate_targets(student_ids)
    if not from_baseline and not grade:
        raise ValidationError(
            "Either set from_baseline=True or supply a fixed grade")
    from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
        predicted_grades as _pred,
    )
    if from_baseline:
        from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
            baseline_assessment as _bl,
        )
    result = BulkResult(operation="assign_predicted_grades",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            chosen = grade
            if from_baseline:
                rec = _bl.get_primary(sid, subject)
                pct = getattr(rec, "percentage", None) if rec else None
                bl_grade = getattr(rec, "baseline_grade", None) if rec else None
                chosen = bl_grade or _pct_to_letter(pct)
                if chosen is None:
                    raise ValidationError(
                        f"No baseline data for {sid} / {subject}")
            _pred.save_prediction({
                "student_id":   sid,
                "subject":      subject,
                "grade":        chosen,
                "confidence":   confidence,
                "predicted_by": predicted_by,
            })
            result.success_ids.append(f"{sid}:{chosen}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Saved predicted grades for "
        f"{result.success_count}/{result.target_count} students "
        f"({subject}; {'from baseline' if from_baseline else f'={grade}'})"
    )
    result.job_id = _log_job(
        operation="assign_predicted_grades", summary=summary_text,
        params={"subject": subject, "grade": grade,
                "from_baseline": from_baseline,
                "confidence": confidence,
                "predicted_by": predicted_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk import assessment marks ───────────────────────

def bulk_import_assessment_marks(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Import baseline-assessment records from a CSV.

    Required: ``student_id, subject_name, assessment_type, assessment_date,
    raw_score, max_score``. Optional: ``percentage, baseline_grade,
    confidence, assessor, notes, is_primary``.
    """
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
        baseline_assessment as _bl,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        required = {"student_id", "subject_name", "assessment_type",
                    "assessment_date", "raw_score", "max_score"}
        missing = required - set(h.strip() for h in (reader.fieldnames or []))
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})

    result = BulkResult(operation="import_assessment_marks",
                         target_count=len(rows))
    if dry_run:
        return result
    for i, r in enumerate(rows, start=2):
        sid = r.get("student_id", "")
        try:
            _bl.create_record({
                "student_id":      sid,
                "subject_name":    r.get("subject_name"),
                "assessment_type": r.get("assessment_type"),
                "assessment_date": r.get("assessment_date"),
                "raw_score":       r.get("raw_score"),
                "max_score":       r.get("max_score"),
                "percentage":      r.get("percentage") or None,
                "baseline_grade":  r.get("baseline_grade") or None,
                "confidence":      r.get("confidence") or None,
                "assessor":        r.get("assessor") or None,
                "notes":           r.get("notes") or None,
                "is_primary":      (r.get("is_primary") or "").lower()
                                    in ("1", "true", "yes", "y"),
            })
            result.success_ids.append(f"L{i}:{sid}")
        except Exception as e:
            result.failures.append((f"L{i}:{sid}", str(e)))
    import os as _os
    summary_text = (f"Imported {result.success_count}/{result.target_count} "
                    f"assessment rows from {_os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_assessment_marks", summary=summary_text,
        params={"csv_path": csv_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk recalculate grade reports ─────────────────────

def bulk_recalc_grade_reports(
    student_ids: list[str],
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Compute per-student grade reports; audit only (read-only)."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.reporting.grades_report import (
        grades_report as _gr,
    )
    result = BulkResult(operation="recalc_grade_reports",
                         target_count=len(targets))
    if dry_run:
        return result
    samples: list[list[Any]] = []
    for sid in targets:
        try:
            rep = _gr.per_student_grade_report(sid)
            avg_pred = getattr(rep, "predicted_avg_grade", None)
            avg_act = getattr(rep, "actual_avg_grade", None)
            samples.append([sid, avg_pred, avg_act])
            result.success_ids.append(
                f"{sid}:pred={avg_pred or '—'},act={avg_act or '—'}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Recalculated grade reports for "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="recalc_grade_reports", summary=summary_text,
        params={"samples": samples},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk export progress reports (text) ────────────────

def bulk_export_progress_reports(
    student_ids: list[str],
    *,
    output_dir: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Write a plain-text progress report per student to ``output_dir``."""
    import os
    targets = _validate_targets(student_ids)
    if not output_dir:
        raise ValidationError("output_dir is required")
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    from education_system.systems.sixth_form.domain.operations.reporting.grades_report import (
        grades_report as _gr,
    )
    result = BulkResult(operation="export_progress_reports",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            rep = _gr.per_student_grade_report(sid)
            lines = [
                f"Progress report — {sid}",
                f"Generated: {_dt.datetime.now().isoformat(sep=' ', timespec='seconds')}",
                "",
            ]
            for row in getattr(rep, "rows", []) or []:
                lines.append(
                    f"  {getattr(row, 'subject', '?'):<28}  "
                    f"pred={getattr(row, 'predicted', '—') or '—'}  "
                    f"mock={getattr(row, 'mock', '—') or '—'}  "
                    f"actual={getattr(row, 'actual', '—') or '—'}"
                )
            path = os.path.join(output_dir, f"progress_{sid}.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            result.success_ids.append(f"{sid}:{path}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Wrote {result.success_count}/{result.target_count} "
                    f"progress reports to {output_dir}")
    result.job_id = _log_job(
        operation="export_progress_reports", summary=summary_text,
        params={"output_dir": output_dir},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk publish / unpublish report cards ──────────────

def bulk_publish_report_cards(
    student_ids: list[str],
    *,
    period: str,
    publish: bool = True,
    published_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    period = (period or "").strip()
    if not period:
        raise ValidationError("period is required (e.g. '2025/26 T1')")
    init_db()
    result = BulkResult(
        operation="publish_report_cards", target_count=len(targets))
    if dry_run:
        return result
    op_word = "Published" if publish else "Unpublished"
    with _connect() as conn:
        for sid in targets:
            try:
                if publish:
                    conn.execute(
                        """INSERT INTO report_card_publications
                              (student_id, period, published_at, published_by)
                           VALUES (?, ?, datetime('now'), ?)
                           ON CONFLICT(student_id, period) DO UPDATE SET
                              published_at = datetime('now'),
                              published_by = excluded.published_by""",
                        (sid, period, published_by),
                    )
                else:
                    conn.execute(
                        """DELETE FROM report_card_publications
                           WHERE student_id = ? AND period = ?""",
                        (sid, period),
                    )
                result.success_ids.append(sid)
            except Exception as e:
                result.failures.append((sid, str(e)))
        conn.commit()
    summary_text = (f"{op_word} report cards for "
                    f"{result.success_count}/{result.target_count} students "
                    f"({period})")
    result.job_id = _log_job(
        operation="publish_report_cards", summary=summary_text,
        params={"period": period, "publish": publish,
                "published_by": published_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk apply grade boundaries ────────────────────────

def bulk_apply_grade_boundaries(
    assignment_ids: list[int],
    *,
    a_star: int | None = None,
    a: int | None = None,
    b: int | None = None,
    c: int | None = None,
    d: int | None = None,
    e: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Apply the same A*/A/B/C/D/E thresholds to many assignments."""
    if not assignment_ids:
        raise ValidationError("Pick at least one assignment")
    str_targets = _validate_targets([str(a_) for a_ in assignment_ids])
    if all(v is None for v in (a_star, a, b, c, d, e)):
        raise ValidationError("Set at least one grade boundary")
    from education_system.systems.sixth_form.domain.assessment.gradebook import (
        gradebook as _gb,
    )
    result = BulkResult(operation="apply_grade_boundaries",
                         target_count=len(str_targets))
    if dry_run:
        return result
    for tag in str_targets:
        try:
            aid = int(tag)
            _gb.set_boundaries(aid, {
                "a_star": a_star, "a": a, "b": b,
                "c": c, "d": d, "e": e,
            })
            result.success_ids.append(f"assn#{aid}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (
        f"Applied boundaries to {result.success_count}/"
        f"{result.target_count} assignment(s) "
        f"(A*={a_star} A={a} B={b} C={c} D={d} E={e})"
    )
    result.job_id = _log_job(
        operation="apply_grade_boundaries", summary=summary_text,
        params={"a_star": a_star, "a": a, "b": b,
                "c": c, "d": d, "e": e,
                "assignment_ids": [int(t) for t in str_targets]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk issue detentions (behaviour entries) ──────────

def bulk_issue_detentions(
    student_ids: list[str],
    *,
    date: str,
    reason: str,
    duration_minutes: int = 30,
    room: str | None = None,
    severity: str = "Low",
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="issue_detentions",
                         target_count=len(targets))
    if dry_run:
        return result
    desc = (f"Detention ({duration_minutes} min"
            f"{f', {room}' if room else ''}): {reason}")
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  date,
                "entry_type":  "Negative",
                "category":    "Other",
                "severity":    severity,
                "description": desc,
                "location":    room,
                "recorded_by": recorded_by,
                "action_taken": (f"Detention scheduled "
                                  f"({duration_minutes} min)"),
                "follow_up_required": True,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Issued detentions to "
                    f"{result.success_count}/{result.target_count} students "
                    f"on {date}")
    result.job_id = _log_job(
        operation="issue_detentions", summary=summary_text,
        params={"date": date, "reason": reason,
                "duration_minutes": duration_minutes,
                "room": room, "severity": severity},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk award merits / house points ───────────────────

def bulk_award_merits(
    student_ids: list[str],
    *,
    date: str,
    category: str = "Achievement",
    description: str,
    points: int = 5,
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="award_merits",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  date,
                "entry_type":  "Positive",
                "category":    category,
                "description": description,
                "points":      int(points),
                "recorded_by": recorded_by,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Awarded {points} merit(s) to "
                    f"{result.success_count}/{result.target_count} "
                    f"students ({category})")
    result.job_id = _log_job(
        operation="award_merits", summary=summary_text,
        params={"date": date, "category": category,
                "points": points, "description": description},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk escalate behaviour ────────────────────────────

def bulk_escalate_behaviour(
    student_ids: list[str],
    *,
    date: str,
    reason: str,
    escalate_to: str = "Senior Tutor",
    follow_up_date: str | None = None,
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Log an escalation entry (negative, High severity) per student."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    result = BulkResult(operation="escalate_behaviour",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  date,
                "entry_type":  "Negative",
                "category":    "Other",
                "severity":    "High",
                "description": f"Escalated to {escalate_to}: {reason}",
                "action_taken": f"Escalated to {escalate_to}",
                "follow_up_required": True,
                "follow_up_date": follow_up_date,
                "parent_contacted": True,
                "recorded_by": recorded_by,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Escalated {result.success_count}/"
                    f"{result.target_count} students to {escalate_to}")
    result.job_id = _log_job(
        operation="escalate_behaviour", summary=summary_text,
        params={"date": date, "reason": reason,
                "escalate_to": escalate_to,
                "follow_up_date": follow_up_date},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk safeguarding flag ─────────────────────────────

def bulk_safeguarding_flag(
    student_ids: list[str],
    *,
    concern_date: str,
    reported_date: str,
    concern_type: str,
    category: str,
    risk_level: str,
    reported_by: str,
    description: str,
    dsl_notified: bool = False,
    dsl_name: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.safeguarding import (
        safeguarding as _sg,
    )
    result = BulkResult(operation="safeguarding_flag",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _sg.create_concern({
                "student_id":   sid,
                "concern_date": concern_date,
                "reported_date": reported_date,
                "concern_type": concern_type,
                "category":     category,
                "risk_level":   risk_level,
                "reported_by":  reported_by,
                "description":  description,
                "dsl_notified": dsl_notified,
                "dsl_name":     dsl_name,
                "dsl_notified_at": (reported_date if dsl_notified else None),
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Opened safeguarding concern for "
        f"{result.success_count}/{result.target_count} students "
        f"({category}, risk={risk_level})"
    )
    result.job_id = _log_job(
        operation="safeguarding_flag", summary=summary_text,
        params={"concern_date": concern_date,
                "reported_date": reported_date,
                "concern_type": concern_type, "category": category,
                "risk_level": risk_level, "reported_by": reported_by,
                "dsl_notified": dsl_notified},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk assign mentors ────────────────────────────────

def bulk_assign_mentors(
    mentee_ids: list[str],
    *,
    mentor_id: str,
    programme: str,
    start_date: str,
    frequency: str = "Weekly",
    coordinator: str | None = None,
    planned_end: str | None = None,
    sessions_planned: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Pair one mentor with many mentees (one ``peer_mentoring`` row each)."""
    targets = _validate_targets(mentee_ids)
    mentor_id = (mentor_id or "").strip()
    if not mentor_id:
        raise ValidationError("mentor_id is required")
    if mentor_id in targets:
        raise ValidationError("Mentor cannot be in the mentee list")
    from education_system.systems.sixth_form.domain.pastoral.peer_mentoring import (
        peer_mentoring as _pm,
    )
    result = BulkResult(operation="assign_mentors",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _pm.create_pairing({
                "mentor_id":   mentor_id,
                "mentee_id":   sid,
                "programme":   programme,
                "frequency":   frequency,
                "start_date":  start_date,
                "planned_end": planned_end,
                "sessions_planned": sessions_planned,
                "coordinator": coordinator,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Paired mentor {mentor_id} with "
        f"{result.success_count}/{result.target_count} mentee(s) "
        f"({programme})"
    )
    result.job_id = _log_job(
        operation="assign_mentors", summary=summary_text,
        params={"mentor_id": mentor_id, "programme": programme,
                "frequency": frequency, "start_date": start_date,
                "planned_end": planned_end,
                "sessions_planned": sessions_planned,
                "coordinator": coordinator},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: reset behaviour points (term roll-over) ────────────

def bulk_reset_behaviour_points(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    reset_date: str | None = None,
    note: str = "Term reset",
    recorded_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each student, compute net behaviour points over the window
    and log a single counter entry that zeroes them out."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as _bh,
    )
    reset_date = reset_date or _dt.date.today().isoformat()
    result = BulkResult(operation="reset_behaviour_points",
                         target_count=len(targets))
    if dry_run:
        return result
    adjustments: list[tuple[str, int]] = []
    for sid in targets:
        try:
            entries = _bh.list_entries(student_id=sid)
            net = 0
            for e in entries:
                d = e.entry_date
                if d and date_from <= d <= date_to:
                    net += (e.points or 0)
            if net == 0:
                result.success_ids.append(f"{sid}:already-zero")
                continue
            offset = -net
            etype = "Positive" if offset > 0 else "Negative"
            cat = ("Other" if etype == "Negative"
                   else "Other")
            severity = ("Low" if etype == "Negative" else None)
            _bh.create_entry({
                "student_id":  sid,
                "entry_date":  reset_date,
                "entry_type":  etype,
                "category":    cat,
                "severity":    severity,
                "description": f"{note} ({date_from}..{date_to}): "
                               f"net={net} → offset={offset}",
                "points":      offset,
                "recorded_by": recorded_by,
            })
            adjustments.append((sid, offset))
            result.success_ids.append(f"{sid}:{offset:+d}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Reset behaviour points for "
                    f"{result.success_count}/{result.target_count} "
                    f"students ({date_from}..{date_to})")
    result.job_id = _log_job(
        operation="reset_behaviour_points", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "reset_date": reset_date, "note": note,
                "adjustments": adjustments},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk SMS (messages with channel=SMS) ───────────────

def bulk_send_sms(
    student_ids: list[str],
    *,
    body: str,
    subject: str = "SMS",
    sender_staff_id: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    result = BulkResult(operation="send_sms", target_count=len(targets))
    if dry_run:
        return result
    try:
        sent = _msg.bulk_send(
            subject=subject, body=body,
            student_ids=targets, channel="SMS",
            category="General", priority="Normal", status="Sent",
            sender_staff_id=sender_staff_id,
        )
        for m in sent.created:
            sid = getattr(m, "student_id", None)
            if sid:
                result.success_ids.append(sid)
        for label, reason in sent.failed:
            result.failures.append((label, reason))
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, str(e)))
    summary_text = (f"SMS sent to "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="send_sms", summary=summary_text,
        params={"subject": subject, "body_preview": body[:80]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk send templated letters ────────────────────────

def bulk_send_letters(
    student_ids: list[str],
    *,
    template_id: int,
    extra_context: dict[str, str] | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Render a letter template per student and store one Message row
    each (channel='Letter'). Per-student placeholders (student_id,
    full_name) are merged into ``extra_context``."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.communications.letter_templates import (
        letter_templates as _lt,
    )
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    tmpl = _lt.get_template(template_id)
    if tmpl is None:
        raise ValidationError(f"No template with id {template_id}")
    result = BulkResult(operation="send_letters",
                         target_count=len(targets))
    if dry_run:
        return result
    base_ctx = dict(extra_context or {})
    for sid in targets:
        try:
            st = _students.get_student(sid)
            ctx = {**base_ctx,
                   "student_id": sid,
                   "full_name": getattr(st, "full_name", sid) if st else sid,
                   "first_name": getattr(st, "first_name", "") if st else "",
                   "last_name": getattr(st, "last_name", "") if st else ""}
            rendered = _lt.render(tmpl, ctx, track_use=False)
            _msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Letter",
                "category":   "General",
                "priority":   "Normal",
                "status":     "Sent",
                "subject":    rendered.subject or f"Letter ({tmpl.name})",
                "body":       rendered.body,
                "student_id": sid,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent template-#{template_id} letter to "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="send_letters", summary=summary_text,
        params={"template_id": template_id,
                "extra_context": extra_context or {}},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk parents-evening meeting invites ───────────────

def bulk_meeting_invites(
    student_ids: list[str],
    *,
    event_id: int,
    booking_link: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Send a parents-evening invite email to each student's primary
    parent contact. ``booking_link`` is embedded in the body if given."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.communications.parents_evenings import (
        parents_evenings as _pe,
    )
    from education_system.systems.sixth_form.domain.operations.communications.parent_contacts import (
        parent_contacts as _pc,
    )
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    event = _pe.get_event(event_id)
    if event is None:
        raise ValidationError(f"No parents-evening event #{event_id}")
    result = BulkResult(operation="meeting_invites",
                         target_count=len(targets))
    if dry_run:
        return result
    subject = f"Parents' evening invitation — {event.title}"
    base_body = (
        f"Date: {event.event_date}\n"
        f"Location: {getattr(event, 'location', '') or '—'}\n\n"
        "Please book a slot at your earliest convenience.\n"
    )
    if booking_link:
        base_body += f"\nBooking link: {booking_link}\n"
    for sid in targets:
        try:
            contact = _pc.primary_for_student(sid)
            if contact is None:
                raise ValidationError("No primary parent contact")
            _msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "Parents Evening",
                "priority":   "Normal",
                "status":     "Sent",
                "subject":    subject,
                "body":       base_body,
                "to_name":    getattr(contact, "full_name", None),
                "to_address": getattr(contact, "email", None),
                "student_id": sid,
                "parent_contact_id": contact.contact_id,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent parents-evening invites for event #{event_id} "
                    f"to {result.success_count}/{result.target_count} "
                    f"families")
    result.job_id = _log_job(
        operation="meeting_invites", summary=summary_text,
        params={"event_id": event_id, "booking_link": booking_link},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk UCAS reference reminders ──────────────────────

def bulk_ucas_reference_reminders(
    student_ids: list[str],
    *,
    referee_email: str | None = None,
    deadline: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Send a reminder email per student to the configured referee
    asking them to complete the UCAS reference."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.progression.ucas import (
        ucas as _ucas,
    )
    result = BulkResult(operation="ucas_reference_reminders",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            st = _students.get_student(sid)
            name = getattr(st, "full_name", sid) if st else sid
            app = _ucas.get_application_for_student(sid) \
                if hasattr(_ucas, "get_application_for_student") else None
            referee = referee_email
            if not referee and app is not None:
                referee = getattr(app, "reference_email", None)
            if not referee:
                raise ValidationError("No referee email available")
            body = (
                f"This is a reminder to complete the UCAS reference "
                f"for {name} ({sid}).\n"
            )
            if deadline:
                body += f"Deadline: {deadline}\n"
            _msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "UCAS",
                "priority":   "High",
                "status":     "Sent",
                "subject":    f"UCAS reference reminder — {name}",
                "body":       body,
                "to_address": referee,
                "student_id": sid,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent UCAS reference reminders for "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="ucas_reference_reminders", summary=summary_text,
        params={"deadline": deadline,
                "referee_email": referee_email},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk password-reset emails ─────────────────────────

def bulk_password_reset_emails(
    student_ids: list[str],
    *,
    reset_url: str | None = None,
    mfa_enrolment: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Send a password-reset (or MFA enrolment) email to each student."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    flow = "MFA enrolment" if mfa_enrolment else "Password reset"
    result = BulkResult(operation="password_reset_emails",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            st = _students.get_student(sid)
            email = getattr(st, "email", None) if st else None
            if not email:
                raise ValidationError("No email on file")
            body = (
                f"Hello,\n\n"
                f"A {flow.lower()} has been initiated for your account.\n"
            )
            if reset_url:
                body += f"\nFollow this link to continue: {reset_url}\n"
            else:
                body += ("\nPlease contact the IT office for the next "
                         "steps.\n")
            _msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "Administrative",
                "priority":   "High",
                "status":     "Sent",
                "subject":    f"{flow} — action required",
                "body":       body,
                "to_address": email,
                "student_id": sid,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent {flow} emails to "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="password_reset_emails", summary=summary_text,
        params={"reset_url": reset_url, "mfa_enrolment": mfa_enrolment},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk schedule message (future send) ────────────────

def bulk_schedule_message(
    student_ids: list[str],
    *,
    subject: str,
    body: str,
    send_at: str,
    channel: str = "Email",
    category: str = "General",
    priority: str = "Normal",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Queue a message per student with ``sent_at = send_at`` and
    ``status = 'Queued'`` — the existing message-dispatcher picks it
    up at or after that timestamp."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    result = BulkResult(operation="schedule_message",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _msg.create_message({
                "direction":  "Outgoing",
                "channel":    channel,
                "category":   category,
                "priority":   priority,
                "status":     "Queued",
                "subject":    subject,
                "body":       body,
                "student_id": sid,
                "sent_at":    send_at,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Queued {subject!r} for {send_at} → "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="schedule_message", summary=summary_text,
        params={"subject": subject, "send_at": send_at,
                "channel": channel, "category": category,
                "priority": priority},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk bursary award ─────────────────────────────────

def bulk_bursary_award(
    student_ids: list[str],
    *,
    bursary_type: str,
    amount_awarded: float,
    academic_year: str | None = None,
    eligibility_basis: str | None = None,
    decision_note: str | None = None,
    assessed_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.finance.bursaries import (
        bursaries as _br,
    )
    today = _dt.date.today().isoformat()
    result = BulkResult(operation="bursary_award",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _br.create_application({
                "student_id":        sid,
                "bursary_type":      bursary_type,
                "academic_year":     academic_year,
                "application_date":  today,
                "amount_requested":  amount_awarded,
                "amount_awarded":    amount_awarded,
                "eligibility_basis": eligibility_basis,
                "status":            "Approved",
                "assessed_by":       assessed_by,
                "assessed_on":       today,
                "decision_note":     decision_note,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Awarded {bursary_type} (£{amount_awarded:.2f}) to "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="bursary_award", summary=summary_text,
        params={"bursary_type": bursary_type,
                "amount_awarded": amount_awarded,
                "academic_year": academic_year,
                "eligibility_basis": eligibility_basis},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk raise invoices ────────────────────────────────

def bulk_raise_invoices(
    student_ids: list[str],
    *,
    description: str,
    category: str,
    amount: float,
    issued_date: str | None = None,
    due_date: str | None = None,
    academic_year: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.finance.fees import (
        fees as _fees,
    )
    issued = issued_date or _dt.date.today().isoformat()
    result = BulkResult(operation="raise_invoices",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _fees.create_item({
                "student_id":   sid,
                "description":  description,
                "category":     category,
                "amount":       amount,
                "issued_date":  issued,
                "due_date":     due_date,
                "academic_year": academic_year,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Raised £{amount:.2f} {category} invoice for "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="raise_invoices", summary=summary_text,
        params={"description": description, "category": category,
                "amount": amount, "issued_date": issued,
                "due_date": due_date,
                "academic_year": academic_year},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk fee discount / waiver ─────────────────────────

def bulk_fee_discount(
    student_ids: list[str],
    *,
    description: str,
    amount: float,
    category: str = "Other",
    issued_date: str | None = None,
    academic_year: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Apply a credit (negative-amount fee item) per student. Pass
    ``amount`` as a positive number; it's stored as a credit (-amount)."""
    if amount <= 0:
        raise ValidationError("Discount amount must be positive")
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.finance.fees import (
        fees as _fees,
    )
    issued = issued_date or _dt.date.today().isoformat()
    result = BulkResult(operation="fee_discount",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            _fees.create_item({
                "student_id":   sid,
                "description":  f"Discount: {description}",
                "category":     category,
                "amount":       -float(amount),
                "issued_date":  issued,
                "academic_year": academic_year,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Applied −£{amount:.2f} {category} credit to "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="fee_discount", summary=summary_text,
        params={"description": description, "amount": amount,
                "category": category, "issued_date": issued,
                "academic_year": academic_year},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk payment import from CSV ───────────────────────

def bulk_import_payments(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """CSV columns: fee_id, amount, paid_on, method, reference?, notes?."""
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.finance.fees import (
        fees as _fees,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        required = {"fee_id", "amount", "paid_on", "method"}
        missing = required - set(h.strip() for h in (reader.fieldnames or []))
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    result = BulkResult(operation="import_payments",
                         target_count=len(rows))
    if dry_run:
        return result
    for i, r in enumerate(rows, start=2):
        try:
            fee_id = int(r["fee_id"])
            _fees.create_payment(fee_id, {
                "amount":     r.get("amount"),
                "paid_on":    r.get("paid_on"),
                "method":     r.get("method"),
                "reference":  r.get("reference") or None,
                "notes":      r.get("notes") or None,
            })
            result.success_ids.append(f"L{i}:fee#{fee_id}")
        except Exception as e:
            result.failures.append((f"L{i}", str(e)))
    summary_text = (f"Imported {result.success_count}/{result.target_count} "
                    f"payments from {os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_payments", summary=summary_text,
        params={"csv_path": csv_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk financial statements (text) ───────────────────

def bulk_financial_statements(
    student_ids: list[str],
    *,
    output_dir: str,
    academic_year: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    import os
    targets = _validate_targets(student_ids)
    if not output_dir:
        raise ValidationError("output_dir is required")
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    from education_system.systems.sixth_form.domain.finance.fees import (
        fees as _fees,
    )
    result = BulkResult(operation="financial_statements",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            items = _fees.list_items(student_id=sid,
                                       academic_year=academic_year)
            total_charged = sum(getattr(i, "amount", 0) or 0 for i in items)
            lines = [
                f"Financial statement — {sid}",
                f"Academic year: {academic_year or 'All'}",
                f"Generated: {_dt.datetime.now().isoformat(sep=' ', timespec='seconds')}",
                "",
                "Fees:",
            ]
            for it in items:
                lines.append(
                    f"  #{it.fee_id:<5} {it.issued_date}  "
                    f"{it.category:<12}  £{it.amount or 0:>10.2f}  "
                    f"{it.description}"
                )
            lines.append("")
            lines.append(f"Total charged: £{total_charged:.2f}")
            path = os.path.join(output_dir, f"statement_{sid}.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            result.success_ids.append(f"{sid}:{path}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Wrote {result.success_count}/{result.target_count} "
                    f"financial statements to {output_dir}")
    result.job_id = _log_job(
        operation="financial_statements", summary=summary_text,
        params={"output_dir": output_dir,
                "academic_year": academic_year},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk exam entries ──────────────────────────────────

def bulk_exam_entries(
    student_ids: list[str],
    *,
    subject: str,
    exam_board: str,
    paper_code: str,
    season: str,
    year: int,
    tier: str | None = None,
    fee: float | None = None,
    candidate_no_prefix: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Create an exam entry per student. ``candidate_no_prefix`` (if
    set) is followed by a 4-digit zero-padded index."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _ee,
    )
    result = BulkResult(operation="exam_entries",
                         target_count=len(targets))
    if dry_run:
        return result
    for idx, sid in enumerate(targets, start=1):
        try:
            candidate_no = None
            if candidate_no_prefix:
                candidate_no = f"{candidate_no_prefix}{idx:04d}"
            _ee.create_entry({
                "student_id":   sid,
                "subject":      subject,
                "exam_board":   exam_board,
                "paper_code":   paper_code,
                "season":       season,
                "year":         year,
                "tier":         tier,
                "fee":          fee,
                "candidate_no": candidate_no,
                "status":       "Entered",
            })
            result.success_ids.append(
                f"{sid}{f':{candidate_no}' if candidate_no else ''}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Entered {result.success_count}/{result.target_count} students "
        f"for {subject} {paper_code} ({exam_board} {season} {year})"
    )
    result.job_id = _log_job(
        operation="exam_entries", summary=summary_text,
        params={"subject": subject, "exam_board": exam_board,
                "paper_code": paper_code, "season": season,
                "year": year, "tier": tier, "fee": fee,
                "candidate_no_prefix": candidate_no_prefix},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk exam access arrangements ──────────────────────

def bulk_exam_access_arrangements(
    student_ids: list[str],
    *,
    arrangement: str,
    description: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    approved_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Convenience wrapper around add_accommodation with
    category='Exam Access' for arrangements like '25% Extra Time',
    'Scribe', 'Reader', 'Rest Breaks'."""
    return bulk_add_accommodation(
        student_ids,
        name=arrangement, category="Exam Access",
        description=description, status="Active",
        start_date=start_date, end_date=end_date,
        approved_by=approved_by, ran_by=ran_by,
        dry_run=dry_run,
    )


# ── Operation: bulk export exam timetables (text) ─────────────────

def bulk_export_exam_timetables(
    student_ids: list[str],
    *,
    output_dir: str,
    year: int | None = None,
    season: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    import os
    targets = _validate_targets(student_ids)
    if not output_dir:
        raise ValidationError("output_dir is required")
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _ee,
    )
    result = BulkResult(operation="exam_timetables",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            entries = _ee.entries_for_student(sid)
            if year is not None:
                entries = [e for e in entries if e.year == year]
            if season:
                entries = [e for e in entries if e.season == season]
            lines = [
                f"Exam timetable — {sid}",
                f"Year: {year or 'All'} · Season: {season or 'All'}",
                f"Generated: {_dt.datetime.now().isoformat(sep=' ', timespec='seconds')}",
                "",
            ]
            for e in entries:
                lines.append(
                    f"  {e.year} {e.season:<8} "
                    f"{e.exam_board:<8} "
                    f"{e.paper_code:<12} "
                    f"{e.subject}  [{e.status}]"
                )
            path = os.path.join(output_dir, f"exams_{sid}.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            result.success_ids.append(f"{sid}:{path}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Wrote {result.success_count}/{result.target_count} "
                    f"exam timetables to {output_dir}")
    result.job_id = _log_job(
        operation="exam_timetables", summary=summary_text,
        params={"output_dir": output_dir, "year": year,
                "season": season},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: UCAS export predictions ────────────────────────────

def bulk_ucas_export_predictions(
    student_ids: list[str],
    *,
    output_path: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Write one CSV row per (student, subject, predicted-grade) for
    selected students. Output format is the columns UCAS bulk-loaders
    accept: student_id, subject, grade, confidence."""
    import csv as _csv
    import os
    targets = _validate_targets(student_ids)
    if not output_path:
        raise ValidationError("output_path is required")
    from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
        predicted_grades as _pred,
    )
    result = BulkResult(operation="ucas_export_predictions",
                         target_count=len(targets))
    if dry_run:
        return result
    rows_written = 0
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["student_id", "subject", "grade", "confidence"])
        for sid in targets:
            try:
                preds = _pred.predictions_for_student(sid)
                for p in preds:
                    w.writerow([sid, p.subject, p.grade, p.confidence])
                    rows_written += 1
                result.success_ids.append(f"{sid}:{len(preds)}")
            except Exception as e:
                result.failures.append((sid, str(e)))
    summary_text = (f"Exported {rows_written} prediction row(s) for "
                    f"{result.success_count}/{result.target_count} "
                    f"students → {output_path}")
    result.job_id = _log_job(
        operation="ucas_export_predictions", summary=summary_text,
        params={"output_path": output_path,
                "rows_written": rows_written},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: UCAS update application status ─────────────────────

def bulk_ucas_update_status(
    student_ids: list[str],
    *,
    status: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Update each student's UCAS application to the given app status."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.progression.ucas import (
        ucas as _ucas,
    )
    if status not in _ucas.APP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(_ucas.APP_STATUSES)}")
    result = BulkResult(operation="ucas_update_status",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            app = _ucas.get_application_for_student(sid)
            if app is None:
                raise ValidationError("No UCAS application")
            _ucas.update_application(app.application_id, {"status": status})
            result.success_ids.append(f"{sid}:app#{app.application_id}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Set UCAS status={status} on "
                    f"{result.success_count}/{result.target_count} apps")
    result.job_id = _log_job(
        operation="ucas_update_status", summary=summary_text,
        params={"status": status}, result=result, ran_by=ran_by,
    )
    return result


# ── Operation: promote year group ─────────────────────────────────

def bulk_promote_year_group(
    student_ids: list[str],
    *,
    new_academic_year: str,
    bump_year_group: bool = True,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Create a new enrolment row for each student in the next academic
    year. If ``bump_year_group`` is True, year_group goes up by one
    (clamped to a max of 13)."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _en,
    )
    result = BulkResult(operation="promote_year_group",
                         target_count=len(targets))
    if dry_run:
        for sid in targets:
            try:
                cur = _en.list_for_student(sid)
                if not cur:
                    result.failures.append((sid, "No prior enrolment"))
                    continue
                latest = cur[0]
                new_yg = (min(latest.year_group + 1, 13)
                          if bump_year_group else latest.year_group)
                result.success_ids.append(
                    f"{sid}: Y{latest.year_group} → Y{new_yg} "
                    f"({new_academic_year})")
            except Exception as e:
                result.failures.append((sid, str(e)))
        return result
    for sid in targets:
        try:
            current = _en.list_for_student(sid)
            if not current:
                raise ValidationError("No prior enrolment")
            latest = current[0]  # list is ordered most-recent first
            new_yg = (min(latest.year_group + 1, 13)
                      if bump_year_group else latest.year_group)
            _en.create_enrolment({
                "student_id":    sid,
                "academic_year": new_academic_year,
                "year_group":    new_yg,
                "tutor_group":   latest.tutor_group,
                "start_date":    _dt.date.today().isoformat(),
                "status":        "Enrolled",
            })
            result.success_ids.append(f"{sid}:Y{latest.year_group}→Y{new_yg}")
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Promoted {result.success_count}/"
                    f"{result.target_count} students into "
                    f"{new_academic_year}")
    result.job_id = _log_job(
        operation="promote_year_group", summary=summary_text,
        params={"new_academic_year": new_academic_year,
                "bump_year_group": bump_year_group},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: mark leavers (Withdrawn) ───────────────────────────

def bulk_mark_leavers(
    student_ids: list[str],
    *,
    leaving_date: str,
    leaving_reason: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flag students as Withdrawn on their most-recent enrolment row,
    without archiving them to alumni."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _en,
    )
    result = BulkResult(operation="mark_leavers",
                         target_count=len(targets))
    if dry_run:
        for sid in targets:
            try:
                rows = _en.list_for_student(sid)
                if not rows:
                    result.failures.append(
                        (sid, "No enrolment to update"))
                    continue
                latest = rows[0]
                result.success_ids.append(
                    f"{sid}: {latest.status} → Withdrawn "
                    f"(left {leaving_date})")
            except Exception as e:
                result.failures.append((sid, str(e)))
        return result
    note_base = (f"Left {leaving_date}"
                 + (f": {leaving_reason}" if leaving_reason else ""))
    for sid in targets:
        try:
            rows = _en.list_for_student(sid)
            if not rows:
                raise ValidationError("No enrolment to update")
            latest = rows[0]
            _en.update_enrolment(latest.enrolment_id, {
                "academic_year": latest.academic_year,
                "year_group":    latest.year_group,
                "tutor_group":   latest.tutor_group,
                "start_date":    latest.start_date,
                "status":        "Withdrawn",
                "notes":         ((latest.notes + " | " + note_base)
                                   if latest.notes else note_base),
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Marked {result.success_count}/{result.target_count} "
                    f"students Withdrawn ({leaving_date})")
    result.job_id = _log_job(
        operation="mark_leavers", summary=summary_text,
        params={"leaving_date": leaving_date,
                "leaving_reason": leaving_reason},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: reinstate alumni → active student ──────────────────

def bulk_reinstate_alumni(
    alumni_ids: list[int],
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Delete alumni rows and (if the student row was also removed)
    recreate a minimal students row from the alumnus's stored fields."""
    if not alumni_ids:
        raise ValidationError("Pick at least one alumnus")
    str_targets = _validate_targets([str(a_) for a_ in alumni_ids])
    from education_system.systems.sixth_form.domain.learners.alumni import (
        alumni as _al,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="reinstate_alumni",
                         target_count=len(str_targets))
    if dry_run:
        return result
    for tag in str_targets:
        try:
            aid = int(tag)
            alum = _al.get_alumnus(aid)
            if alum is None:
                raise ValidationError(f"No alumnus #{aid}")
            sid = alum.original_student_id
            if sid and _students.get_student(sid) is None:
                # Recreate minimum-viable student row.
                _students.create_student({
                    "first_name": alum.first_name,
                    "last_name":  alum.last_name,
                    "subject_1":  "Mathematics",
                    "subject_2":  "Biology",
                    "subject_3":  "Chemistry",
                })
            _al.delete_alumnus(aid) if hasattr(_al, "delete_alumnus") \
                else _al.anonymise_alumnus(aid)
            result.success_ids.append(f"alum#{aid}→{sid or 'new'}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (f"Reinstated {result.success_count}/"
                    f"{result.target_count} alumni")
    result.job_id = _log_job(
        operation="reinstate_alumni", summary=summary_text,
        params={"alumni_ids": [int(t) for t in str_targets]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: GDPR redact PII fields on students ─────────────────

def bulk_gdpr_redact(
    student_ids: list[str],
    *,
    fields: list[str] | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Clear personal data from selected students. Default fields:
    ``phone, personal_email, emergency_contact_*``."""
    targets = _validate_targets(student_ids)
    default_fields = ["phone", "personal_email",
                      "emergency_contact_name",
                      "emergency_contact_phone",
                      "emergency_contact_relation"]
    fields = fields or default_fields
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="gdpr_redact",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            existing = _students.get_student(sid)
            if existing is None:
                raise ValidationError(f"No student with id {sid}")
            payload = {
                "first_name":  existing.first_name,
                "middle_name": existing.middle_name,
                "last_name":   existing.last_name,
                "phone":       existing.phone,
                "personal_email": getattr(existing, "personal_email",
                                            None),
                "emergency_contact_name":     existing.emergency_contact_name,
                "emergency_contact_phone":    existing.emergency_contact_phone,
                "emergency_contact_relation": existing.emergency_contact_relation,
                "subject_1": existing.subject_1,
                "subject_2": existing.subject_2,
                "subject_3": existing.subject_3,
            }
            for f in fields:
                if f in payload:
                    payload[f] = None
            _students.update_student(sid, payload)
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Redacted {', '.join(fields)} on "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="gdpr_redact", summary=summary_text,
        params={"fields": fields}, result=result, ran_by=ran_by,
    )
    return result


# ── Operation: export student records CSV ─────────────────────────

def bulk_export_student_records(
    student_ids: list[str],
    *,
    output_path: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Write one CSV row per student with their core record fields."""
    import csv as _csv
    import os
    targets = _validate_targets(student_ids)
    if not output_path:
        raise ValidationError("output_path is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="export_student_records",
                         target_count=len(targets))
    if dry_run:
        return result
    cols = ["student_id", "first_name", "middle_name", "last_name",
            "email", "phone",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation",
            "subject_1", "subject_2", "subject_3"]
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(cols)
        for sid in targets:
            try:
                st = _students.get_student(sid)
                if st is None:
                    raise ValidationError("Not found")
                w.writerow([getattr(st, c, "") or "" for c in cols])
                result.success_ids.append(sid)
            except Exception as e:
                result.failures.append((sid, str(e)))
    summary_text = (f"Exported {result.success_count}/{result.target_count} "
                    f"student records → {output_path}")
    result.job_id = _log_job(
        operation="export_student_records", summary=summary_text,
        params={"output_path": output_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: anonymise alumni ───────────────────────────────────

def bulk_anonymise_alumni(
    alumni_ids: list[int],
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    if not alumni_ids:
        raise ValidationError("Pick at least one alumnus")
    str_targets = _validate_targets([str(a_) for a_ in alumni_ids])
    from education_system.systems.sixth_form.domain.learners.alumni import (
        alumni as _al,
    )
    result = BulkResult(operation="anonymise_alumni",
                         target_count=len(str_targets))
    if dry_run:
        return result
    for tag in str_targets:
        try:
            _al.anonymise_alumnus(int(tag))
            result.success_ids.append(f"alum#{tag}")
        except Exception as e:
            result.failures.append((tag, str(e)))
    summary_text = (f"Anonymised {result.success_count}/"
                    f"{result.target_count} alumni")
    result.job_id = _log_job(
        operation="anonymise_alumni", summary=summary_text,
        params={"alumni_ids": [int(t) for t in str_targets]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: assign inventory (locker / library card / ID) ──────

VALID_INVENTORY_KINDS: tuple[str, ...] = (
    "Locker", "Library Card", "ID Badge", "Bus Pass", "Other",
)


def bulk_assign_inventory(
    student_ids: list[str],
    *,
    kind: str,
    starting_number: int = 1,
    prefix: str = "",
    pad: int = 4,
    assigned_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Assign sequential inventory numbers (lockers, badges, etc.) to
    selected students. Numbers are zero-padded to ``pad`` digits."""
    targets = _validate_targets(student_ids)
    if kind not in VALID_INVENTORY_KINDS:
        raise ValidationError(
            f"kind must be one of: {', '.join(VALID_INVENTORY_KINDS)}")
    init_db()
    result = BulkResult(operation="assign_inventory",
                         target_count=len(targets))
    if dry_run:
        return result
    with _connect() as conn:
        for i, sid in enumerate(targets):
            try:
                ident = f"{prefix}{starting_number + i:0{pad}d}"
                conn.execute(
                    """INSERT INTO student_inventory
                          (student_id, kind, identifier, assigned_by)
                       VALUES (?, ?, ?, ?)""",
                    (sid, kind, ident, assigned_by),
                )
                result.success_ids.append(f"{sid}:{ident}")
            except Exception as e:
                result.failures.append((sid, str(e)))
        conn.commit()
    summary_text = (f"Assigned {result.success_count}/{result.target_count} "
                    f"{kind} numbers")
    result.job_id = _log_job(
        operation="assign_inventory", summary=summary_text,
        params={"kind": kind, "starting_number": starting_number,
                "prefix": prefix, "pad": pad},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: upload photos (ZIP, matched by student_id) ─────────

def bulk_upload_photos(
    zip_path: str,
    *,
    output_dir: str,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Extract image files named ``<student_id>.<ext>`` from a ZIP and
    copy each to ``output_dir/<student_id>.<ext>``. Only files matching
    an existing student id are accepted."""
    import os
    import zipfile
    if not zip_path or not os.path.isfile(zip_path):
        raise ValidationError(f"ZIP not found: {zip_path}")
    if not output_dir:
        raise ValidationError("output_dir is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    valid_ids = {s.student_id for s in _students.list_students()}
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        result = BulkResult(operation="upload_photos",
                             target_count=len(names))
        if dry_run:
            return result
        os.makedirs(output_dir, exist_ok=True)
        for name in names:
            try:
                base = os.path.basename(name)
                root, ext = os.path.splitext(base)
                if not ext:
                    raise ValidationError("no file extension")
                if root not in valid_ids:
                    raise ValidationError(f"unknown student id {root}")
                target = os.path.join(output_dir, base)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                result.success_ids.append(f"{root}:{target}")
            except Exception as e:
                result.failures.append((name, str(e)))
    summary_text = (f"Uploaded {result.success_count}/{result.target_count} "
                    f"photos from {os.path.basename(zip_path)}")
    result.job_id = _log_job(
        operation="upload_photos", summary=summary_text,
        params={"zip_path": zip_path, "output_dir": output_dir},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: import emergency contacts CSV ──────────────────────

def bulk_import_contacts_csv(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Update student emergency-contact fields from a CSV. Required:
    ``student_id``. Optional: ``phone, emergency_contact_name,
    emergency_contact_phone, emergency_contact_relation``."""
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    rows: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        if "student_id" not in (reader.fieldnames or []):
            raise ValidationError("CSV must have student_id column")
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    result = BulkResult(operation="import_contacts_csv",
                         target_count=len(rows))
    if dry_run:
        return result
    editable = ("phone", "emergency_contact_name",
                "emergency_contact_phone",
                "emergency_contact_relation")
    for i, r in enumerate(rows, start=2):
        sid = r.get("student_id", "")
        try:
            existing = _students.get_student(sid)
            if existing is None:
                raise ValidationError(f"No student with id {sid}")
            payload = {
                "first_name":  existing.first_name,
                "middle_name": existing.middle_name,
                "last_name":   existing.last_name,
                "phone":       existing.phone,
                "emergency_contact_name":     existing.emergency_contact_name,
                "emergency_contact_phone":    existing.emergency_contact_phone,
                "emergency_contact_relation": existing.emergency_contact_relation,
                "subject_1": existing.subject_1,
                "subject_2": existing.subject_2,
                "subject_3": existing.subject_3,
            }
            for k in editable:
                if k in r and r[k]:
                    payload[k] = r[k]
            _students.update_student(sid, payload)
            result.success_ids.append(f"L{i}:{sid}")
        except Exception as e:
            result.failures.append((f"L{i}:{sid}", str(e)))
    summary_text = (f"Updated contacts for "
                    f"{result.success_count}/{result.target_count} "
                    f"students from {os.path.basename(csv_path)}")
    result.job_id = _log_job(
        operation="import_contacts_csv", summary=summary_text,
        params={"csv_path": csv_path},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: force-password-reset flag ──────────────────────────

def bulk_force_password_reset(
    student_ids: list[str],
    *,
    reason: str | None = None,
    flagged_by: str | None = None,
    clear: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flag selected students so they must change their password on
    next login. If ``clear`` is True the flag is removed."""
    targets = _validate_targets(student_ids)
    init_db()
    result = BulkResult(operation="force_password_reset",
                         target_count=len(targets))
    if dry_run:
        return result
    with _connect() as conn:
        for sid in targets:
            try:
                if clear:
                    conn.execute(
                        "DELETE FROM password_reset_required "
                        "WHERE student_id = ?", (sid,))
                else:
                    conn.execute(
                        """INSERT INTO password_reset_required
                              (student_id, flagged_by, reason)
                           VALUES (?, ?, ?)
                           ON CONFLICT(student_id) DO UPDATE SET
                              flagged_at = datetime('now'),
                              flagged_by = excluded.flagged_by,
                              reason = excluded.reason""",
                        (sid, flagged_by, reason))
                result.success_ids.append(sid)
            except Exception as e:
                result.failures.append((sid, str(e)))
        conn.commit()
    word = "Cleared" if clear else "Flagged"
    summary_text = (f"{word} force-password-reset on "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="force_password_reset", summary=summary_text,
        params={"reason": reason, "clear": clear,
                "flagged_by": flagged_by},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: undo job (best-effort compensating action) ─────────

_UNDOABLE: tuple[str, ...] = (
    "log_behaviour", "mark_attendance", "apply_lateness",
    "issue_detentions", "award_merits", "escalate_behaviour",
    "publish_report_cards", "assign_inventory",
    "force_password_reset",
)


def bulk_undo_job(
    target_job_id: int,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Roll back side-effects of a previous job. Supported only for
    ops in ``_UNDOABLE``; for any other operation a single failure is
    recorded."""
    job = get_job(target_job_id)
    if job is None:
        raise ValidationError(f"No job #{target_job_id}")
    result = BulkResult(operation="undo_job",
                         target_count=job.target_count)
    if job.operation not in _UNDOABLE:
        result.failures.append(
            (str(target_job_id),
             f"Operation {job.operation!r} is not undoable"))
        if not dry_run:
            result.job_id = _log_job(
                operation="undo_job",
                summary=f"Attempted undo of job #{target_job_id} "
                        f"({job.operation}) — not undoable",
                params={"target_job_id": target_job_id,
                        "operation": job.operation},
                result=result, ran_by=ran_by)
        return result
    if dry_run:
        return result

    sids = [sid for sid in job.success_ids
            if isinstance(sid, str) and ":" not in sid
            and not sid.startswith("L")]
    op = job.operation
    # ran_at +/- a small window around when side-effects were created.
    ts = job.ran_at  # "YYYY-MM-DD HH:MM:SS"
    removed = 0
    try:
        if op in ("log_behaviour", "issue_detentions", "award_merits",
                   "escalate_behaviour", "apply_lateness"):
            import sqlite3 as _sq
            from education_system.systems.sixth_form.domain.pastoral.behaviour import (
                behaviour as _bh,
            )
            _bh.init_db()
            with _sq.connect(str(_bh.DB_PATH)) as conn:
                for sid in sids:
                    cur = conn.execute(
                        "DELETE FROM behaviour_entries "
                        "WHERE student_id = ? "
                        "AND datetime(created_at) "
                        "    BETWEEN datetime(?) "
                        "        AND datetime(?, '+10 seconds')",
                        (sid, ts, ts))
                    removed += cur.rowcount
                    result.success_ids.append(f"{sid}:−{cur.rowcount}")
                conn.commit()
        elif op == "mark_attendance":
            from education_system.systems.sixth_form.domain.academics.attendance import (
                attendance as _att,
            )
            slot_id = job.parameters.get("slot_id")
            date = job.parameters.get("date")
            for sid in sids:
                rows = _att.list_records(
                    student_id=sid, slot_id=slot_id, date=date)
                for r in rows:
                    if _att.delete_record(r.record_id):
                        removed += 1
                result.success_ids.append(f"{sid}:−{len(rows)}")
        elif op == "publish_report_cards":
            init_db()
            period = job.parameters.get("period")
            with _connect() as conn:
                for sid in sids:
                    cur = conn.execute(
                        "DELETE FROM report_card_publications "
                        "WHERE student_id = ? AND period = ?",
                        (sid, period))
                    removed += cur.rowcount
                    result.success_ids.append(f"{sid}:−{cur.rowcount}")
                conn.commit()
        elif op == "assign_inventory":
            init_db()
            with _connect() as conn:
                for entry in job.success_ids:
                    if ":" not in entry:
                        continue
                    sid, ident = entry.split(":", 1)
                    cur = conn.execute(
                        "DELETE FROM student_inventory "
                        "WHERE student_id = ? AND identifier = ?",
                        (sid, ident))
                    removed += cur.rowcount
                    result.success_ids.append(
                        f"{sid}:{ident} −{cur.rowcount}")
                conn.commit()
        elif op == "force_password_reset":
            init_db()
            with _connect() as conn:
                for sid in sids:
                    cur = conn.execute(
                        "DELETE FROM password_reset_required "
                        "WHERE student_id = ?", (sid,))
                    removed += cur.rowcount
                    result.success_ids.append(f"{sid}:−{cur.rowcount}")
                conn.commit()
    except Exception as e:  # noqa: BLE001
        result.failures.append((str(target_job_id), str(e)))

    summary_text = (f"Undid {removed} side-effect(s) from job "
                    f"#{target_job_id} ({op})")
    result.job_id = _log_job(
        operation="undo_job", summary=summary_text,
        params={"target_job_id": target_job_id,
                "operation": op, "rows_removed": removed},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: schedule recurring bulk job ────────────────────────

@dataclass
class Schedule:
    schedule_id: int
    name: str
    operation: str
    parameters: dict[str, Any]
    cron_expr: str
    enabled: bool
    next_run_at: str | None
    last_run_at: str | None
    last_job_id: int | None
    created_by: str | None
    created_at: str


def _row_schedule(r: sqlite3.Row) -> Schedule:
    try:
        params = json.loads(r["parameters"]) if r["parameters"] else {}
    except (TypeError, ValueError):
        params = {}
    return Schedule(
        schedule_id=r["schedule_id"], name=r["name"],
        operation=r["operation"], parameters=params,
        cron_expr=r["cron_expr"], enabled=bool(r["enabled"]),
        next_run_at=r["next_run_at"], last_run_at=r["last_run_at"],
        last_job_id=r["last_job_id"],
        created_by=r["created_by"], created_at=r["created_at"],
    )


def create_schedule(
    *,
    name: str,
    operation: str,
    parameters: dict[str, Any],
    cron_expr: str,
    next_run_at: str | None = None,
    created_by: str | None = None,
) -> Schedule:
    name = (name or "").strip()
    if not name:
        raise ValidationError("Schedule name is required")
    if operation not in OPERATIONS:
        raise ValidationError(
            f"Unknown operation {operation!r}")
    cron_expr = (cron_expr or "").strip()
    if not cron_expr:
        raise ValidationError("cron_expr is required")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO bulk_schedules
                  (name, operation, parameters, cron_expr,
                   enabled, next_run_at, created_by)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (name, operation, json.dumps(parameters, default=str),
             cron_expr, next_run_at, created_by),
        )
        conn.commit()
        sid = cur.lastrowid
    out = get_schedule(sid)
    assert out is not None
    return out


def get_schedule(schedule_id: int) -> Schedule | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM bulk_schedules WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
        return _row_schedule(r) if r else None


def list_schedules(*, enabled: bool | None = None) -> list[Schedule]:
    init_db()
    clauses, args = [], []
    if enabled is not None:
        clauses.append("enabled = ?")
        args.append(1 if enabled else 0)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM bulk_schedules {where} "
            "ORDER BY enabled DESC, schedule_id DESC",
            args).fetchall()
    return [_row_schedule(r) for r in rows]


def set_schedule_enabled(schedule_id: int, enabled: bool) -> Schedule:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE bulk_schedules SET enabled = ? "
            "WHERE schedule_id = ?",
            (1 if enabled else 0, schedule_id))
        conn.commit()
        if not cur.rowcount:
            raise ValidationError(f"No schedule #{schedule_id}")
    out = get_schedule(schedule_id)
    assert out is not None
    return out


def delete_schedule(schedule_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM bulk_schedules WHERE schedule_id = ?",
            (schedule_id,))
        conn.commit()
        return bool(cur.rowcount)


def bulk_schedule_recurring(
    *,
    name: str,
    operation: str,
    cron_expr: str,
    parameters: dict[str, Any] | None = None,
    next_run_at: str | None = None,
    created_by: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Persist a recurring bulk-job definition. An external scheduler
    (not implemented here) is expected to dispatch matching rows when
    ``next_run_at`` arrives. Reported as a single-target job."""
    if dry_run:
        return BulkResult(operation="schedule_recurring", target_count=1)
    sched = create_schedule(
        name=name, operation=operation,
        parameters=parameters or {}, cron_expr=cron_expr,
        next_run_at=next_run_at, created_by=created_by,
    )
    result = BulkResult(operation="schedule_recurring", target_count=1)
    result.success_ids.append(f"schedule#{sched.schedule_id}:{sched.name}")
    result.job_id = _log_job(
        operation="schedule_recurring",
        summary=(f"Created schedule #{sched.schedule_id} {name!r} "
                 f"({operation} @ {cron_expr})"),
        params={"name": name, "operation": operation,
                "cron_expr": cron_expr,
                "parameters": parameters or {},
                "next_run_at": next_run_at},
        result=result, ran_by=ran_by,
    )
    return result


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM bulk_jobs").fetchone()[0]
        by_op: dict[str, int] = {o: 0 for o in OPERATIONS}
        for r in conn.execute(
                "SELECT operation, COUNT(*) n FROM bulk_jobs "
                "GROUP BY operation").fetchall():
            by_op[r["operation"]] = r["n"]
        totals = conn.execute(
            "SELECT COALESCE(SUM(target_count), 0) tt, "
            "       COALESCE(SUM(success_count), 0) ts, "
            "       COALESCE(SUM(failure_count), 0) tf "
            "FROM bulk_jobs").fetchone()
        most_recent = conn.execute(
            "SELECT ran_at FROM bulk_jobs "
            "ORDER BY ran_at DESC LIMIT 1").fetchone()
    return Summary(
        total_jobs=total,
        by_operation=by_op,
        total_targets=totals["tt"] or 0,
        total_successes=totals["ts"] or 0,
        total_failures=totals["tf"] or 0,
        most_recent_ts=most_recent["ran_at"] if most_recent else None,
    )


# ──────────────────────────────────────────────────────────────────
# Items 1–10 from the "50 more bulk operations" wishlist
# ──────────────────────────────────────────────────────────────────

# ── Operation: bulk mark holiday ──────────────────────────────────

def bulk_mark_holiday(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    reason: str = "Authorised holiday",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Mark a date range as Authorised absence for selected students.

    For every weekday in ``[date_from, date_to]`` we look up the
    timetable slots that run on that weekday and stamp an Authorised
    record (with ``reason`` in notes) for each selected student. Any
    existing Absent / Late record in the window for those students is
    flipped to Authorised as well.
    """
    targets = _validate_targets(student_ids)
    dates = _daterange(date_from, date_to)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    result = BulkResult(operation="mark_holiday", target_count=len(targets))
    if dry_run:
        return _preview_targets(
            result, targets,
            verb=f"authorise {len(dates)} day(s) ({date_from}..{date_to})")

    # Group slots by day-of-week (1=Mon..7=Sun) once.
    slots_by_day: dict[int, list[Any]] = {}
    try:
        for s in _tt.list_slots():
            slots_by_day.setdefault(s.day, []).append(s)
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, f"Could not load timetable: {e}"))
        summary_text = (f"Mark holiday failed: timetable unreadable "
                        f"({date_from}..{date_to})")
        result.job_id = _log_job(
            operation="mark_holiday", summary=summary_text,
            params={"date_from": date_from, "date_to": date_to,
                    "reason": reason}, result=result, ran_by=ran_by,
        )
        return result

    written = 0
    converted = 0
    for sid in targets:
        try:
            for date in dates:
                weekday = _dt.date.fromisoformat(date).weekday() + 1
                day_slots = slots_by_day.get(weekday, [])
                for s in day_slots:
                    try:
                        _att.save_register(
                            s.slot_id, date,
                            {sid: {"status": "Authorised",
                                   "minutes_late": None,
                                   "notes": reason}},
                        )
                        written += 1
                    except Exception as e:  # noqa: BLE001
                        # Per-slot failure — keep going for the rest.
                        log_event(
                            logging.WARNING,
                            f"mark_holiday: slot #{s.slot_id} {date} "
                            f"failed for {sid}: {e}",
                            operation="mark_holiday")
                # Convert any *other* records on this date (e.g. Absent
                # marks already entered before the holiday was approved).
                existing = _att.list_records(
                    student_id=sid, date_from=date, date_to=date)
                for rec in existing:
                    if rec.status in ("Absent", "Late"):
                        merged = (
                            f"{rec.notes} | {reason}".strip(" |")
                            if rec.notes else reason)
                        _att.update_record(rec.record_id, {
                            "status": "Authorised",
                            "minutes_late": None,
                            "notes": merged,
                        })
                        converted += 1
            result.success_ids.append(sid)
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    summary_text = (
        f"Marked holiday for {result.success_count}/{result.target_count} "
        f"students ({date_from}..{date_to}); "
        f"wrote {written} authorised row(s), converted {converted} existing"
    )
    result.job_id = _log_job(
        operation="mark_holiday", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "reason": reason, "written": written,
                "converted": converted},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk clear attendance ──────────────────────────────

def bulk_clear_attendance(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    only_status: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Delete attendance rows in a date range for register correction.

    If ``only_status`` is given (Present/Late/Absent/Authorised) the
    deletion is restricted to that status — useful when reverting a
    mis-keyed register without nuking the surrounding marks.
    """
    targets = _validate_targets(student_ids)
    _daterange(date_from, date_to)  # validates the range
    if only_status is not None and only_status not in (
            "Present", "Late", "Absent", "Authorised"):
        raise ValidationError(
            "only_status must be Present/Late/Absent/Authorised")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="clear_attendance",
                        target_count=len(targets))
    if dry_run:
        # Count what we'd delete without doing it.
        for sid in targets:
            try:
                rows = _att.list_records(
                    student_id=sid,
                    date_from=date_from, date_to=date_to,
                    status=only_status,
                )
                result.success_ids.append(f"{sid}: would delete {len(rows)}")
            except Exception as e:  # noqa: BLE001
                result.failures.append((sid, str(e)))
        return result
    total_deleted = 0
    for sid in targets:
        try:
            rows = _att.list_records(
                student_id=sid,
                date_from=date_from, date_to=date_to,
                status=only_status,
            )
            n = 0
            for rec in rows:
                if _att.delete_record(rec.record_id):
                    n += 1
            total_deleted += n
            result.success_ids.append(f"{sid}:-{n}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    summary_text = (
        f"Cleared {total_deleted} attendance row(s) for "
        f"{result.success_count}/{result.target_count} students "
        f"({date_from}..{date_to}"
        + (f", status={only_status}" if only_status else "") + ")"
    )
    result.job_id = _log_job(
        operation="clear_attendance", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "only_status": only_status, "deleted": total_deleted},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk convert Late→Unauthorised over threshold ──────

def bulk_late_to_unauth(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    over_minutes: int = 15,
    reason: str | None = "Late > threshold — unauthorised",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Flip Late records with ``minutes_late > over_minutes`` to Absent."""
    targets = _validate_targets(student_ids)
    _daterange(date_from, date_to)
    try:
        over_minutes = int(over_minutes)
    except (TypeError, ValueError):
        raise ValidationError("over_minutes must be a number") from None
    if over_minutes < 0 or over_minutes > 1000:
        raise ValidationError("over_minutes must be 0..1000")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="late_to_unauth",
                        target_count=len(targets))
    converted = 0
    for sid in targets:
        try:
            rows = _att.list_records(
                student_id=sid, status="Late",
                date_from=date_from, date_to=date_to,
            )
            qualifying = [r for r in rows
                          if (r.minutes_late or 0) > over_minutes]
            if dry_run:
                result.success_ids.append(
                    f"{sid}: would convert {len(qualifying)}")
                continue
            for rec in qualifying:
                merged = (f"{rec.notes} | {reason}".strip(" |")
                          if rec.notes and reason else (reason or rec.notes))
                _att.update_record(rec.record_id, {
                    "status": "Absent",
                    "minutes_late": None,
                    "notes": merged,
                })
                converted += 1
            result.success_ids.append(f"{sid}:-{len(qualifying)}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    if dry_run:
        return result
    summary_text = (
        f"Converted {converted} Late→Absent row(s) (>{over_minutes} min) "
        f"for {result.success_count}/{result.target_count} students "
        f"({date_from}..{date_to})"
    )
    result.job_id = _log_job(
        operation="late_to_unauth", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "over_minutes": over_minutes, "reason": reason,
                "converted": converted},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk attendance letters ────────────────────────────

# Default thresholds — anything ≥ stage1 gets no letter; below stage1 →
# stage 1, below stage2 → stage 2, etc.
DEFAULT_ATTENDANCE_STAGES: tuple[tuple[float, str], ...] = (
    (95.0, "Stage 1"),
    (90.0, "Stage 2"),
    (85.0, "Stage 3"),
)


def bulk_attendance_letters(
    student_ids: list[str],
    *,
    window_days: int = 28,
    stages: tuple[tuple[float, str], ...] | None = None,
    send: bool = True,
    sender_staff_id: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Generate stage-tiered attendance warning letters.

    For each student we compute attendance % over the last
    ``window_days`` days. Students above every stage threshold get no
    letter; everyone else gets a message tagged with the stage label.
    """
    targets = _validate_targets(student_ids)
    try:
        window_days = int(window_days)
    except (TypeError, ValueError):
        raise ValidationError("window_days must be numeric") from None
    if window_days <= 0 or window_days > 365:
        raise ValidationError("window_days must be 1..365")
    tiers = list(stages or DEFAULT_ATTENDANCE_STAGES)
    if not tiers:
        raise ValidationError("At least one stage tier is required")
    # Tiers must be sorted high → low so we pick the *first* match below.
    tiers.sort(key=lambda t: -float(t[0]))

    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )

    end = _dt.date.today()
    start = end - _dt.timedelta(days=window_days)
    df, dt = start.isoformat(), end.isoformat()

    result = BulkResult(operation="attendance_letters",
                        target_count=len(targets))

    # Bucket students by stage.
    by_stage: dict[str, list[tuple[str, float]]] = {}
    for sid in targets:
        try:
            s = _att.summary_for_student(sid, date_from=df, date_to=dt)
            pct = s.percentage
            if pct is None or s.total == 0:
                result.success_ids.append(f"{sid}:no-data")
                continue
            stage_label: str | None = None
            for threshold, label in tiers:
                if pct < threshold:
                    stage_label = label
                else:
                    break
            if stage_label is None:
                result.success_ids.append(f"{sid}:above-thresholds@{pct}%")
                continue
            by_stage.setdefault(stage_label, []).append((sid, pct))
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    if dry_run:
        for stage, rows in by_stage.items():
            for sid, pct in rows:
                result.success_ids.append(f"{sid}:{stage}@{pct}%")
        return result

    sent_total = 0
    if send:
        for stage, rows in by_stage.items():
            sids = [r[0] for r in rows]
            subject = f"Attendance — {stage}"
            body = (
                f"This is an automated {stage} attendance letter.\n\n"
                f"Your attendance over the last {window_days} day(s) has "
                f"fallen below the threshold set by the sixth form. Please "
                f"speak to your tutor about steps to improve.\n\n"
                f"This is generated by Bulk Operations."
            )
            try:
                br = _msg.bulk_send(
                    subject=subject, body=body,
                    student_ids=sids,
                    category="Attendance", priority="High",
                    status="Sent",
                    sender_staff_id=sender_staff_id,
                    tags=f"attendance,{stage.lower().replace(' ', '_')}",
                )
                for m in br.created:
                    sid = getattr(m, "student_id", None)
                    if sid:
                        result.success_ids.append(f"{sid}:{stage}-sent")
                        sent_total += 1
                for label, reason in br.failed:
                    result.failures.append((label, reason))
            except Exception as e:  # noqa: BLE001
                for sid in sids:
                    result.failures.append((sid, str(e)))
    else:
        for stage, rows in by_stage.items():
            for sid, pct in rows:
                result.success_ids.append(f"{sid}:{stage}@{pct}%-queued")

    summary_text = (
        f"Attendance letters: {sent_total if send else 0} sent across "
        + ", ".join(f"{s}×{len(v)}" for s, v in by_stage.items())
        + f" ({window_days}-day window)"
    )
    result.job_id = _log_job(
        operation="attendance_letters", summary=summary_text,
        params={"window_days": window_days,
                "stages": [(t, l) for t, l in tiers],
                "send": send, "sent_total": sent_total,
                "buckets": {k: len(v) for k, v in by_stage.items()}},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk punctuality report (to tutors) ────────────────

def bulk_punctuality_report(
    student_ids: list[str],
    *,
    date_from: str,
    date_to: str,
    sender_staff_id: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Email each tutor a punctuality breakdown for their tutees.

    For each student we count Late records and the average
    minutes_late in the window. Students are grouped by their current
    tutor group; one message per tutor goes out via the messages
    module to that tutor's staff id (if the tutor group's ``tutor``
    field looks like a staff id). Students without a tutor group are
    surfaced as failures so they don't get silently dropped.
    """
    targets = _validate_targets(student_ids)
    _daterange(date_from, date_to)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as _msg,
    )
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _tg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )

    result = BulkResult(operation="punctuality_report",
                        target_count=len(targets))

    # Aggregate per student: total Late + average minutes_late.
    per_student: dict[str, tuple[int, float, str | None]] = {}
    for sid in targets:
        try:
            student = _students.get_student(sid)
            if student is None:
                result.failures.append((sid, "Unknown student"))
                continue
            rows = _att.list_records(
                student_id=sid, status="Late",
                date_from=date_from, date_to=date_to,
            )
            n = len(rows)
            avg = (sum(r.minutes_late or 0 for r in rows) / n) if n else 0.0
            per_student[sid] = (n, round(avg, 1), student.full_name)
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    # Group by tutor.
    buckets: dict[str, list[tuple[str, int, float, str]]] = {}
    no_tutor: list[str] = []
    for sid, (lates, avg, name) in per_student.items():
        try:
            grp = _tg.group_for_student(sid)
        except Exception:  # noqa: BLE001
            grp = None
        tutor_id = (grp.tutor if grp else None) or None
        if not tutor_id:
            no_tutor.append(sid)
            continue
        buckets.setdefault(tutor_id, []).append(
            (sid, lates, avg, name or sid))

    if dry_run:
        for tutor, rows in buckets.items():
            result.success_ids.append(
                f"tutor {tutor}: would email {len(rows)} student(s)")
        for sid in no_tutor:
            result.success_ids.append(f"{sid}:no-tutor")
        return result

    sent = 0
    for tutor, rows in buckets.items():
        rows.sort(key=lambda r: (-r[1], r[3]))  # late-count desc, name
        body_lines = [
            f"Punctuality report ({date_from}..{date_to})",
            "",
            f"{'Student':<24} {'Lates':>6} {'Avg min':>9}",
            "-" * 42,
        ]
        for sid, lates, avg, name in rows:
            body_lines.append(f"{(name[:23]):<24} {lates:>6} {avg:>9}")
        body = "\n".join(body_lines)
        try:
            br = _msg.bulk_send(
                subject=f"Punctuality report — {date_from}..{date_to}",
                body=body,
                staff_ids=[tutor],
                category="Attendance", priority="Normal",
                status="Sent",
                sender_staff_id=sender_staff_id,
                tags="punctuality_report",
            )
            for m in br.created:
                sent += 1
                result.success_ids.append(
                    f"tutor {tutor}: {len(rows)} student(s)")
            for label, reason in br.failed:
                result.failures.append((label, reason))
        except Exception as e:  # noqa: BLE001
            result.failures.append((f"tutor {tutor}", str(e)))

    for sid in no_tutor:
        result.failures.append((sid, "Student has no tutor group"))

    summary_text = (
        f"Punctuality report: emailed {sent} tutor(s) covering "
        f"{sum(len(v) for v in buckets.values())} student(s) "
        f"({date_from}..{date_to}); "
        f"{len(no_tutor)} student(s) skipped (no tutor)"
    )
    result.job_id = _log_job(
        operation="punctuality_report", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "tutors": list(buckets.keys()),
                "no_tutor": no_tutor},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk register closure (lock past registers) ─────────

def bulk_register_closure(
    slot_ids: list[int],
    *,
    date_from: str,
    date_to: str,
    default_status: str = "Present",
    notes: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """For each (slot, date) in the window, ensure blanks are filled
    with ``default_status`` and then record a closure row so the
    register is "locked" — :func:`is_register_closed` can be queried
    by other modules before letting a user edit it.
    """
    if not slot_ids:
        raise ValidationError("Pick at least one slot")
    str_targets = _validate_targets([str(s) for s in slot_ids])
    dates = _daterange(date_from, date_to)
    today = _dt.date.today()
    if any(_dt.date.fromisoformat(d) > today for d in dates):
        raise ValidationError(
            "Cannot close registers in the future — pick a date range "
            "that ends on or before today")
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as _att,
    )
    result = BulkResult(operation="register_closure",
                        target_count=len(str_targets) * len(dates))
    if dry_run:
        for tag in str_targets:
            for date in dates:
                result.success_ids.append(
                    f"slot#{tag} {date}: would close")
        return result
    init_db()
    filled = 0
    closed = 0
    skipped_existing = 0
    for tag in str_targets:
        try:
            slot_id = int(tag)
        except ValueError:
            result.failures.append((tag, "slot_id not numeric"))
            continue
        for date in dates:
            try:
                roster = _att.register_view(slot_id, date)
                missing = {
                    e.student_id: {"status": default_status,
                                   "minutes_late": None,
                                   "notes": "Auto-filled at closure"}
                    for e in roster if e.record is None
                }
                if missing:
                    _att.save_register(slot_id, date, missing)
                    filled += len(missing)
                with _connect() as conn:
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO register_closures "
                        "(slot_id, date, closed_by, notes) "
                        "VALUES (?, ?, ?, ?)",
                        (slot_id, date, ran_by, notes),
                    )
                    conn.commit()
                    if cur.rowcount:
                        closed += 1
                        result.success_ids.append(
                            f"slot#{slot_id} {date}: closed (+{len(missing)})")
                    else:
                        skipped_existing += 1
                        result.success_ids.append(
                            f"slot#{slot_id} {date}: already closed")
            except Exception as e:  # noqa: BLE001
                result.failures.append((f"slot#{tag} {date}", str(e)))
    summary_text = (
        f"Closed {closed} (slot, date) register(s); "
        f"filled {filled} blank entry(ies); "
        f"{skipped_existing} already closed "
        f"({date_from}..{date_to})"
    )
    result.job_id = _log_job(
        operation="register_closure", summary=summary_text,
        params={"date_from": date_from, "date_to": date_to,
                "default_status": default_status,
                "slot_ids": [int(t) for t in str_targets],
                "closed": closed, "filled": filled,
                "skipped_existing": skipped_existing,
                "notes": notes},
        result=result, ran_by=ran_by,
    )
    return result


def is_register_closed(slot_id: int, date: str) -> bool:
    """Lookup helper — has this (slot, date) register been closed?"""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM register_closures "
            "WHERE slot_id = ? AND date = ?",
            (slot_id, date),
        ).fetchone()
        return row is not None


# ── Operation: bulk assign subjects ───────────────────────────────

def bulk_assign_subjects(
    student_ids: list[str],
    *,
    subjects: list[str],
    overwrite: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Place ``subjects`` into the students' three subject slots.

    By default, only empty slots are filled (so existing subjects are
    preserved and not silently duplicated). With ``overwrite=True``,
    the supplied list replaces the slots wholesale (any missing
    positions are blanked).
    """
    targets = _validate_targets(student_ids)
    if not subjects:
        raise ValidationError("Pick at least one subject")
    # De-dup while preserving order; cap at 3 to match the schema.
    seen: set[str] = set()
    cleaned: list[str] = []
    for s in subjects:
        ss = (s or "").strip()
        if not ss or ss.lower() in seen:
            continue
        seen.add(ss.lower())
        cleaned.append(ss)
    if not cleaned:
        raise ValidationError("No valid subjects supplied")
    if len(cleaned) > 3:
        raise ValidationError(
            "Students can hold at most 3 subjects (subject_1..subject_3)")

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as _sub,
    )
    # Validate against the active subject catalogue (warn-only — if
    # the catalogue is empty we accept whatever was typed).
    try:
        active = {n.lower() for n in _sub.get_active_names()}
    except Exception:  # noqa: BLE001
        active = set()
    unknown = [c for c in cleaned if active and c.lower() not in active]
    if unknown and active:
        raise ValidationError(
            f"Unknown subject(s): {', '.join(unknown)}. "
            f"Active: {', '.join(sorted(active))}")

    result = BulkResult(operation="assign_subjects",
                        target_count=len(targets))

    for sid in targets:
        try:
            student = _students.get_student(sid)
            if student is None:
                result.failures.append((sid, "Unknown student"))
                continue
            current = [student.subject_1, student.subject_2, student.subject_3]
            if overwrite:
                new_slots: list[str | None] = list(cleaned) + [None] * (
                    3 - len(cleaned))
            else:
                new_slots = list(current)
                for incoming in cleaned:
                    if any(
                        (c or "").lower() == incoming.lower()
                        for c in new_slots
                    ):
                        continue  # already present
                    free = next(
                        (i for i, c in enumerate(new_slots) if not c),
                        None)
                    if free is None:
                        # All 3 slots full and not overwriting.
                        result.failures.append(
                            (sid, f"All subject slots full — cannot add "
                                  f"{incoming}"))
                        new_slots = current  # leave unchanged
                        break
                    new_slots[free] = incoming
                else:
                    pass
            if new_slots == current:
                result.success_ids.append(f"{sid}: (no change)")
                continue
            if dry_run:
                result.success_ids.append(
                    f"{sid}: {tuple(current)} → {tuple(new_slots)}")
                continue
            payload = {
                "first_name":                 student.first_name,
                "middle_name":                student.middle_name,
                "last_name":                  student.last_name,
                "phone":                      student.phone,
                "emergency_contact_name":     student.emergency_contact_name,
                "emergency_contact_phone":    student.emergency_contact_phone,
                "emergency_contact_relation": student.emergency_contact_relation,
                "subject_1":                  new_slots[0],
                "subject_2":                  new_slots[1],
                "subject_3":                  new_slots[2],
            }
            _students.update_student(sid, payload)
            result.success_ids.append(f"{sid}: {tuple(new_slots)}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))

    if dry_run:
        return result
    summary_text = (
        f"Assigned subjects {cleaned!r} (overwrite={overwrite}) to "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="assign_subjects", summary=summary_text,
        params={"subjects": cleaned, "overwrite": overwrite},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk withdraw subjects ─────────────────────────────

def bulk_withdraw_subjects(
    student_ids: list[str],
    *,
    subjects: list[str],
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Remove ``subjects`` from the students' subject slots."""
    targets = _validate_targets(student_ids)
    if not subjects:
        raise ValidationError("Pick at least one subject to withdraw")
    drop = {(s or "").strip().lower()
            for s in subjects if (s or "").strip()}
    if not drop:
        raise ValidationError("No valid subjects supplied")

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    result = BulkResult(operation="withdraw_subjects",
                        target_count=len(targets))
    for sid in targets:
        try:
            student = _students.get_student(sid)
            if student is None:
                result.failures.append((sid, "Unknown student"))
                continue
            current = [student.subject_1, student.subject_2, student.subject_3]
            new_slots = [
                None if (c or "").lower() in drop else c
                for c in current
            ]
            if new_slots == current:
                result.success_ids.append(f"{sid}: (none of those held)")
                continue
            if dry_run:
                result.success_ids.append(
                    f"{sid}: {tuple(current)} → {tuple(new_slots)}")
                continue
            payload = {
                "first_name":                 student.first_name,
                "middle_name":                student.middle_name,
                "last_name":                  student.last_name,
                "phone":                      student.phone,
                "emergency_contact_name":     student.emergency_contact_name,
                "emergency_contact_phone":    student.emergency_contact_phone,
                "emergency_contact_relation": student.emergency_contact_relation,
                "subject_1":                  new_slots[0],
                "subject_2":                  new_slots[1],
                "subject_3":                  new_slots[2],
            }
            _students.update_student(sid, payload)
            removed = [c for c in current
                       if (c or "").lower() in drop]
            result.success_ids.append(
                f"{sid}: dropped {tuple(removed)}")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    if dry_run:
        return result
    summary_text = (
        f"Withdrew subjects {list(drop)!r} from "
        f"{result.success_count}/{result.target_count} students"
    )
    result.job_id = _log_job(
        operation="withdraw_subjects", summary=summary_text,
        params={"subjects": sorted(drop)},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk set teaching set ──────────────────────────────

def bulk_set_teaching_set(
    student_ids: list[str],
    *,
    target_group_id: int,
    course_id: int | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Move students into ``target_group_id``, removing them first from
    any *other* group on the same course (so teaching sets don't
    silently overlap).

    If ``course_id`` is not given, it's inferred from ``target_group_id``.
    """
    targets = _validate_targets(student_ids)
    try:
        target_group_id = int(target_group_id)
    except (TypeError, ValueError):
        raise ValidationError("target_group_id must be numeric") from None

    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    target = _cg.get_group(target_group_id)
    if target is None:
        raise ValidationError(
            f"No class group with id {target_group_id}")
    course_id = course_id or getattr(target, "course_id", None)
    if course_id is None:
        raise ValidationError(
            "Target group has no course_id and none was supplied")

    result = BulkResult(operation="set_teaching_set",
                        target_count=len(targets))
    moved = 0
    removed_total = 0
    for sid in targets:
        try:
            others = [
                g for g in _cg.groups_for_student(sid)
                if g.group_id != target_group_id
                and getattr(g, "course_id", None) == course_id
            ]
            other_names = [g.group_name for g in others]
            already_in_target = any(
                g.group_id == target_group_id
                for g in _cg.groups_for_student(sid))
            if dry_run:
                if already_in_target and not others:
                    result.success_ids.append(f"{sid}: (already there)")
                else:
                    result.success_ids.append(
                        f"{sid}: leave {other_names!r} → join "
                        f"{target.group_name!r}")
                continue
            for g in others:
                if _cg.remove_member(g.group_id, sid):
                    removed_total += 1
            if not already_in_target:
                _cg.add_member(target_group_id, sid)
                moved += 1
                result.success_ids.append(
                    f"{sid}: → {target.group_name}")
            else:
                result.success_ids.append(f"{sid}: (already in target)")
        except Exception as e:  # noqa: BLE001
            result.failures.append((sid, str(e)))
    if dry_run:
        return result
    summary_text = (
        f"Set teaching set {target.group_name!r} (course #{course_id}) for "
        f"{result.success_count}/{result.target_count} students; "
        f"removed {removed_total} prior membership(s), "
        f"added {moved} new"
    )
    result.job_id = _log_job(
        operation="set_teaching_set", summary=summary_text,
        params={"target_group_id": target_group_id,
                "course_id": course_id,
                "moved": moved, "removed": removed_total},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk import timetable slots from CSV ───────────────

def bulk_import_timetable_csv(
    csv_path: str,
    *,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Load timetable slots from a CSV.

    Required headers: ``group_id, day, period``.
    Optional: ``start_time, end_time, room, notes``.

    ``day`` accepts both an integer (1=Mon..7=Sun) and a day name
    (``Mon``/``Monday``). One slot per row; failures are reported
    per-line so partial imports are kept.
    """
    import csv as _csv
    import os
    if not csv_path or not os.path.isfile(csv_path):
        raise ValidationError(f"CSV not found: {csv_path}")
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )

    try:
        fh = open(csv_path, encoding="utf-8-sig", newline="")
    except OSError as e:
        raise ValidationError(f"Cannot open CSV: {e}") from e
    with fh:
        reader = _csv.DictReader(fh)
        required = {"group_id", "day", "period"}
        headers = {(h or "").strip() for h in (reader.fieldnames or [])}
        missing = required - headers
        if missing:
            raise ValidationError(
                f"CSV missing columns: {', '.join(sorted(missing))}")
        rows: list[dict[str, str]] = [
            {k: (v or "").strip() for k, v in r.items()}
            for r in reader
        ]

    result = BulkResult(operation="import_timetable_csv",
                        target_count=len(rows))
    if not rows:
        result.job_id = _log_job(
            operation="import_timetable_csv",
            summary=(f"Imported 0 timetable rows from "
                     f"{os.path.basename(csv_path)} (empty file)"),
            params={"csv_path": csv_path}, result=result, ran_by=ran_by,
        )
        return result
    if dry_run:
        for i, r in enumerate(rows, start=2):
            result.success_ids.append(
                f"line {i}: group={r.get('group_id')} "
                f"day={r.get('day')} P{r.get('period')}")
        return result

    created = 0
    student_clashes = 0
    teacher_clashes = 0
    for i, r in enumerate(rows, start=2):  # +2 for header
        try:
            payload = {
                "group_id":   r.get("group_id"),
                "day":        r.get("day"),
                "period":     r.get("period"),
                "start_time": r.get("start_time") or None,
                "end_time":   r.get("end_time") or None,
                "room":       r.get("room") or None,
                "notes":      r.get("notes") or None,
            }
            save = _tt.create_slot(payload)
            created += 1
            sc, tc = len(save.student_clashes), len(save.teacher_clashes)
            student_clashes += sc
            teacher_clashes += tc
            tag = f"line {i}: slot #{save.slot.slot_id}"
            if sc or tc:
                tag += f" (clashes: students={sc}, teachers={tc})"
            result.success_ids.append(tag)
        except Exception as e:  # noqa: BLE001
            result.failures.append((f"line {i}", str(e)))
    summary_text = (
        f"Imported {created}/{len(rows)} timetable slot(s) from "
        f"{os.path.basename(csv_path)} "
        f"(student clashes={student_clashes}, teacher clashes={teacher_clashes})"
    )
    result.job_id = _log_job(
        operation="import_timetable_csv", summary=summary_text,
        params={"csv_path": csv_path,
                "created": created,
                "student_clashes": student_clashes,
                "teacher_clashes": teacher_clashes},
        result=result, ran_by=ran_by,
    )
    return result
