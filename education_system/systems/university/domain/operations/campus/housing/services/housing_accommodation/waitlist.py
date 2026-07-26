"""Housing waitlist service.

When an application can't be placed because no suitable room is
available, the application is parked here keyed by building (optional)
and room type. As rooms free up — typically at move-out — the next
matching waitlist entry is promoted automatically.

Schema is created lazily on first use so callers don't have to run a
separate migration step. Rows are append-only: status flips between
``Waiting`` → ``Promoted`` / ``Removed`` and the original row stays for
audit history.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
from typing import Any

from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import (
    get_connection, generate_id,
)

logger = logging.getLogger(__name__)


# ── Schema ─────────────────────────────────────────────────────────────

def init_waitlist_schema() -> None:
    """Create the ``housing_waitlist`` table if it doesn't exist. Safe
    to call multiple times; logs and re-raises on DB error so the
    caller can decide whether to abort."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS housing_waitlist (
                    waitlist_id    TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    student_id     TEXT NOT NULL,
                    building_id    TEXT,
                    room_type      TEXT,
                    priority       INTEGER NOT NULL DEFAULT 0,
                    status         TEXT NOT NULL DEFAULT 'Waiting',
                    notes          TEXT,
                    promoted_to_assignment_id TEXT,
                    added_at       TEXT NOT NULL,
                    updated_at     TEXT NOT NULL,
                    FOREIGN KEY (application_id)
                        REFERENCES housing_applications (application_id),
                    FOREIGN KEY (student_id)
                        REFERENCES students (student_id),
                    FOREIGN KEY (building_id)
                        REFERENCES housing_buildings (building_id)
                )
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_housing_waitlist_status
                ON housing_waitlist(status, priority DESC, added_at)
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to initialise housing_waitlist schema")
        raise


# ── Reads ──────────────────────────────────────────────────────────────

def list_waitlist(*, status: str | None = "Waiting",
                  building_id: str | None = None,
                  room_type: str | None = None) -> list[dict[str, Any]]:
    """Return waitlist rows joined with student + application info.

    Default scope is ``status='Waiting'``; pass ``status=None`` to see
    every row including promoted/removed history.
    """
    init_waitlist_schema()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("w.status = ?")
        args.append(status)
    if building_id:
        clauses.append("w.building_id = ?")
        args.append(building_id)
    if room_type:
        clauses.append("w.room_type = ?")
        args.append(room_type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f'''
        SELECT w.waitlist_id, w.application_id, w.student_id,
               s.first_name || ' ' || s.last_name AS student_name,
               w.building_id,
               COALESCE(b.building_name, '(any building)') AS building_name,
               w.room_type, w.priority, w.status, w.notes,
               w.promoted_to_assignment_id,
               w.added_at, w.updated_at
        FROM housing_waitlist w
        LEFT JOIN students          s ON s.student_id  = w.student_id
        LEFT JOIN housing_buildings b ON b.building_id = w.building_id
        {where}
        ORDER BY w.status, w.priority DESC, w.added_at
    '''
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, args).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_waitlist failed (status=%s, building=%s, type=%s)",
                         status, building_id, room_type)
        return []


# ── Writes ─────────────────────────────────────────────────────────────

def add_to_waitlist(application_id: str, *,
                    priority: int = 0,
                    notes: str | None = None) -> str | None:
    """Add an application to the waitlist. Pulls student_id /
    building_id / room_type from the application row so the caller
    only has to supply the application_id.

    Returns the new ``waitlist_id`` or ``None`` on failure (already
    logged).
    """
    init_waitlist_schema()
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT student_id, preferred_building_id, preferred_room_type
                FROM housing_applications
                WHERE application_id = ?
            ''', (application_id,))
            row = cur.fetchone()
            if not row:
                logger.warning("add_to_waitlist: unknown application %s",
                               application_id)
                return None
            student_id, building_id, room_type = row

            # Avoid duplicates: an application already Waiting stays put.
            cur.execute('''
                SELECT waitlist_id FROM housing_waitlist
                WHERE application_id = ? AND status = 'Waiting'
            ''', (application_id,))
            existing = cur.fetchone()
            if existing:
                logger.info("add_to_waitlist: application %s already waiting (%s)",
                            application_id, existing[0])
                return existing[0]

            now = datetime.datetime.now().isoformat(timespec='seconds')
            wid = generate_id('WL')
            cur.execute('''
                INSERT INTO housing_waitlist
                (waitlist_id, application_id, student_id, building_id, room_type,
                 priority, status, notes, added_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'Waiting', ?, ?, ?)
            ''', (wid, application_id, student_id, building_id, room_type,
                  int(priority or 0), notes, now, now))
            conn.commit()
            logger.info("add_to_waitlist: %s queued for application %s "
                        "(building=%s, type=%s, priority=%d)",
                        wid, application_id, building_id, room_type,
                        int(priority or 0))
            return wid
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("add_to_waitlist failed for application %s",
                         application_id)
        return None


def remove(waitlist_id: str, *, reason: str | None = None) -> bool:
    """Mark a waitlist entry ``Removed``."""
    init_waitlist_schema()
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE housing_waitlist
                   SET status = 'Removed',
                       notes  = COALESCE(?, notes),
                       updated_at = ?
                 WHERE waitlist_id = ? AND status = 'Waiting'
            ''', (reason, now, waitlist_id))
            ok = cur.rowcount > 0
            conn.commit()
            if ok:
                logger.info("waitlist %s removed (reason=%s)",
                            waitlist_id, reason)
            else:
                logger.warning("waitlist %s could not be removed "
                               "(not found or already terminal)", waitlist_id)
            return ok
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("waitlist remove failed for %s", waitlist_id)
        return False


def find_next_match(*, building_id: str | None,
                    room_type: str | None) -> dict[str, Any] | None:
    """Return the highest-priority waitlist row that matches the given
    building/type, or ``None`` if no candidate exists.

    Matching rules: an entry with NULL ``building_id`` matches any
    building; same for ``room_type``. Specific values take precedence
    over wildcards via the ORDER BY.
    """
    init_waitlist_schema()
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT *
                FROM housing_waitlist
                WHERE status = 'Waiting'
                  AND (building_id IS NULL OR building_id = ?)
                  AND (room_type   IS NULL OR room_type   = ?)
                ORDER BY
                    (building_id IS NULL),
                    (room_type   IS NULL),
                    priority DESC,
                    added_at
                LIMIT 1
            ''', (building_id, room_type)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("find_next_match failed (building=%s, type=%s)",
                         building_id, room_type)
        return None


def mark_promoted(waitlist_id: str, assignment_id: str) -> bool:
    """Flag a waitlist row as ``Promoted`` and link the new assignment."""
    init_waitlist_schema()
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE housing_waitlist
                   SET status = 'Promoted',
                       promoted_to_assignment_id = ?,
                       updated_at = ?
                 WHERE waitlist_id = ?
            ''', (assignment_id, now, waitlist_id))
            ok = cur.rowcount > 0
            conn.commit()
            if ok:
                logger.info("waitlist %s promoted -> assignment %s",
                            waitlist_id, assignment_id)
            return ok
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("mark_promoted failed for %s", waitlist_id)
        return False


def promote_room_to_next(room_id: str, *, default_rent: float = 0.0,
                         created_by: str = 'system') -> dict[str, Any] | None:
    """When a room becomes available, find the next waitlist row that
    matches its building+type and create a new ``housing_assignments``
    row for the queued student. Returns a summary dict on success or
    ``None`` if no match exists / promotion failed.

    Does NOT collect a deposit or write any payment rows — that
    happens through the normal application/assignment workflow once
    the student confirms. The promoted row sits in ``Pending`` so
    staff can finish the paperwork.
    """
    init_waitlist_schema()
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT room_id, building_id, room_type, monthly_rent, status
                FROM housing_rooms WHERE room_id = ?
            ''', (room_id,))
            room = cur.fetchone()
            if not room:
                logger.warning("promote_room_to_next: unknown room %s", room_id)
                return None
            r_room_id, building_id, room_type, monthly_rent, status = room
            if status != 'Available':
                logger.info("promote_room_to_next: room %s status=%s — not free",
                            room_id, status)
                return None

            match = find_next_match(building_id=building_id, room_type=room_type)
            if not match:
                logger.info("promote_room_to_next: no waitlist match for "
                            "room=%s (building=%s, type=%s)",
                            room_id, building_id, room_type)
                return None

            now = datetime.datetime.now().isoformat(timespec='seconds')
            assignment_id = generate_id('ASG')
            rent = float(monthly_rent or default_rent or 0.0)

            cur.execute('''
                INSERT INTO housing_assignments
                (assignment_id, application_id, student_id, room_id,
                 move_in_date, planned_move_out_date, monthly_rent,
                 status, assigned_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
            ''', (
                assignment_id, match['application_id'], match['student_id'],
                room_id,
                now[:10],                                # move_in_date placeholder
                (datetime.date.fromisoformat(now[:10])
                 + datetime.timedelta(days=365)).isoformat(),
                rent, created_by, now, now,
            ))

            # Hold the room while paperwork completes.
            cur.execute('''
                UPDATE housing_rooms
                   SET status = 'Reserved',
                       current_occupants = current_occupants + 1,
                       updated_at = ?
                 WHERE room_id = ?
            ''', (now, room_id))

            cur.execute('''
                UPDATE housing_waitlist
                   SET status = 'Promoted',
                       promoted_to_assignment_id = ?,
                       updated_at = ?
                 WHERE waitlist_id = ?
            ''', (assignment_id, now, match['waitlist_id']))

            conn.commit()
            logger.info("promote_room_to_next: room %s -> waitlist %s -> "
                        "assignment %s (student %s)",
                        room_id, match['waitlist_id'],
                        assignment_id, match['student_id'])
            return {
                'room_id': room_id,
                'waitlist_id': match['waitlist_id'],
                'assignment_id': assignment_id,
                'student_id': match['student_id'],
            }
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("promote_room_to_next failed for room %s", room_id)
        return None
