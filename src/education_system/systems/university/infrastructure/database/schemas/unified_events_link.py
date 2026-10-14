"""Provenance for ``unified_events``: which source row a unified row came from.

``unified_events`` was built as a consolidation target — it carries
``source_type`` (NOT NULL) and ``source_event_id`` for exactly that purpose, and
a dozen subsystems already insert into it tagged ``'campus'``, ``'alumni'``,
``'club'`` and so on.

``source_event_id``, however, has never been written by any of them. Every
unified row therefore records *which system* produced it but not *which row*,
which is the one fact a phased migration needs: without it there is no way to
tell whether a given legacy event has already been copied across, so a backfill
cannot be re-run safely and the two tables cannot be reconciled while both are
live.

This module supplies the missing half:

* :func:`ensure_source_link` adds the partial unique index on
  ``(source_type, source_event_id)`` — partial so that natively-created events,
  which have no source row and leave ``source_event_id`` NULL, do not collide
  with each other;
* :func:`link_source_event` upserts a source row into ``unified_events`` and
  returns the unified ``event_id``, so a migration is idempotent by
  construction.

This module deliberately does **not** define ``unified_events``. That table has
six disagreeing ``CREATE`` statements across the tree already; adding a seventh
would make the problem worse rather than better. Consolidating them is a
separate job.
"""

from __future__ import annotations

import logging
import sqlite3
from education_system.systems.university.infrastructure.sql_safety import validate_identifier

logger = logging.getLogger(__name__)

#: ``source_type`` values in use. A row's source_type says which subsystem owns
#: it; ``None``/native rows are those created directly in the unified system.
SOURCE_LIBRARY = "library"
SOURCE_CAMPUS = "campus"
SOURCE_ALUMNI = "alumni"
SOURCE_CLUB = "club"
SOURCE_UNION = "union"
SOURCE_ACADEMIC_CALENDAR = "academic_calendar"
SOURCE_COMMUNITY = "community"              # was ``public_events``
SOURCE_STUDENT_COUNCIL = "student_council"  # was ``sc_events``
SOURCE_COMMITTEE = "committee"              # was ``committee_meetings``

#: Columns a source needs that ``unified_events`` did not have. Added in place
#: by :func:`ensure_unified_columns`; everything else maps onto existing ones.
EXTRA_COLUMNS = {
    "committee_id": "INTEGER",
    "secretary_id": "TEXT",
    "recurrence": "TEXT",
}

# Source-filtered projections exposing each legacy table's column names, so
# existing WHERE / ORDER BY clauses keep working. Use as ``FROM <SRC> e``.
# Writes go to ``unified_events`` directly and must filter on source_type.
PUBLIC_EVENTS_SRC = (
    "(SELECT event_id, title AS event_name, organizer_id, event_date, location, "
    "description, max_capacity AS expected_attendance, status, created_at "
    "FROM unified_events ue WHERE ue.source_type = 'community')"
)
SC_EVENTS_SRC = (
    "(SELECT event_id AS id, title AS name, event_date, start_time AS event_time, "
    "location AS venue, organizer_name AS organiser, description, created_at "
    "FROM unified_events ue WHERE ue.source_type = 'student_council')"
)
COMMITTEE_MEETINGS_SRC = (
    "(SELECT event_id AS id, event_id AS meeting_id, committee_id, title, "
    "event_date AS meeting_date, start_time, end_time, location, virtual_link, "
    "status, organizer_id AS chair_id, secretary_id, recurrence, notes, "
    "created_by, created_at, updated_at "
    "FROM unified_events ue WHERE ue.source_type = 'committee')"
)

SOURCE_LINK_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_unified_events_source "
    "ON unified_events (source_type, source_event_id) "
    "WHERE source_event_id IS NOT NULL"
)


def ensure_source_link(conn) -> None:
    """Add the provenance index, and the registration columns a source needs.

    Accepts a connection or a cursor. Idempotent; safe on every startup.
    """
    try:
        conn.execute(SOURCE_LINK_INDEX)
    except sqlite3.OperationalError as exc:
        # A pre-existing duplicate (source_type, source_event_id) pair would
        # fail here. Report it rather than leaving the caller to assume the
        # index is in place.
        logger.error("Could not create unified_events source index: %s", exc)
        raise

    # ``unified_event_registrations`` has no attendee-name column, but sources
    # can register people who are not system users (a library walk-in has a
    # name and no user_id). Add it rather than dropping the name on migration.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unified_event_registrations)")}
    if cols and "attendee_name" not in cols:
        conn.execute(
            "ALTER TABLE unified_event_registrations ADD COLUMN attendee_name TEXT"
        )
        logger.info("Added unified_event_registrations.attendee_name")

    ensure_unified_columns(conn)


def ensure_unified_columns(conn) -> None:
    """Add :data:`EXTRA_COLUMNS` to ``unified_events`` if missing. Idempotent.

    A no-op when ``unified_events`` does not exist yet.
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unified_events)")}
    if not cols:
        return
    for name, decl in EXTRA_COLUMNS.items():
        if name not in cols:
            # db-audit: ignore[DBW001] - name/decl come from the EXTRA_COLUMNS literal
            conn.execute(f'ALTER TABLE unified_events ADD COLUMN "{name}" {decl}')
            logger.info("Added unified_events.%s", name)


def start_datetime(event_date, start_time=None):
    """``YYYY-MM-DDTHH:MM`` for the ``start_datetime`` index, or None."""
    day = (event_date or "").strip()[:10]
    if not day:
        return None
    time = (start_time or "").strip()
    return f"{day}T{time}" if time else day


def link_source_event(conn, source_type: str, source_event_id, fields: dict):
    """Insert or update the unified row for one source event; return its id.

    Idempotent on ``(source_type, source_event_id)`` — calling it twice for the
    same source row updates that row rather than creating a second one, so a
    backfill can be re-run without duplicating.
    """
    if source_event_id is None:
        raise ValueError("source_event_id is required to link a source event")

    existing = conn.execute(
        "SELECT event_id FROM unified_events "
        "WHERE source_type = ? AND source_event_id = ?",
        (source_type, source_event_id),
    ).fetchone()

    payload = dict(fields)
    payload["source_type"] = source_type
    payload["source_event_id"] = source_event_id

    if existing:
        event_id = existing[0]
        assignments = ", ".join(
            f'"{validate_identifier(k, "column")}" = ?' for k in fields)
        if assignments:
            conn.execute(
                f"UPDATE unified_events SET {assignments} WHERE event_id = ?",
                (*fields.values(), event_id),
            )
        return event_id

    columns = ", ".join(
        f'"{validate_identifier(k, "column")}"' for k in payload)
    placeholders = ", ".join("?" for _ in payload)
    cur = conn.execute(
        f"INSERT INTO unified_events ({columns}) VALUES ({placeholders})",
        tuple(payload.values()),
    )
    return cur.lastrowid


def registered_count(conn, event_id) -> int:
    """Live registration count for a unified event.

    The per-source tables kept a denormalised ``registered_count`` that had to
    be incremented by hand alongside every insert; counting the registrations
    cannot drift out of step with them.
    """
    return conn.execute(
        "SELECT COUNT(*) FROM unified_event_registrations WHERE event_id = ?",
        (event_id,),
    ).fetchone()[0]
