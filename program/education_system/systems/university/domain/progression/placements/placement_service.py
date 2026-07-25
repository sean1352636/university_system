"""
Tkinter-free data/service layer for the Placement Hours Tracker.

The canonical `Database` wrapper lives here so both the Tkinter GUI
(`placement_tracker.py`) and the text CLI (`cli/placements_cli.py`)
share one persistence path — no SQL is duplicated in the CLI. Rows
written via either interface are visible in the other.

Persistence: basic student identity lives in canonical `students`;
placement-specific data is split into `placement_profiles` and
`placement_hours_log` in the shared `student_records.db`.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# T-Level minimum required hours (industry placement requirement)
REQUIRED_HOURS = 315

# Legacy local DB file — data now lives in the central student_records.db.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "placement_tracker.db")


def _remove_legacy_db() -> None:
    """Delete the old per-module placement_tracker.db (and WAL/SHM
    siblings) — data now lives in the central student_records.db."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy placement_tracker DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class Database:
    """Wraps the central `student_records.db` via the shared
    `get_connection`. Basic student identity lives in canonical
    `students`; placement-specific data is split into side tables
    `placement_profiles` and `placement_hours_log`.

    Method return shapes preserve the leading row-identity element used
    as the WHERE-clause key (the TEXT student_id or the integer
    hours-log id)."""

    def __init__(self, db_name=None):
        from education_system.systems.university.infrastructure.database.db import get_connection
        self.conn = get_connection()
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT,
                course TEXT
            );

            CREATE TABLE IF NOT EXISTS placement_profiles (
                student_id TEXT PRIMARY KEY,
                cohort     TEXT,
                employer   TEXT,
                supervisor TEXT,
                start_date TEXT,
                end_date   TEXT
            );

            CREATE TABLE IF NOT EXISTS placement_hours_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                log_date TEXT NOT NULL,
                hours REAL NOT NULL,
                activity TEXT,
                supervisor_signoff INTEGER DEFAULT 0,
                notes TEXT
            );
        """)
        self.conn.commit()

    # ---------- Student CRUD ----------
    def add_student(self, data):
        """data = (student_id, first_name, last_name, course, cohort,
        email, employer, supervisor, start_date, end_date)."""
        sid, first, last, course, cohort, email, employer, supervisor, start, end = data
        self.cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, course, email_address)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                course=excluded.course,
                email_address=excluded.email_address
        """, (sid, first, last, course, email))
        self.cursor.execute("""
            INSERT INTO placement_profiles
                (student_id, cohort, employer, supervisor, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                cohort=excluded.cohort,
                employer=excluded.employer,
                supervisor=excluded.supervisor,
                start_date=excluded.start_date,
                end_date=excluded.end_date
        """, (sid, cohort, employer, supervisor, start, end))
        self.conn.commit()
        return sid

    def update_student(self, student_pk, data):
        """student_pk is the original student_id (TEXT) being edited.
        If the dialog renames the student_id, cascade-rename across the
        three tables to keep the join key consistent."""
        old_sid = student_pk
        new_sid = data[0]
        sid, first, last, course, cohort, email, employer, supervisor, start, end = data
        if new_sid != old_sid:
            self.cursor.execute("UPDATE students SET student_id=? WHERE student_id=?",
                                (new_sid, old_sid))
            self.cursor.execute("UPDATE placement_profiles SET student_id=? WHERE student_id=?",
                                (new_sid, old_sid))
            self.cursor.execute("UPDATE placement_hours_log SET student_id=? WHERE student_id=?",
                                (new_sid, old_sid))
        self.cursor.execute("""
            UPDATE students SET first_name=?, last_name=?, course=?, email_address=?
            WHERE student_id=?
        """, (first, last, course, email, new_sid))
        self.cursor.execute("""
            INSERT INTO placement_profiles
                (student_id, cohort, employer, supervisor, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                cohort=excluded.cohort,
                employer=excluded.employer,
                supervisor=excluded.supervisor,
                start_date=excluded.start_date,
                end_date=excluded.end_date
        """, (new_sid, cohort, employer, supervisor, start, end))
        self.conn.commit()

    def delete_student(self, student_pk):
        """Remove placement enrollment for a student. The canonical
        `students` row is left intact — it's shared with the rest of the
        system and may be referenced by other modules."""
        self.cursor.execute("DELETE FROM placement_hours_log WHERE student_id=?",
                            (student_pk,))
        self.cursor.execute("DELETE FROM placement_profiles WHERE student_id=?",
                            (student_pk,))
        self.conn.commit()

    def get_all_students(self, search=""):
        """Return rows for students that have a placement_profile.
        Shape: (id, student_id, first, last, course, cohort, employer)."""
        base = """
            SELECT s.student_id AS id, s.student_id, s.first_name, s.last_name,
                   s.course, p.cohort, p.employer
            FROM placement_profiles p
            JOIN students s ON s.student_id = p.student_id
        """
        if search:
            q = f"%{search}%"
            self.cursor.execute(base + """
                WHERE s.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
                   OR s.course LIKE ? OR p.employer LIKE ?
                ORDER BY s.last_name, s.first_name
            """, (q, q, q, q, q))
        else:
            self.cursor.execute(base + " ORDER BY s.last_name, s.first_name")
        return self.cursor.fetchall()

    def get_student(self, student_pk):
        """Shape: (id, student_id, first, last, course, cohort, email,
        employer, supervisor, start_date, end_date)."""
        self.cursor.execute("""
            SELECT s.student_id AS id, s.student_id, s.first_name, s.last_name,
                   s.course, p.cohort, s.email_address, p.employer, p.supervisor,
                   p.start_date, p.end_date
            FROM students s
            LEFT JOIN placement_profiles p ON p.student_id = s.student_id
            WHERE s.student_id = ?
        """, (student_pk,))
        return self.cursor.fetchone()

    # ---------- Hours CRUD ----------
    def add_hours(self, student_pk, log_date, hours, activity, signoff, notes):
        self.cursor.execute("""
            INSERT INTO placement_hours_log
                (student_id, log_date, hours, activity, supervisor_signoff, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_pk, log_date, hours, activity, signoff, notes))
        self.conn.commit()

    def update_hours(self, log_pk, log_date, hours, activity, signoff, notes):
        self.cursor.execute("""
            UPDATE placement_hours_log SET log_date=?, hours=?, activity=?,
                                 supervisor_signoff=?, notes=?
            WHERE id=?
        """, (log_date, hours, activity, signoff, notes, log_pk))
        self.conn.commit()

    def delete_hours(self, log_pk):
        self.cursor.execute("DELETE FROM placement_hours_log WHERE id=?", (log_pk,))
        self.conn.commit()

    def get_hours_for_student(self, student_pk):
        self.cursor.execute("""
            SELECT id, log_date, hours, activity, supervisor_signoff, notes
            FROM placement_hours_log WHERE student_id=? ORDER BY log_date DESC
        """, (student_pk,))
        return self.cursor.fetchall()

    def get_total_hours(self, student_pk):
        self.cursor.execute("""
            SELECT COALESCE(SUM(hours), 0) FROM placement_hours_log WHERE student_id=?
        """, (student_pk,))
        return self.cursor.fetchone()[0]

    def get_signed_off_hours(self, student_pk):
        self.cursor.execute("""
            SELECT COALESCE(SUM(hours), 0) FROM placement_hours_log
            WHERE student_id=? AND supervisor_signoff=1
        """, (student_pk,))
        return self.cursor.fetchone()[0]

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def export_summary_rows(db: Database) -> list[list]:
    """Build the placement-progress summary rows the GUI's CSV export
    produces, as a list of lists (header first). Kept here so the CLI
    can render/export the same data without any Tkinter dependency."""
    rows: list[list] = [[
        "Student ID", "Name", "Course", "Cohort", "Employer",
        "Total Hours", "Signed-off Hours", "Required", "Remaining", "% Complete",
    ]]
    for s in db.get_all_students():
        pk, sid, fn, ln, course, cohort, employer = s
        total = db.get_total_hours(pk)
        signed = db.get_signed_off_hours(pk)
        remaining = max(0, REQUIRED_HOURS - signed)
        pct = (signed / REQUIRED_HOURS * 100) if REQUIRED_HOURS else 0
        rows.append([sid, f"{fn} {ln}", course, cohort or "", employer or "",
                     f"{total:.1f}", f"{signed:.1f}", REQUIRED_HOURS,
                     f"{remaining:.1f}", f"{pct:.1f}%"])
    return rows


def submit_as_apl_evidence(db: Database, student_pk) -> int:
    """Push a student's placement hours into a draft APL/RPL
    ``work_experience`` claim. Returns the claim id."""
    s = db.get_student(student_pk)
    if not s:
        raise ValueError(f"No student with id {student_pk}")
    student_id = s[1]
    course = s[4] or None
    employer = s[7] or "Placement employer"
    date_range: Optional[str] = None
    if s[9] or s[10]:
        date_range = f"{s[9] or '?'} → {s[10] or '?'}"
    total_hours = float(db.get_total_hours(student_pk) or 0)
    signed_hours = float(db.get_signed_off_hours(student_pk) or 0)
    from education_system.systems.university.domain.admissions.prior_learning_recognition.services.prior_learning_service import (
        PriorLearningService,
    )
    return PriorLearningService().create_evidence_from_placement(
        student_id,
        employer=employer,
        total_hours=total_hours,
        signed_off_hours=signed_hours,
        date_range=date_range,
        target_course=course,
    )
