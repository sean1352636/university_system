"""WellbeingService service for the University System."""

import logging
import sqlite3
import traceback
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import connect
from education_system.post_18.university_system.core.sql_safety import validate_identifier

logger = logging.getLogger(__name__)


def _send_student_affairs_email(template_name: str, recipient_email: str,
                                vars_: dict) -> bool:
    """Render ``student_affairs/<template_name>`` and dispatch best-effort.

    Skips silently when *recipient_email* is empty."""
    if not recipient_email:
        return False
    try:
        from education_system.post_18.university_system.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.post_18.university_system.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    subject, body = render_template(f"student_affairs/{template_name}", vars_)
    if not subject or not body:
        logger.error("template render failed: student_affairs/%s", template_name)
        return False
    try:
        send_email(recipient_email=recipient_email, subject=subject, body=body)
        return True
    except Exception:
        logger.exception("send_email failed student_affairs/%s recipient=%s",
                         template_name, recipient_email)
        return False


def _lookup_student_email(conn, student_id):
    """Best-effort: pull email + display name from the ``students`` table.
    Returns (name, email) — either field may be empty."""
    try:
        row = conn.execute(
            "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name,"
            "       COALESCE(email_address,'') AS email"
            "  FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        if row:
            return ((row['name'] or '').strip(), (row['email'] or '').strip())
    except sqlite3.OperationalError:
        pass
    return ('', '')


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
    def create_checkin(self, student_id, mood_rating=None, notes=None, logged_by=None,
                       reason_summary="", send_email_notice=True):
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
            checkin_id = cur.lastrowid
            if send_email_notice:
                name, email = _lookup_student_email(conn, student_id)
                _send_student_affairs_email('welfare_checkin', email, {
                    'student_name':    name or student_id,
                    'checkin_id':      checkin_id,
                    'logged_by':       logged_by or '(member of staff)',
                    'checkin_date':    datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'mood_summary':    f"{mood_rating}/10" if mood_rating is not None else '(not recorded)',
                    'reason_summary':  reason_summary or '(general check-in)',
                    'checkin_notes':   notes or '(no notes added)',
                })
            return checkin_id
        finally:
            conn.close()

    def send_disciplinary_letter(self, student_id, allegation, sanctions="",
                                 findings="(see attached case file)",
                                 case_reference="", incident_date="",
                                 reported_by="(member of staff)",
                                 decision_maker="Office of Student Conduct",
                                 matter_stage="Formal letter",
                                 response_by="(within 10 working days)"):
        """Email a student a disciplinary letter. Best-effort."""
        conn = self._conn()
        try:
            name, email = _lookup_student_email(conn, student_id)
        finally:
            conn.close()
        return _send_student_affairs_email('disciplinary_letter', email, {
            'student_id':     student_id,
            'student_name':   name or student_id,
            'case_reference': case_reference or f"SC-{student_id}-{datetime.now().strftime('%Y%m%d')}",
            'incident_date':  incident_date or '(unspecified)',
            'reported_by':    reported_by,
            'letter_date':    datetime.now().strftime('%Y-%m-%d'),
            'decision_maker': decision_maker,
            'matter_stage':   matter_stage,
            'allegation':     allegation,
            'findings':       findings,
            'sanctions':      sanctions or '(see case file)',
            'response_by':    response_by,
        })

    def send_support_referral(self, student_id, referral_service,
                              referred_by, referral_reason,
                              referred_by_role="Member of Staff",
                              concern_type="general",
                              urgency="normal",
                              expected_response_days="3",
                              urgent_contact="the Student Wellbeing Service (wellbeing@university.edu)"):
        """Create a wellbeing referral row and email the student to flag it."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO wellbeing_referrals
                       (student_id, referred_by, concern_type, description, urgency)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, referred_by, concern_type, referral_reason, urgency),
            )
            conn.commit()
            referral_id = cur.lastrowid
            name, email = _lookup_student_email(conn, student_id)
        finally:
            conn.close()
        _send_student_affairs_email('support_referral', email, {
            'student_id':              student_id,
            'student_name':            name or student_id,
            'referral_id':             referral_id,
            'referral_service':        referral_service,
            'referred_by':             referred_by,
            'referred_by_role':        referred_by_role,
            'referral_date':           datetime.now().strftime('%Y-%m-%d'),
            'urgency':                 urgency,
            'concern_type':            concern_type,
            'referral_reason':         referral_reason,
            'expected_response_days':  expected_response_days,
            'urgent_contact':          urgent_contact,
        })
        return referral_id

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
        except Exception:
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
        except Exception:
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

