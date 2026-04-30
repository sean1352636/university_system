"""Shared certification expiry tracker.

HR dashboards, First Aid roster, H&S team views, and the chatbot all
need answers to the same question: *what certifications are about
to expire?* This module owns the schema and the canonical query so
each consumer gets the same answer.

Reads from two tables in priority order:

* ``staff_certifications`` (created here on first call) — explicit
  staff/role certifications: First Aid, Manual Handling, Fire Warden,
  DSE Assessor, etc.
* ``certifications`` (legacy, user-bound) — fallback for older data.

Public surface:

- ``add_certification(staff_id, kind, ...)`` — write + publish
- ``delete_certification(cert_id)`` — soft-delete + publish
- ``expiring_certifications(within_days=30, kind=None)`` — list
- ``list_certifications_for(staff_id)`` — per-person view

Publishes ``EVENT_CERT_CHANGED`` on any write.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS staff_certifications (
    cert_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id    TEXT NOT NULL,
    kind        TEXT NOT NULL,
    issued_on   TEXT,
    expires_on  TEXT,
    issuer      TEXT,
    document_id INTEGER,
    notes       TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_staff_certs_staff "
    "ON staff_certifications(staff_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_staff_certs_expiry "
    "ON staff_certifications(expires_on)",
    "CREATE INDEX IF NOT EXISTS idx_staff_certs_kind "
    "ON staff_certifications(kind)",
)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    for sql in _INDEX_SQL:
        conn.execute(sql)


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.university_system.modules.domain.academics.gui._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("cert bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def add_certification(
    staff_id: str | int,
    kind: str,
    *,
    issued_on: str | None = None,
    expires_on: str | None = None,
    issuer: str | None = None,
    document_id: int | None = None,
    notes: str | None = None,
) -> int | None:
    """Record a new certification. Returns the new cert_id."""
    if not staff_id or not kind:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cert_id: int | None = None
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            cur = conn.execute(
                """INSERT INTO staff_certifications
                   (staff_id, kind, issued_on, expires_on, issuer,
                    document_id, notes, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (str(staff_id), kind, issued_on, expires_on,
                 issuer, document_id, notes, now, now),
            )
            cert_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("add_certification failed: %s", exc)
        return None

    _publish(
        "hr.certification.changed",
        cert_id=cert_id, staff_id=str(staff_id),
        kind=kind, action="created",
        expires_on=expires_on,
    )
    return cert_id


def delete_certification(cert_id: int) -> bool:
    """Soft-delete a certification."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    staff_id: str | None = None
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT staff_id FROM staff_certifications WHERE cert_id = ?",
                (cert_id,),
            ).fetchone()
            if not row:
                return False
            staff_id = row[0]
            conn.execute(
                "UPDATE staff_certifications SET is_active = 0, updated_at = ? "
                "WHERE cert_id = ?",
                (now, cert_id),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("delete_certification(%s) failed: %s", cert_id, exc)
        return False

    _publish(
        "hr.certification.changed",
        cert_id=cert_id, staff_id=staff_id, action="deleted",
    )
    return True


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def expiring_certifications(within_days: int = 30,
                            kind: str | None = None,
                            ) -> list[dict[str, Any]]:
    """Return certifications expiring in ``within_days`` (or already expired).

    Pulls from both ``staff_certifications`` and the legacy
    ``certifications`` table, normalising the columns. Empty list on
    any failure or missing schema.
    """
    floor = datetime.now().strftime("%Y-%m-%d")
    ceiling = (datetime.now() + timedelta(days=int(within_days))).strftime("%Y-%m-%d")
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            params: list[Any] = [ceiling]
            sql = (
                "SELECT cert_id, staff_id AS subject_id, kind, "
                "       expires_on, issuer, 'staff_certifications' AS source "
                "FROM staff_certifications "
                "WHERE COALESCE(is_active, 1) = 1 "
                "  AND expires_on IS NOT NULL "
                "  AND expires_on <= ? "
            )
            if kind:
                sql += "AND LOWER(kind) = LOWER(?) "
                params.append(kind)
            sql += "ORDER BY expires_on"
            for r in conn.execute(sql, tuple(params)).fetchall():
                out.append(dict(r))

            # Legacy table — same shape, different column names.
            try:
                params2: list[Any] = [ceiling]
                sql2 = (
                    "SELECT cert_id, user_id AS subject_id, name AS kind, "
                    "       expiry_date AS expires_on, issuing_body AS issuer, "
                    "       'certifications' AS source "
                    "FROM certifications "
                    "WHERE COALESCE(status, 'active') = 'active' "
                    "  AND expiry_date IS NOT NULL "
                    "  AND expiry_date <= ? "
                )
                if kind:
                    sql2 += "AND LOWER(name) = LOWER(?) "
                    params2.append(kind)
                sql2 += "ORDER BY expiry_date"
                for r in conn.execute(sql2, tuple(params2)).fetchall():
                    out.append(dict(r))
            except sqlite3.OperationalError:
                pass
    except Exception as exc:
        logger.warning("expiring_certifications failed: %s", exc)
        return []
    # Mark already-expired vs upcoming for the caller's UI.
    for d in out:
        d["already_expired"] = (d.get("expires_on") or "") < floor
    return out


def list_certifications_for(staff_id: str | int) -> list[dict[str, Any]]:
    if not staff_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            for r in conn.execute(
                "SELECT cert_id, kind, issued_on, expires_on, issuer, notes "
                "FROM staff_certifications "
                "WHERE staff_id = ? AND COALESCE(is_active, 1) = 1 "
                "ORDER BY expires_on",
                (str(staff_id),),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_certifications_for(%s) failed: %s", staff_id, exc)
    return out


__all__ = [
    "add_certification", "delete_certification",
    "expiring_certifications", "list_certifications_for",
]
