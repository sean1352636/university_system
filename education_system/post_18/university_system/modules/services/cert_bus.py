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

from education_system.post_18.university_system.infrastructure.database.db import (
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
        from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import publish
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


def notify_expiring(within_days: int = 30) -> dict[str, Any]:
    """Cross-domain expiring-cert subscriber.

    Walks ``expiring_certifications(within_days)`` and:

    * Sends a templated email to each affected staff member via
      ``email_bus.send_templated`` (subject ``cert_expiring``).
    * For first-aid certs specifically, scans
      ``trip_bus.list_trips`` for upcoming field/research trips
      led by the staff member and raises a
      ``risk_bus.raise_risk(category='Safety', reference_id=
      f'staff_cert:{cert_id}')`` so HR sees the trip-coverage
      gap on the legal/risk GUI.

    Returns ``{"emailed": N, "trip_risks_raised": M, "reviewed": K}``.
    Idempotent: the risk row is only raised once per cert (via
    ``risk_bus.list_risks_for`` precheck).
    """
    out = {"emailed": 0, "trip_risks_raised": 0, "reviewed": 0}
    try:
        rows = expiring_certifications(within_days=within_days) or []
    except Exception as exc:
        logger.warning("notify_expiring: list failed: %s", exc)
        return out
    out["reviewed"] = len(rows)

    try:
        from education_system.post_18.university_system.modules.services import (
            email_bus, risk_bus,
        )
    except Exception:
        return out

    for cert in rows:
        cert_id = cert.get("cert_id") or cert.get("id")
        staff_id = cert.get("subject_id") or cert.get("staff_id") \
                    or cert.get("user_id")
        kind = str(cert.get("kind") or cert.get("name") or "")
        expires = cert.get("expires_on") or cert.get("expiry_date")
        if not staff_id:
            continue
        try:
            sent = email_bus.send_templated(
                staff_id, "cert_expiring",
                {"cert_kind": kind, "expires_on": expires,
                 "cert_id": cert_id},
            )
            if sent:
                out["emailed"] += 1
        except Exception as exc:
            logger.debug("cert_expiring email send failed: %s", exc)

        if "first" in kind.lower() and "aid" in kind.lower() and cert_id:
            ref = f"staff_cert:{cert_id}"
            try:
                if risk_bus.list_risks_for(ref):
                    continue
                # Look up upcoming trips led by this staff member.
                from education_system.post_18.university_system.modules.services import (
                    trip_bus,
                )
                today = datetime.now().strftime("%Y-%m-%d")
                upcoming = [
                    t for t in (trip_bus.list_trips() or [])
                    if str(t.get("created_by") or "") == str(staff_id)
                       and str(t.get("start_date", "")) >= today
                ]
                if upcoming:
                    risk_bus.raise_risk(
                        title=(f"First-aid cert expiring for staff "
                               f"{staff_id} with {len(upcoming)} "
                               f"upcoming trip(s)"),
                        category="Safety",
                        department="Trips & Mobility",
                        description=(
                            f"Cert {cert_id} ({kind}) expires "
                            f"{expires}. Affects "
                            f"{[t.get('trip_name') for t in upcoming]}."
                        ),
                        likelihood=4, impact=4,
                        owner=str(staff_id),
                        reference_id=ref,
                        next_review_date=str(expires)[:10] if expires
                                          else None,
                    )
                    out["trip_risks_raised"] += 1
            except Exception as exc:
                logger.debug("first-aid trip risk failed: %s", exc)

    return out


__all__ = [
    "add_certification", "delete_certification",
    "expiring_certifications", "list_certifications_for",
    "notify_expiring",
]
