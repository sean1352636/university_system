"""Retention and legal holds.

A hold blocks erasure of a subject's records: litigation, a regulatory
investigation, a safeguarding case, or a statutory retention period that has
not yet expired. It is the control ``StudentLifecycleService.purge`` requires
before it will queue a destructive erasure.

This exists because there was no such register. The only ``has_active_hold``
in the codebase lives in ``services/bus/finance_bus`` and means *unpaid
fees* — using it here would let an unpaid library fine block a lawful GDPR
erasure while a genuine litigation hold went undetected. The two concepts are
unrelated and must not share a check.

Fails closed: if the register cannot be read, callers are told a hold exists.
Refusing an erasure that should have proceeded is recoverable; performing one
that should have been blocked is not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from education_system.systems.university.infrastructure.database.db import transaction

logger = logging.getLogger(__name__)

SUBJECT_STUDENT = "student"
SUBJECT_STAFF = "staff"

#: Why a hold exists. Recorded so a reviewer can tell a court order from a
#: routine retention period without reading free text.
REASON_LEGAL = "legal"
REASON_REGULATORY = "regulatory"
REASON_SAFEGUARDING = "safeguarding"
REASON_STATUTORY_RETENTION = "statutory_retention"
REASONS = (REASON_LEGAL, REASON_REGULATORY, REASON_SAFEGUARDING,
           REASON_STATUTORY_RETENTION)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retention_holds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type    TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    reason          TEXT NOT NULL,
    detail          TEXT NOT NULL DEFAULT '',
    case_reference  TEXT NOT NULL DEFAULT '',
    placed_by       TEXT NOT NULL,
    placed_at       TEXT NOT NULL,
    expires_on      TEXT,
    released_by     TEXT,
    released_at     TEXT,
    release_reason  TEXT
)
"""

_INDEX = """
CREATE INDEX IF NOT EXISTS idx_retention_holds_subject
    ON retention_holds (subject_type, subject_id)
"""


class HoldError(ValueError):
    pass


@dataclass(frozen=True)
class Hold:
    id: int
    subject_type: str
    subject_id: str
    reason: str
    detail: str
    case_reference: str
    placed_by: str
    placed_at: str
    expires_on: str | None


def _ensure_schema(conn) -> None:
    conn.execute(_SCHEMA)
    conn.execute(_INDEX)


def _active_clause() -> str:
    """Active = not released, and not past an expiry date if one was set."""
    return ("released_at IS NULL "
            " AND (expires_on IS NULL OR TRIM(expires_on) = '' OR expires_on >= ?)")


def place_hold(subject_id: str, *, reason: str, placed_by: str,
               detail: str = "", case_reference: str = "",
               expires_on: str | None = None,
               subject_type: str = SUBJECT_STUDENT,
               db_path: str | None = None) -> int:
    """Record a hold. Returns its id."""
    if reason not in REASONS:
        raise HoldError(f"reason must be one of {', '.join(REASONS)}")
    if not str(subject_id or "").strip():
        raise HoldError("subject_id is required")
    if not str(placed_by or "").strip():
        raise HoldError("placed_by is required — a hold must be attributable")
    if expires_on:
        try:
            date.fromisoformat(expires_on)
        except ValueError as exc:
            raise HoldError("expires_on must be an ISO date (YYYY-MM-DD)") from exc
    with transaction(db_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute(
            """INSERT INTO retention_holds
                 (subject_type, subject_id, reason, detail, case_reference,
                  placed_by, placed_at, expires_on)
               VALUES (?,?,?,?,?,?,?,?)""",
            (subject_type, str(subject_id), reason, detail, case_reference,
             placed_by, datetime.now().isoformat(timespec="seconds"), expires_on),
        )
        hold_id = int(cursor.lastrowid)
    logger.info("retention hold %s placed on %s %s by %s (%s)",
                hold_id, subject_type, subject_id, placed_by, reason)
    return hold_id


def release_hold(hold_id: int, *, released_by: str, reason: str,
                 db_path: str | None = None) -> bool:
    """Release a hold. Rows are never deleted — the audit trail is the point."""
    if not str(released_by or "").strip():
        raise HoldError("released_by is required")
    if not str(reason or "").strip():
        raise HoldError("a release reason is required")
    with transaction(db_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute(
            """UPDATE retention_holds
                  SET released_by = ?, released_at = ?, release_reason = ?
                WHERE id = ? AND released_at IS NULL""",
            (released_by, datetime.now().isoformat(timespec="seconds"),
             reason, int(hold_id)),
        )
        released = cursor.rowcount > 0
    if released:
        logger.info("retention hold %s released by %s (%s)",
                    hold_id, released_by, reason)
    return released


def list_holds(subject_id: str, *, subject_type: str = SUBJECT_STUDENT,
               active_only: bool = True,
               db_path: str | None = None) -> list[Hold]:
    with transaction(db_path) as conn:
        _ensure_schema(conn)
        sql = ("SELECT * FROM retention_holds "
               " WHERE subject_type = ? AND subject_id = ?")
        params: list[Any] = [subject_type, str(subject_id)]
        if active_only:
            sql += " AND " + _active_clause()
            params.append(date.today().isoformat())
        rows: Iterable = conn.execute(sql + " ORDER BY placed_at DESC", params).fetchall()
        return [Hold(id=int(r["id"]), subject_type=r["subject_type"],
                     subject_id=r["subject_id"], reason=r["reason"],
                     detail=r["detail"], case_reference=r["case_reference"],
                     placed_by=r["placed_by"], placed_at=r["placed_at"],
                     expires_on=r["expires_on"]) for r in rows]


def has_active_hold(subject_id: str, *, subject_type: str = SUBJECT_STUDENT,
                    db_path: str | None = None) -> bool:
    """True if erasure is blocked. Fails closed on any error.

    This is the callable ``StudentLifecycleService.purge`` expects. Note the
    deliberate name collision with ``services/bus/finance_bus.has_active_hold``
    — that one is about money, this one about law. Import the right module.
    """
    try:
        with transaction(db_path) as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT 1 FROM retention_holds "
                " WHERE subject_type = ? AND subject_id = ? AND " + _active_clause()
                + " LIMIT 1",
                (subject_type, str(subject_id), date.today().isoformat()),
            ).fetchone()
            return row is not None
    except Exception:
        logger.warning("retention hold register unreadable for %s %s; "
                       "reporting a hold so erasure is refused",
                       subject_type, subject_id, exc_info=True)
        return True


__all__ = ["Hold", "HoldError", "REASONS", "REASON_LEGAL", "REASON_REGULATORY",
           "REASON_SAFEGUARDING", "REASON_STATUTORY_RETENTION",
           "SUBJECT_STAFF", "SUBJECT_STUDENT", "has_active_hold",
           "list_holds", "place_hold", "release_hold"]
