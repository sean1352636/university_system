"""Persistent log capture for the Sixth Form System.

Plugs into Python's standard ``logging`` so any record emitted by a
sixth-form module is written to a ``system_logs`` table in SQLite.
This complements the in-memory ``logger.info(...)`` output (which is
still printed/streamed as configured by the host application) with a
durable audit trail that survives process restarts and can be queried
from the GUI/CLI.

Typical use::

    from education_system.post_16.sixthform_system.core import log_store
    log_store.install()          # idempotent — safe to call repeatedly

Records are inserted with a per-emit connection so the handler is
thread-safe under SQLite's normal locking. The handler swallows any
emit-time failure (via ``logging.Handler.handleError``) so a broken
DB never crashes the calling code.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.post_16.sixthform_system.core import paths

DB_PATH = paths.SYSTEM_LOGS_DB

# Sixth-form student ids look like "C" + exactly 7 digits (see
# ``students.generate_student_id``). Word boundaries keep us from
# matching the leading "C" inside an unrelated identifier.
_STUDENT_ID_RE = re.compile(r"\bC\d{7}\b")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS system_logs (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL DEFAULT (datetime('now')),
    level       TEXT    NOT NULL,
    level_no    INTEGER NOT NULL,
    logger_name TEXT    NOT NULL,
    module      TEXT,
    func_name   TEXT,
    line_no     INTEGER,
    message     TEXT    NOT NULL,
    student_id  TEXT,
    extra_json  TEXT,
    exc_text    TEXT
);

CREATE INDEX IF NOT EXISTS idx_sys_logs_ts        ON system_logs(ts DESC);
CREATE INDEX IF NOT EXISTS idx_sys_logs_level     ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_sys_logs_logger    ON system_logs(logger_name);
CREATE INDEX IF NOT EXISTS idx_sys_logs_student   ON system_logs(student_id);
"""

_INSTALLED: bool = False
_DB_READY: bool = False


def _connect() -> sqlite3.Connection:
    """Open a fresh connection tuned for write-concurrency.

    The log table sits inside the main sixth-form DB, so the handler
    will routinely be asked to insert while another connection is
    mid-transaction (e.g. subjects.init_db seeding rows). Enabling
    WAL mode + a busy timeout lets those inserts proceed instead of
    racing into ``OperationalError: database is locked``.
    """
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    # WAL: writer doesn't block readers and is much friendlier under
    # concurrent INSERTs. busy_timeout: how long the driver will wait
    # for a competing writer before erroring out.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except sqlite3.DatabaseError:
        # Pragmas are best-effort — the handler still works without
        # them, just less robust under contention.
        pass
    return conn


def init_db() -> None:
    """Apply the schema (once per process)."""
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


@dataclass
class LogRow:
    log_id: int
    ts: str
    level: str
    level_no: int
    logger_name: str
    module: str | None
    func_name: str | None
    line_no: int | None
    message: str
    student_id: str | None
    extra_json: str | None
    exc_text: str | None


class SqliteLogHandler(logging.Handler):
    """Logging handler that writes each record to ``system_logs``.

    Looks for these optional fields on the ``LogRecord``:

    * ``student_id`` — populated by callers passing
      ``extra={"student_id": sid}``; promoted to its own column so
      the GUI can filter by it.
    """

    # Retry config for transient SQLite "database is locked" errors.
    # Happens when another connection in the same process is mid-
    # transaction at the moment we try to insert. Short backoff is
    # enough — these are sub-second contentions.
    _RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4)

    def emit(self, record: logging.LogRecord) -> None:
        import time
        try:
            init_db()
            msg = self.format(record)
            # Prefer an explicit ``extra={"student_id": ...}`` from
            # the caller; fall back to scanning the rendered message
            # for a ``Cxxxxxxx`` id so the column populates for free.
            student_id = getattr(record, "student_id", None)
            if not student_id:
                m = _STUDENT_ID_RE.search(msg)
                if m:
                    student_id = m.group(0)
            exc_text = (self.formatter or logging.Formatter()).formatException(
                record.exc_info) if record.exc_info else None
            params = (record.levelname, record.levelno, record.name,
                      record.module, record.funcName, record.lineno,
                      msg, student_id, exc_text)
            last_err: Exception | None = None
            for delay in (0.0,) + self._RETRY_DELAYS:
                if delay:
                    time.sleep(delay)
                try:
                    with _connect() as conn:
                        conn.execute(
                            """INSERT INTO system_logs
                                   (level, level_no, logger_name, module,
                                    func_name, line_no, message,
                                    student_id, exc_text)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            params,
                        )
                        conn.commit()
                    return
                except sqlite3.OperationalError as exc:
                    # "database is locked" is the one we expect; any
                    # other OperationalError is structural and worth
                    # the standard error path.
                    if "locked" not in str(exc).lower():
                        raise
                    last_err = exc
            # Out of retries — drop the record silently so the caller
            # isn't punished for a log statement during contention.
            # ``raiseExceptions=False`` would do the same suppression.
            if last_err is not None:
                # Last-ditch: avoid handleError's traceback dump for
                # the locked case specifically.
                return
        except Exception:
            self.handleError(record)


def install(*, logger_name: str = "education_system.post_16.sixthform_system",
            level: int | str = logging.DEBUG) -> SqliteLogHandler | None:
    """Attach the SQLite log handler to ``logger_name`` (idempotent).

    Returns the installed handler, or the existing one if already
    installed. Defaults to capturing every sixth-form-package record
    at DEBUG or above.
    """
    global _INSTALLED
    target = logging.getLogger(logger_name)
    for h in target.handlers:
        if isinstance(h, SqliteLogHandler):
            return h
    handler = SqliteLogHandler()
    handler.setLevel(level)
    # Standard log format — message stored separately so the column
    # stays clean; level/logger/etc. are in their own columns.
    handler.setFormatter(logging.Formatter("%(message)s"))
    target.addHandler(handler)
    # Make sure the target logger itself isn't filtering us out.
    if target.level == logging.NOTSET or target.level > handler.level:
        target.setLevel(handler.level)
    _INSTALLED = True
    return handler


def is_installed() -> bool:
    return _INSTALLED


# ── Read helpers ───────────────────────────────────────────────────

def _row(r: sqlite3.Row) -> LogRow:
    return LogRow(
        log_id=r["log_id"], ts=r["ts"], level=r["level"],
        level_no=r["level_no"], logger_name=r["logger_name"],
        module=r["module"], func_name=r["func_name"],
        line_no=r["line_no"], message=r["message"],
        student_id=r["student_id"], extra_json=r["extra_json"],
        exc_text=r["exc_text"],
    )


def list_logs(
    *,
    level: str | None = None,
    min_level_no: int | None = None,
    logger_name_like: str | None = None,
    student_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
) -> list[LogRow]:
    """Return recent log rows, most recent first."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if level:
        clauses.append("level = ?")
        args.append(level.upper())
    if min_level_no is not None:
        clauses.append("level_no >= ?")
        args.append(min_level_no)
    if logger_name_like:
        clauses.append("logger_name LIKE ?")
        args.append(f"%{logger_name_like}%")
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if since:
        clauses.append("ts >= ?")
        args.append(since)
    if until:
        clauses.append("ts <= ?")
        args.append(until)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM system_logs {where} "
           f"ORDER BY log_id DESC LIMIT ?")
    args.append(int(limit))
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def count_logs() -> int:
    init_db()
    with _connect() as conn:
        (n,) = conn.execute(
            "SELECT COUNT(*) FROM system_logs").fetchone()
    return n


def purge_before(ts: str) -> int:
    """Delete log rows older than ``ts`` (YYYY-MM-DD or full timestamp).

    Returns the number of rows removed. Intended for periodic
    housekeeping — the table is otherwise append-only.
    """
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM system_logs WHERE ts < ?", (ts,))
        conn.commit()
        return cur.rowcount or 0
