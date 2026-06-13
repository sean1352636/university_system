"""Dashboard statistics for the Nursery System home screen.

Aggregates headline counts from across the shared ``nursery.db`` so the GUI
welcome screen (and any CLI summary) can show a live snapshot — children on
roll, staffing, the latest daily register, admissions pipeline and the
safeguarding/compliance picture — instead of empty placeholders.

All reads are defensive: a missing table or column yields ``0``/empty rather
than raising, so the dashboard still renders on a partially-seeded database.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)


@dataclass
class RoomOccupancy:
    name: str
    children: int
    capacity: int

    @property
    def label(self) -> str:
        if self.capacity:
            return f"{self.children} / {self.capacity}"
        return str(self.children)

    @property
    def full(self) -> bool:
        return bool(self.capacity) and self.children >= self.capacity


@dataclass
class DashboardStats:
    children_on_roll: int = 0
    staff_total: int = 0
    dsl_count: int = 0
    first_aider_count: int = 0
    dbs_checked: int = 0
    rooms_open: int = 0
    rooms_total: int = 0
    # Latest daily register
    register_date: str | None = None
    present: int = 0
    absent: int = 0
    register_total: int = 0
    # Admissions pipeline
    admissions_waiting: int = 0
    admissions_offered: int = 0
    # Safeguarding / welfare
    accidents_recent: int = 0
    open_concerns: int = 0
    medications_recent: int = 0
    # Comms
    email_drafts: int = 0
    email_sent: int = 0
    # Per-room breakdown
    rooms: list[RoomOccupancy] = field(default_factory=list)

    @property
    def attendance_pct(self) -> int | None:
        if not self.register_total:
            return None
        return round(100 * self.present / self.register_total)


def _scalar(conn: sqlite3.Connection, sql: str, *params) -> int:
    try:
        row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.Error:
        logger.debug("dashboard query failed: %s", sql, exc_info=True)
        return 0


def _value(conn: sqlite3.Connection, sql: str, *params):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        logger.debug("dashboard query failed: %s", sql, exc_info=True)
        return None


def _room_occupancy(conn: sqlite3.Connection) -> list[RoomOccupancy]:
    """Children-per-room against each room's capacity.

    Rooms are listed from the ``rooms`` table (so empty rooms still show), with
    a left join onto the active children grouped by their room name.
    """
    try:
        rows = conn.execute(
            """
            SELECT r.name AS name,
                   COALESCE(r.capacity, 0) AS capacity,
                   COALESCE(c.n, 0) AS children
            FROM rooms r
            LEFT JOIN (
                SELECT room, COUNT(*) AS n FROM pupils
                WHERE status = 'active' GROUP BY room
            ) c ON c.room = r.name
            WHERE r.status = 'open' OR r.status IS NULL
            ORDER BY r.min_age_months, r.name
            """
        ).fetchall()
    except sqlite3.Error:
        logger.debug("room occupancy query failed", exc_info=True)
        return []
    return [RoomOccupancy(name=r["name"], children=r["children"],
                          capacity=r["capacity"]) for r in rows]


def get_stats() -> DashboardStats:
    """Collect a live snapshot of the setting. Never raises for missing data."""
    init_db()
    s = DashboardStats()
    try:
        conn = connect()
    except sqlite3.Error:
        logger.exception("Dashboard could not open the nursery DB")
        return s
    try:
        s.children_on_roll = _scalar(
            conn, "SELECT COUNT(*) FROM pupils WHERE status = 'active'")
        s.staff_total = _scalar(conn, "SELECT COUNT(*) FROM staff")
        s.dsl_count = _scalar(conn, "SELECT COUNT(*) FROM staff WHERE is_dsl = 1")
        s.first_aider_count = _scalar(
            conn, "SELECT COUNT(*) FROM staff WHERE is_paediatric_first_aider = 1")
        s.dbs_checked = _scalar(
            conn, "SELECT COUNT(*) FROM staff WHERE dbs_checked = 1")
        s.rooms_total = _scalar(conn, "SELECT COUNT(*) FROM rooms")
        s.rooms_open = _scalar(
            conn, "SELECT COUNT(*) FROM rooms WHERE status = 'open'")

        s.register_date = _value(
            conn, "SELECT MAX(attend_date) FROM attendance_records")
        if s.register_date:
            s.present = _scalar(
                conn, "SELECT COUNT(*) FROM attendance_records "
                "WHERE attend_date = ? AND status = 'present'", s.register_date)
            s.absent = _scalar(
                conn, "SELECT COUNT(*) FROM attendance_records "
                "WHERE attend_date = ? AND status = 'absent'", s.register_date)
            s.register_total = _scalar(
                conn, "SELECT COUNT(*) FROM attendance_records "
                "WHERE attend_date = ?", s.register_date)

        s.admissions_waiting = _scalar(
            conn, "SELECT COUNT(*) FROM admissions WHERE status = 'waiting'")
        s.admissions_offered = _scalar(
            conn, "SELECT COUNT(*) FROM admissions WHERE status = 'offered'")

        s.accidents_recent = _scalar(
            conn, "SELECT COUNT(*) FROM accident_records "
            "WHERE occurred_date >= date('now', '-7 day')")
        s.medications_recent = _scalar(
            conn, "SELECT COUNT(*) FROM medication_log "
            "WHERE administered_date >= date('now', '-7 day')")
        s.open_concerns = _scalar(
            conn, "SELECT COUNT(*) FROM concerns "
            "WHERE status NOT IN ('closed', 'resolved')")

        s.email_drafts = _scalar(
            conn, "SELECT COUNT(*) FROM email_messages WHERE status = 'Draft'")
        s.email_sent = _scalar(
            conn, "SELECT COUNT(*) FROM email_messages WHERE status = 'Sent'")

        s.rooms = _room_occupancy(conn)
    finally:
        conn.close()
    return s
