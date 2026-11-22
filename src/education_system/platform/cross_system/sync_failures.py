"""Failed best-effort cross-system syncs, kept so they can be seen and retried.

``progression.register_local_student``, ``publish_progression`` and
``announce_progression`` never raise: the caller's local record has
already been written and must stand. Before this module a failure there
went only to the log, so the systems could drift out of step — a pupil
with no journey, a progression nobody heard about — with nothing on any
screen to say so.

Each failure is now a row in ``cross_system_sync_failure`` (auth.db) with
the call's keyword arguments. :func:`list_failures` shows the open ones,
:func:`retry` runs the call again (raising this time, so the error is
kept), and :func:`abandon` closes one that should not be retried. The bus
has its own failed-delivery list (``cross_system_bus.list_failed_deliveries``);
this covers what happens *before* an event reaches the bus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from education_system.platform.identity.auth.db import connect

logger = logging.getLogger(__name__)

OPEN = "open"
RESOLVED = "resolved"
ABANDONED = "abandoned"
STATUSES = (OPEN, RESOLVED, ABANDONED)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cross_system_sync_failure (
    failure_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    operation     TEXT NOT NULL,
    system        TEXT,
    local_id      TEXT,
    kwargs_json   TEXT NOT NULL,
    error_message TEXT,
    attempts      INTEGER NOT NULL DEFAULT 1,
    status        TEXT NOT NULL DEFAULT 'open',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_by   TEXT,
    note          TEXT
);
CREATE INDEX IF NOT EXISTS ix_sync_failure_status
    ON cross_system_sync_failure(status, created_at);
"""


class SyncFailureError(ValueError):
    """A failure row cannot be retried or closed as asked."""


def _ensure(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


def _operations() -> dict[str, Callable[..., Any]]:
    # Imported here: progression imports this module.
    from education_system.platform.cross_system import progression
    return {
        "register_local_student": progression._register_local_student,
        "publish_progression": progression._publish_progression,
        "announce_progression": progression._announce_progression,
    }


def record_failure(operation: str, kwargs: dict[str, Any], error: BaseException, *,
                   system: str | None = None, local_id: str | None = None,
                   db_path: str | None = None) -> int | None:
    """Keep one failed call. Never raises — it is called from an except block
    whose caller must not fail, and returns ``None`` if even this could not
    be written (the original failure is still in the log)."""
    try:
        conn = connect(db_path)
        try:
            _ensure(conn)
            cur = conn.execute(
                "INSERT INTO cross_system_sync_failure "
                "(operation, system, local_id, kwargs_json, error_message) "
                "VALUES (?, ?, ?, ?, ?)",
                (operation, system, None if local_id is None else str(local_id),
                 json.dumps(kwargs, default=str),
                 f"{type(error).__name__}: {error}"[:2000]))
            conn.commit()
            return int(cur.lastrowid or 0) or None
        finally:
            conn.close()
    except Exception:
        logger.exception("Could not record the failed %s call", operation)
        return None


def _row(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    try:
        out["kwargs"] = json.loads(out.pop("kwargs_json") or "{}")
    except ValueError:
        out["kwargs"] = {}
    return out


def list_failures(*, status: str | None = OPEN, limit: int = 200,
                  db_path: str | None = None) -> list[dict[str, Any]]:
    """Failures newest first; ``status=None`` for every status."""
    conn = connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        _ensure(conn)
        if status is None:
            rows = conn.execute(
                "SELECT * FROM cross_system_sync_failure "
                "ORDER BY failure_id DESC LIMIT ?", (int(limit),)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM cross_system_sync_failure WHERE status = ? "
                "ORDER BY failure_id DESC LIMIT ?", (status, int(limit))).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


def get_failure(failure_id: int, *, db_path: str | None = None) -> dict | None:
    conn = connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        _ensure(conn)
        row = conn.execute(
            "SELECT * FROM cross_system_sync_failure WHERE failure_id = ?",
            (int(failure_id),)).fetchone()
        return _row(row) if row is not None else None
    finally:
        conn.close()


def _close(failure_id: int, status: str, *, actor: str | None, note: str | None,
           db_path: str | None, error: str | None = None,
           bump: bool = False) -> bool:
    conn = connect(db_path)
    try:
        _ensure(conn)
        cur = conn.execute(
            "UPDATE cross_system_sync_failure SET status = ?, resolved_by = "
            "COALESCE(?, resolved_by), note = COALESCE(?, note), "
            "error_message = COALESCE(?, error_message), "
            "attempts = attempts + ?, updated_at = datetime('now') "
            "WHERE failure_id = ? AND status = 'open'",
            (status, actor, note, error, 1 if bump else 0, int(failure_id)))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def retry(failure_id: int, *, actor: str | None = None,
          db_path: str | None = None) -> Any:
    """Run a failed call again. On success the row is resolved and the
    call's result returned; on failure the row stays open with the new
    error and attempt count, and the exception propagates."""
    row = get_failure(failure_id, db_path=db_path)
    if row is None:
        raise SyncFailureError(f"No sync failure {failure_id}")
    if row["status"] != OPEN:
        raise SyncFailureError(f"Sync failure {failure_id} is already {row['status']}")
    fn = _operations().get(row["operation"])
    if fn is None:
        raise SyncFailureError(f"Unknown operation {row['operation']!r}")
    kwargs = dict(row["kwargs"])
    try:
        result = fn(**kwargs)
    except Exception as exc:
        conn = connect(db_path)
        try:
            conn.execute(
                "UPDATE cross_system_sync_failure SET attempts = attempts + 1, "
                "error_message = ?, updated_at = datetime('now') "
                "WHERE failure_id = ?",
                (f"{type(exc).__name__}: {exc}"[:2000], int(failure_id)))
            conn.commit()
        finally:
            conn.close()
        raise
    _close(failure_id, RESOLVED, actor=actor, note="retried successfully",
           db_path=db_path, bump=True)
    logger.info("Sync failure %s (%s) resolved by retry", failure_id, row["operation"])
    return result


def abandon(failure_id: int, *, reason: str, actor: str | None = None,
            db_path: str | None = None) -> bool:
    """Close a failure without retrying. ``reason`` is required."""
    if not (reason or "").strip():
        raise SyncFailureError("Give a reason for abandoning the failure")
    return _close(failure_id, ABANDONED, actor=actor, note=reason.strip(),
                  db_path=db_path)


def count_open(*, db_path: str | None = None) -> int:
    conn = connect(db_path)
    try:
        _ensure(conn)
        return int(conn.execute(
            "SELECT COUNT(*) FROM cross_system_sync_failure WHERE status = 'open'"
        ).fetchone()[0])
    finally:
        conn.close()


__all__ = [
    "ABANDONED", "OPEN", "RESOLVED", "STATUSES", "SyncFailureError",
    "abandon", "count_open", "get_failure", "list_failures", "record_failure",
    "retry",
]
