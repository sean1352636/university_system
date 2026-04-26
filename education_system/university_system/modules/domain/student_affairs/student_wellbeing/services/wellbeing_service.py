"""WellbeingService service for the University System."""

import logging
import sqlite3
import traceback
from datetime import datetime

from education_system.university_system.infrastructure.database.db import connect
from education_system.university_system.core.sql_safety import validate_identifier

logger = logging.getLogger(__name__)


class WellbeingService:
    """CRUD operations for wellbeing referral."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        # The low-level connect() doesn't set a row_factory; this service
        # returns rows as dicts (`dict(r)`), which only works when the
        # connection yields ``sqlite3.Row`` objects.
        conn = connect(self._db_path)
        conn.row_factory = sqlite3.Row
        self._ensure_schema(conn)
        return conn

    @staticmethod
    def _ensure_schema(conn):
        # The wellbeing tables live in new_features_schemas.get_new_features_tables(),
        # which is not wired into initialize_all_schemas(). Create them on demand
        # so the GUI/CLI work on a fresh DB.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wellbeing_referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                referred_by TEXT NOT NULL,
                concern_type TEXT NOT NULL,
                description TEXT,
                urgency TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wellbeing_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                mood_rating INTEGER,
                notes TEXT,
                logged_by TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()

    def list_student_ids(self):
        """Return list of (student_id, display_label) for dropdowns.

        Falls back to student IDs already seen in referrals/check-ins if the
        ``students`` table is missing (e.g. a stripped-down dev DB).
        """
        conn = self._conn()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT student_id, first_name, last_name FROM students "
                    "ORDER BY student_id"
                )
                rows = cur.fetchall()
                return [
                    (r["student_id"],
                     f"{r['student_id']} — {(r['first_name'] or '').strip()} "
                     f"{(r['last_name'] or '').strip()}".rstrip(" —"))
                    for r in rows
                ]
            except sqlite3.OperationalError:
                cur.execute(
                    "SELECT DISTINCT student_id FROM ("
                    "  SELECT student_id FROM wellbeing_referrals"
                    "  UNION SELECT student_id FROM wellbeing_checkins"
                    ") ORDER BY student_id"
                )
                return [(r[0], r[0]) for r in cur.fetchall() if r[0]]
        finally:
            conn.close()

    # ----- check-ins (staff-side log against referred students) ----------
    def create_checkin(self, student_id, mood_rating=None, notes=None, logged_by=None):
        if not student_id:
            raise ValueError("student_id required")
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO wellbeing_checkins (student_id, mood_rating, notes, logged_by) "
                "VALUES (?, ?, ?, ?)",
                (student_id, mood_rating, notes, logged_by),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_checkins(self, student_id=None, limit=100):
        conn = self._conn()
        try:
            cur = conn.cursor()
            if student_id:
                cur.execute(
                    "SELECT * FROM wellbeing_checkins WHERE student_id = ? "
                    "ORDER BY id DESC LIMIT ?", (student_id, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM wellbeing_checkins ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # ----- summary aggregations ------------------------------------------
    def summary(self):
        """Aggregate counts across referrals + check-ins for the Summary tab."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            out = {
                "referrals_total": 0,
                "referrals_by_status": {},
                "referrals_by_urgency": {},
                "referrals_auto": 0,
                "referrals_manual": 0,
                "checkins_total": 0,
                "avg_mood": None,
                "recent_referrals": [],
            }
            cur.execute("SELECT COUNT(*) FROM wellbeing_referrals")
            out["referrals_total"] = cur.fetchone()[0]
            cur.execute(
                "SELECT status, COUNT(*) FROM wellbeing_referrals GROUP BY status"
            )
            out["referrals_by_status"] = {r[0] or "unknown": r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT urgency, COUNT(*) FROM wellbeing_referrals GROUP BY urgency"
            )
            out["referrals_by_urgency"] = {r[0] or "unknown": r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT COUNT(*) FROM wellbeing_referrals WHERE referred_by = 'absence_tracker'"
            )
            out["referrals_auto"] = cur.fetchone()[0]
            out["referrals_manual"] = out["referrals_total"] - out["referrals_auto"]
            cur.execute("SELECT COUNT(*), AVG(mood_rating) FROM wellbeing_checkins")
            row = cur.fetchone()
            out["checkins_total"] = row[0] or 0
            out["avg_mood"] = round(row[1], 2) if row[1] is not None else None
            cur.execute(
                "SELECT id, student_id, concern_type, urgency, status, created_at "
                "FROM wellbeing_referrals ORDER BY id DESC LIMIT 5"
            )
            out["recent_referrals"] = [dict(r) for r in cur.fetchall()]
            return out
        finally:
            conn.close()

    def create(self, **kwargs):
        """Create a new wellbeing referral record."""
        conn = self._conn()
        try:
            cols = ", ".join(validate_identifier(k, "column") for k in kwargs)
            placeholders = ", ".join("?" for _ in kwargs)
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO wellbeing_referrals ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_all(self, limit=100, offset=0, **filters):
        """List wellbeing referral records with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM wellbeing_referrals WHERE 1=1"
            params = []
            for key, val in filters.items():
                if val is not None:
                    sql += f" AND {validate_identifier(key, 'column')} = ?"
                    params.append(val)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get(self, record_id):
        """Get a single wellbeing referral by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM wellbeing_referrals WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        """Update a wellbeing referral record."""
        if not kwargs:
            return False
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{validate_identifier(k, 'column')} = ?" for k in kwargs)
            values = list(kwargs.values()) + [record_id]
            conn.execute(
                f"UPDATE wellbeing_referrals SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, record_id):
        """Delete a wellbeing referral record."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM wellbeing_referrals WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

