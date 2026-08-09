"""
Tkinter-free data/service layer for the Apprenticeship module.

The canonical `Database` wrapper (schema bootstrap + thin execute/fetch
helpers over the shared `student_records.db`) lives here so both the
Tkinter GUI (`apprenticeship_system.py`) and the text CLI
(`cli/apprenticeships_cli.py`) share one persistence path — no SQL is
duplicated in the CLI. Rows created via either interface are visible in
the other.

Tables (canonical, shared with the rest of the system):
`students`, `employers`, `apprenticeships`, `applications`.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)

# Legacy local DB file — data now lives in the central student_records.db.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "apprenticeships.db")


def _remove_legacy_db() -> None:
    """Delete the old per-module apprenticeships.db (and WAL/SHM
    siblings) — data now lives in the central student_records.db."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy apprenticeships DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class Database:
    """Wraps the central `student_records.db` via the shared
    `get_connection` and uses the canonical `students`, `employers`,
    `apprenticeships`, and `applications` tables so apprenticeship
    rows live alongside the rest of the system's data."""

    def __init__(self, db_name=None):
        from education_system.systems.university.infrastructure.database.db import get_connection
        self.conn = get_connection()
        # The canonical `apprenticeships` and `applications` tables ship
        # with FK declarations referencing non-existent parent columns,
        # so enforcing them rejects every INSERT — leave FKs OFF and
        # enforce relationships logically in the DELETE cleanup helpers.
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.ensure_schema()
        self._cleanup_module_private_tables()

    def ensure_schema(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT,
                course TEXT,
                year_of_study INTEGER
            );

            CREATE TABLE IF NOT EXISTS employers (
                employer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT UNIQUE NOT NULL,
                contact_person TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                industry TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS apprenticeships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                employer_id INTEGER NOT NULL,
                description TEXT,
                duration_months INTEGER NOT NULL,
                salary REAL,
                location TEXT,
                required_course TEXT,
                min_year INTEGER DEFAULT 1,
                positions_available INTEGER DEFAULT 1,
                status TEXT DEFAULT 'Open',
                posted_date TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                apprenticeship_id INTEGER NOT NULL,
                application_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Pending',
                notes TEXT,
                UNIQUE(student_id, apprenticeship_id)
            );
        """)
        existing_student_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(students)")}
        if "gpa" not in existing_student_cols:
            self.conn.execute("ALTER TABLE students ADD COLUMN gpa REAL")
            logger.info("Added students.gpa column")
        existing_employer_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(employers)")}
        if "address" not in existing_employer_cols:
            self.conn.execute("ALTER TABLE employers ADD COLUMN address TEXT")
            logger.info("Added employers.address column")
        self.conn.commit()

    def _cleanup_module_private_tables(self):
        for tbl in ("apprenticeship_applications", "apprenticeship_listings",
                    "apprenticeship_employers", "apprenticeship_students"):
            try:
                row = self.conn.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'"
                ).fetchone()
                if not row:
                    continue
                count = self.conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                if count == 0:
                    self.conn.execute(f"DROP TABLE {tbl}")
                    logger.info("Dropped empty legacy table %s", tbl)
                else:
                    logger.warning(
                        "Legacy table %s still has %d row(s); leaving in place.",
                        tbl, count,
                    )
            except sqlite3.Error:
                logger.debug("Could not inspect/drop %s", tbl, exc_info=True)
        self.conn.commit()

    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor

    def fetch_all(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def fetch_one(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


class ApprenticeshipService:
    """CLI/GUI-agnostic operations over the apprenticeship tables.

    Every method returns plain dicts / ids so a text UI can render them
    without knowing any SQL. All persistence goes through the shared
    `Database` wrapper above.
    """

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def close(self):
        self.db.close()

    # ---------------- Students ----------------
    _STUDENT_COLS = ["student_id", "first_name", "last_name", "email_address",
                     "course", "year_of_study", "gpa"]

    def list_students(self, search: str = "") -> list[dict]:
        if search:
            q = f"%{search}%"
            rows = self.db.fetch_all(
                """SELECT student_id, first_name, last_name, email_address,
                          course, year_of_study, gpa
                   FROM students
                   WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                      OR email_address LIKE ? OR course LIKE ?
                   ORDER BY last_name""", (q, q, q, q, q))
        else:
            rows = self.db.fetch_all(
                """SELECT student_id, first_name, last_name, email_address,
                          course, year_of_study, gpa
                   FROM students ORDER BY last_name""")
        return [dict(zip(self._STUDENT_COLS, r)) for r in rows]

    def add_student(self, student_id, first_name, last_name, email, course,
                    year_of_study=0, gpa=None) -> str:
        self.db.execute(
            """INSERT INTO students
                   (student_id, first_name, last_name, email_address,
                    course, year_of_study, gpa)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, first_name, last_name, email, course, year_of_study, gpa))
        return student_id

    def update_student(self, old_student_id, student_id, first_name, last_name,
                       email, course, year_of_study=0, gpa=None) -> None:
        # Cascade-clear the student's applications first (the canonical
        # schema doesn't enforce ON DELETE CASCADE for the TEXT key).
        self.db.execute("DELETE FROM applications WHERE student_id=?", (old_student_id,))
        self.db.execute(
            """UPDATE students SET student_id=?, first_name=?, last_name=?,
                   email_address=?, course=?, year_of_study=?, gpa=?
               WHERE student_id=?""",
            (student_id, first_name, last_name, email, course,
             year_of_study, gpa, old_student_id))

    def delete_student(self, student_id) -> None:
        self.db.execute("DELETE FROM applications WHERE student_id=?", (student_id,))
        self.db.execute("DELETE FROM students WHERE student_id=?", (student_id,))

    # ---------------- Employers ----------------
    _EMPLOYER_COLS = ["employer_id", "company_name", "contact_person",
                      "contact_email", "contact_phone", "industry", "address"]

    def list_employers(self) -> list[dict]:
        rows = self.db.fetch_all(
            """SELECT employer_id, company_name, contact_person, contact_email,
                      contact_phone, industry, address
               FROM employers ORDER BY company_name""")
        return [dict(zip(self._EMPLOYER_COLS, r)) for r in rows]

    def add_employer(self, company_name, contact_person, email,
                     phone="", industry="", address="") -> int:
        cur = self.db.execute(
            """INSERT INTO employers
                   (company_name, contact_person, contact_email,
                    contact_phone, industry, address)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (company_name, contact_person, email, phone, industry, address))
        return cur.lastrowid

    def update_employer(self, employer_id, company_name, contact_person, email,
                        phone="", industry="", address="") -> None:
        self.db.execute(
            """UPDATE employers SET company_name=?, contact_person=?,
                   contact_email=?, contact_phone=?, industry=?, address=?
               WHERE employer_id=?""",
            (company_name, contact_person, email, phone, industry, address,
             employer_id))

    def delete_employer(self, employer_id) -> None:
        self.db.execute(
            "DELETE FROM applications WHERE apprenticeship_id IN "
            "(SELECT id FROM apprenticeships WHERE employer_id=?)", (employer_id,))
        self.db.execute("DELETE FROM apprenticeships WHERE employer_id=?", (employer_id,))
        self.db.execute("DELETE FROM employers WHERE employer_id=?", (employer_id,))

    # ---------------- Apprenticeships ----------------
    _APP_COLS = ["id", "title", "company_name", "duration_months", "salary",
                 "location", "required_course", "min_year",
                 "positions_available", "status"]

    def list_apprenticeships(self, status: Optional[str] = None) -> list[dict]:
        query = """SELECT a.id, a.title, e.company_name, a.duration_months,
                          a.salary, a.location, a.required_course, a.min_year,
                          a.positions_available, a.status
                   FROM apprenticeships a
                   JOIN employers e ON a.employer_id = e.employer_id"""
        params = ()
        if status:
            query += " WHERE a.status = ?"
            params = (status,)
        query += " ORDER BY a.posted_date DESC"
        rows = self.db.fetch_all(query, params)
        return [dict(zip(self._APP_COLS, r)) for r in rows]

    def add_apprenticeship(self, title, employer_id, duration_months,
                           description="", salary=None, location="",
                           required_course="", min_year=1,
                           positions_available=1, status="Open") -> int:
        cur = self.db.execute(
            """INSERT INTO apprenticeships
                   (title, employer_id, description, duration_months, salary,
                    location, required_course, min_year, positions_available, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, employer_id, description, duration_months, salary, location,
             required_course, min_year, positions_available, status))
        return cur.lastrowid

    def update_apprenticeship(self, app_id, title, employer_id, duration_months,
                              description="", salary=None, location="",
                              required_course="", min_year=1,
                              positions_available=1, status="Open") -> None:
        self.db.execute(
            """UPDATE apprenticeships SET title=?, employer_id=?, description=?,
                   duration_months=?, salary=?, location=?, required_course=?,
                   min_year=?, positions_available=?, status=?
               WHERE id=?""",
            (title, employer_id, description, duration_months, salary, location,
             required_course, min_year, positions_available, status, app_id))

    def delete_apprenticeship(self, app_id) -> None:
        self.db.execute("DELETE FROM applications WHERE apprenticeship_id=?", (app_id,))
        self.db.execute("DELETE FROM apprenticeships WHERE id=?", (app_id,))

    # ---------------- Applications ----------------
    _APPLICATION_COLS = ["id", "student_name", "student_id", "title",
                         "company_name", "application_date", "status"]

    def list_applications(self, status: Optional[str] = None) -> list[dict]:
        query = """SELECT app.id, s.first_name || ' ' || s.last_name, s.student_id,
                          ap.title, e.company_name, app.application_date, app.status
                   FROM applications app
                   JOIN students s ON app.student_id = s.student_id
                   JOIN apprenticeships ap ON app.apprenticeship_id = ap.id
                   JOIN employers e ON ap.employer_id = e.employer_id"""
        params = ()
        if status:
            query += " WHERE app.status = ?"
            params = (status,)
        query += " ORDER BY app.application_date DESC"
        rows = self.db.fetch_all(query, params)
        return [dict(zip(self._APPLICATION_COLS, r)) for r in rows]

    def submit_application(self, student_id, apprenticeship_id,
                           status="Pending", notes="") -> int:
        cur = self.db.execute(
            """INSERT INTO applications (student_id, apprenticeship_id, status, notes)
               VALUES (?, ?, ?, ?)""",
            (student_id, apprenticeship_id, status, notes))
        return cur.lastrowid

    def update_application_status(self, app_id, status, notes=None) -> None:
        if notes is None:
            self.db.execute("UPDATE applications SET status=? WHERE id=?",
                            (status, app_id))
        else:
            self.db.execute("UPDATE applications SET status=?, notes=? WHERE id=?",
                            (status, notes, app_id))

    def delete_application(self, app_id) -> None:
        self.db.execute("DELETE FROM applications WHERE id=?", (app_id,))

    # ---------------- APL evidence ----------------
    def submit_as_apl(self, student_id, course: Optional[str] = None) -> int:
        """Open or create a draft APL/RPL ``work_experience`` claim for a
        student, seeded from their most recent apprenticeship employer.
        Returns the claim id."""
        employer = "Apprenticeship employer"
        try:
            row = self.db.fetch_one(
                """SELECT e.company_name FROM applications a
                   JOIN apprenticeships ap ON a.apprenticeship_id = ap.id
                   JOIN employers e ON ap.employer_id = e.employer_id
                   WHERE a.student_id = ?
                   ORDER BY a.id DESC LIMIT 1""",
                (student_id,))
            if row and row[0]:
                employer = row[0]
        except Exception:
            logger.debug("Could not resolve employer for APL evidence", exc_info=True)
        from education_system.systems.university.domain.admissions.prior_learning_recognition.services.prior_learning_service import (
            PriorLearningService,
        )
        return PriorLearningService().create_evidence_from_placement(
            student_id,
            employer=employer,
            total_hours=0.0,
            signed_off_hours=0.0,
            target_course=course,
        )
