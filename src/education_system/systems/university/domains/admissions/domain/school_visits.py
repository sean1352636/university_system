"""A school's visit filed in the Admissions CRM: one ``campus_tours`` row,
one ``admission_prospects`` row per attendee, and a ``tour_registrations``
row linking them.

The sixth form used to write these tables itself, reaching into this
database. It now asks through the university's platform adapter
(:meth:`UniversityAdapter.record_school_visit`), so the university owns its
own rows and the sixth form only keeps the ids it is given back.

Idempotent: an existing tour or prospect id is updated rather than
duplicated, and a prospect is matched on e-mail before a new one is made.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _ensure_schema() -> None:
    """Make sure the admissions tables exist (older databases)."""
    try:
        from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
            AdmissionsSchemas,
        )
    except Exception:
        # Older layouts don't ship the schemas class — the tables may
        # already exist from runtime setup elsewhere.
        return
    try:
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        conn = get_connection()
        try:
            AdmissionsSchemas.create_schemas(conn)
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("AdmissionsSchemas bootstrap failed: %s", exc)


def record_school_visit(tour: dict[str, Any], attendees: list[dict[str, Any]]) -> dict:
    """See :meth:`PhaseAdapter.record_school_visit` for the shapes."""
    from education_system.systems.university.infrastructure.database.db import transaction

    _ensure_schema()
    prospects: dict[str, dict[str, Any]] = {}
    registrations_created = 0
    with transaction() as conn:
        tour_id = _upsert_tour(conn, tour)
        for a in attendees:
            prospect_id, created = _prospect_for(conn, a)
            prospects[str(a["key"])] = {"prospect_id": prospect_id, "created": created}
            if _ensure_registration(conn, tour_id, prospect_id,
                                    attended=bool(a.get("attended"))):
                registrations_created += 1
    return {"tour_id": tour_id, "prospects": prospects,
            "registrations_created": registrations_created}


def _upsert_tour(conn, tour: dict[str, Any]) -> int:
    values = (tour.get("tour_date"), tour.get("tour_time"), tour.get("tour_guide"),
              tour.get("max_attendees"), tour.get("meeting_point"),
              tour.get("duration_minutes"), tour.get("status") or "scheduled")
    existing = tour.get("tour_id")
    if existing and conn.execute("SELECT 1 FROM campus_tours WHERE tour_id = ?",
                                 (existing,)).fetchone():
        conn.execute(
            """UPDATE campus_tours SET
                   tour_date = ?, tour_time = ?, tour_guide = ?,
                   max_attendees = ?, meeting_point = ?,
                   duration_minutes = ?, status = ?
               WHERE tour_id = ?""", (*values, existing))
        return int(existing)
    cur = conn.execute(
        """INSERT INTO campus_tours
               (tour_date, tour_time, tour_guide, max_attendees,
                meeting_point, duration_minutes, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""", values)
    return int(cur.lastrowid)


def _prospect_for(conn, a: dict[str, Any]) -> tuple[int, bool]:
    """``(prospect_id, created)`` for one attendee."""
    existing = a.get("prospect_id")
    if existing and conn.execute("SELECT 1 FROM admission_prospects WHERE prospect_id = ?",
                                 (existing,)).fetchone():
        return int(existing), False
    email = (a.get("email") or "").strip()
    if email:
        r = conn.execute("SELECT prospect_id FROM admission_prospects WHERE email = ? "
                         "ORDER BY prospect_id LIMIT 1", (email,)).fetchone()
        if r is not None:
            return int(r[0]), False
    cur = conn.execute(
        """INSERT INTO admission_prospects
               (first_name, last_name, email, date_of_birth,
                high_school, source, status)
           VALUES (?, ?, ?, ?, ?, ?, 'prospect')""",
        (a.get("first_name") or "", a.get("last_name") or "", email,
         a.get("date_of_birth") or "", a.get("high_school") or "", a.get("source") or ""))
    return int(cur.lastrowid), True


def _ensure_registration(conn, tour_id: int, prospect_id: int, *, attended: bool) -> bool:
    """Insert a tour_registrations row if none exists for this (tour,
    prospect); keep ``attended`` in sync otherwise. True if inserted."""
    r = conn.execute("SELECT registration_id FROM tour_registrations "
                     "WHERE tour_id = ? AND prospect_id = ?", (tour_id, prospect_id)).fetchone()
    if r is not None:
        conn.execute("UPDATE tour_registrations SET attended = ? "
                     "WHERE tour_id = ? AND prospect_id = ?",
                     (1 if attended else 0, tour_id, prospect_id))
        return False
    conn.execute("""INSERT INTO tour_registrations
                        (tour_id, prospect_id, num_guests, attended)
                    VALUES (?, ?, 0, ?)""", (tour_id, prospect_id, 1 if attended else 0))
    conn.execute("UPDATE campus_tours SET current_attendees = current_attendees + 1 "
                 "WHERE tour_id = ?", (tour_id,))
    return True
