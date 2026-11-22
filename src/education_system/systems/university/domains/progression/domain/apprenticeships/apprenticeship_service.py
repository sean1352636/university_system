"""
Legacy careers listings and applications for university students.

This is not the authoritative apprenticeship learner system and must not be
used for degree-apprenticeship enrolment, KSB, gateway, EPA or funding data.
Those records live under ``systems.apprenticeships`` and are joined to the
university through the shared journey and durable degree events.

Tkinter-free data/service layer for the Apprenticeship listings module.

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
        # Foreign keys stay ON (as everywhere in this repo): `apprenticeships`
        # references employers(employer_id) and `applications` references
        # apprenticeships(id) and students(student_id), all real tables
        # with those keys. The DELETE helpers below still clear children
        # first so a delete never depends on the ON DELETE clause.
        self.conn.execute("PRAGMA foreign_keys = ON")
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
                posted_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                apprenticeship_id INTEGER NOT NULL,
                application_date TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Pending',
                notes TEXT,
                UNIQUE(student_id, apprenticeship_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                FOREIGN KEY (apprenticeship_id) REFERENCES apprenticeships(id) ON DELETE CASCADE
            );
        """)
        # An application is made to a *programme at an employer*, both owned
        # by the apprenticeships system. Without the employer on the row,
        # the record can't say who the application was routed to.
        existing_application_cols = {
            r[1] for r in self.conn.execute("PRAGMA table_info(applications)")
        }
        if existing_application_cols and "employer_id" not in existing_application_cols:
            try:
                self.conn.execute("ALTER TABLE applications ADD COLUMN employer_id INTEGER")
            except sqlite3.OperationalError:
                logger.debug("applications.employer_id already present")

        # (students is owned by Student Records; nothing is added to it here.
        # An older version added a US-style ``gpa`` column — it is left in
        # place on databases that have it, but no longer read or created.)
        existing_employer_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(employers)")}
        if "address" not in existing_employer_cols:
            self.conn.execute("ALTER TABLE employers ADD COLUMN address TEXT")
            logger.info("Added employers.address column")
        self.conn.commit()

    def _cleanup_module_private_tables(self):
        for tbl in ("apprenticeship_applications", "apprenticeship_listings",
                    "apprenticeship_employers", "apprenticeship_students"):
            try:
                # db-audit: ignore[DBW001] - literal collection
                row = self.conn.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'"
                ).fetchone()
                if not row:
                    continue
                # db-audit: ignore[DBW001] - literal collection
                count = self.conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                if count == 0:
                    # db-audit: ignore[DBW001] - literal collection
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
            logger.debug("Suppressed exception", exc_info=True)


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

    # ---------------- Students (read-only) ----------------
    # The canonical ``students`` table is owned by Student Records.
    # Apprenticeships reads it; creating, renaming or deleting a
    # person from here used to also wipe their applications.
    _STUDENT_COLS = ["student_id", "first_name", "last_name", "email_address",
                     "course", "year_of_study"]

    def list_students(self, search: str = "") -> list[dict]:
        if search:
            q = f"%{search}%"
            rows = self.db.fetch_all(
                """SELECT student_id, first_name, last_name, email_address,
                          course, year_of_study
                   FROM students
                   WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                      OR email_address LIKE ? OR course LIKE ?
                   ORDER BY last_name""", (q, q, q, q, q))
        else:
            rows = self.db.fetch_all(
                """SELECT student_id, first_name, last_name, email_address,
                          course, year_of_study
                   FROM students ORDER BY last_name""")
        return [dict(zip(self._STUDENT_COLS, r)) for r in rows]

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
                           status="Pending", notes="", employer_id=None) -> int:
        """Record an application.

        ``apprenticeship_id`` is the apprenticeships system's ``programme_id``
        and ``employer_id`` its ``employer_id`` — both read through the
        read-only gateway, so this table references them rather than holding
        a second copy of the programme and employer.
        """
        cur = self.db.execute(
            """INSERT INTO applications
                   (student_id, apprenticeship_id, status, notes, employer_id)
               VALUES (?, ?, ?, ?, ?)""",
            (student_id, apprenticeship_id, status, notes, employer_id))
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

    # ---------------- Import from the apprenticeships system ----------------
    # Employers and programmes are owned by the apprenticeships system and
    # read through the read-only ``ApprenticeshipsGateway``. The listings
    # screens here work on local ``employers`` / ``apprenticeships`` rows, so
    # an import copies the employer records across (matched by name, kept up
    # to date on re-import). The apprenticeships system has no vacancies, so
    # vacancies come from a CSV (:meth:`import_vacancies_csv`). Apprentices
    # are not copied: they are that system's learners, linked to university
    # students through the shared journey, and ``students`` belongs to
    # Student Records.

    def _employer_by_name(self, name):
        row = self.db.fetch_one(
            "SELECT employer_id FROM employers WHERE LOWER(TRIM(company_name)) = ? "
            "ORDER BY employer_id LIMIT 1", ((name or "").strip().lower(),))
        return row[0] if row else None

    def upsert_gateway_employer(self, emp) -> tuple[int, bool]:
        """Local employer row for an apprenticeships-system employer
        (an ``EmployerSummary``). Returns ``(employer_id, created)``."""
        name = (emp.name or "").strip()
        if not name:
            raise ValueError("The employer has no name")
        address = emp.postcode or ""
        existing = self._employer_by_name(name)
        if existing is None:
            return self.add_employer(name, emp.contact_name or "", emp.contact_email or "",
                                     industry=emp.sector or "", address=address), True
        # The apprenticeships system owns the record: refresh what it holds,
        # keep local values it has nothing for.
        self.db.execute(
            """UPDATE employers SET
                   contact_person = COALESCE(NULLIF(?, ''), contact_person),
                   contact_email = COALESCE(NULLIF(?, ''), contact_email),
                   industry = COALESCE(NULLIF(?, ''), industry),
                   address = COALESCE(NULLIF(address, ''), NULLIF(?, ''))
               WHERE employer_id = ?""",
            (emp.contact_name or "", emp.contact_email or "", emp.sector or "", address,
             existing))
        return existing, False

    def import_from_gateway(self, gateway) -> dict:
        """Copy the apprenticeships system's employers into the local
        employer list. Raises ``ApprenticeshipsGatewayError`` when that
        system's data cannot be read."""
        employers = gateway.list_employers()
        created = updated = 0
        skipped = []
        for emp in employers:
            if (emp.status or "Active").strip().lower() == "ended":
                skipped.append(f"{emp.name} ({emp.status})")
                continue
            _, new = self.upsert_gateway_employer(emp)
            created += 1 if new else 0
            updated += 0 if new else 1
        return {"employers_read": len(employers), "employers_created": created,
                "employers_updated": updated, "employers_skipped": skipped,
                "programmes": gateway.list_programmes(open_only=True)}

    def listing_for_programme(self, programme, employer) -> int:
        """The local listing an application to ``programme`` at ``employer``
        (gateway summaries) is recorded against, created if it is not there
        yet — so ``applications.apprenticeship_id`` always points at a real
        ``apprenticeships`` row."""
        employer_id, _ = self.upsert_gateway_employer(employer)
        title = programme.title
        if programme.reference:
            title = f"{programme.title} ({programme.reference})"
        row = self.db.fetch_one(
            "SELECT id FROM apprenticeships WHERE employer_id = ? AND title = ? "
            "ORDER BY id DESC LIMIT 1", (employer_id, title))
        if row:
            return row[0]
        return self.add_apprenticeship(
            title, employer_id, int(programme.duration_months or 12),
            description=f"Level {programme.level} apprenticeship standard"
            if programme.level else "", required_course="", status="Open")

    VACANCY_COLUMNS = ("title", "employer", "duration_months", "salary", "location",
                       "required_course", "min_year", "positions_available", "status",
                       "description", "programme_reference")
    VACANCY_STATUSES = ("Open", "Closed", "Filled", "Draft")

    def import_vacancies_csv(self, path, programmes=()) -> dict:
        """Validate a vacancies CSV and, only if every row is valid, add the
        listings in one transaction.

        Required columns: ``title`` (or ``programme_reference``), ``employer``
        (an employer already in the list) and ``duration_months`` (or a
        ``programme_reference`` that gives it). ``programmes`` are the
        apprenticeships system's programmes, used to check and fill
        ``programme_reference``. Returns ``{"added", "skipped", "errors"}``;
        nothing is written when ``errors`` is not empty.
        """
        import csv

        by_ref = {(p.reference or "").strip().lower(): p for p in programmes if p.reference}
        errors, rows = [], []
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = [h.strip().lower() for h in (reader.fieldnames or [])]
            if not header:
                return {"added": 0, "skipped": [], "errors": ["The file is empty."]}
            unknown = [h for h in header if h not in self.VACANCY_COLUMNS]
            if unknown:
                errors.append(f"Unknown column(s): {', '.join(unknown)}. Allowed: "
                              f"{', '.join(self.VACANCY_COLUMNS)}")
            if "employer" not in header:
                errors.append("The 'employer' column is required.")
            if "title" not in header and "programme_reference" not in header:
                errors.append("A 'title' or 'programme_reference' column is required.")
            if errors:
                return {"added": 0, "skipped": [], "errors": errors}
            for line, raw in enumerate(reader, start=2):
                rec = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
                if not any(rec.values()):
                    continue
                problems, out = [], {}
                ref = rec.get("programme_reference", "")
                prog = by_ref.get(ref.lower()) if ref else None
                if ref and prog is None:
                    problems.append(f"programme reference '{ref}' is not an open programme "
                                    "in the apprenticeships system")
                out["title"] = rec.get("title") or (prog.title if prog else "")
                if not out["title"]:
                    problems.append("title is missing")
                emp = rec.get("employer", "")
                out["employer_id"] = self._employer_by_name(emp) if emp else None
                if not emp:
                    problems.append("employer is missing")
                elif out["employer_id"] is None:
                    problems.append(f"employer '{emp}' is not in the employer list "
                                    "(import employers first, or add it)")
                out["duration_months"] = self._csv_int(
                    rec.get("duration_months") or (prog.duration_months if prog else ""),
                    "duration_months", problems, minimum=1, required=True)
                salary = rec.get("salary", "").replace("£", "").replace(",", "")
                out["salary"] = None
                if salary:
                    try:
                        out["salary"] = float(salary)
                        if out["salary"] < 0:
                            problems.append("salary cannot be negative")
                    except ValueError:
                        problems.append(f"salary '{rec.get('salary')}' is not a number")
                out["min_year"] = self._csv_int(rec.get("min_year") or "1", "min_year",
                                                problems, minimum=1)
                out["positions_available"] = self._csv_int(
                    rec.get("positions_available") or "1", "positions_available", problems,
                    minimum=1)
                status = (rec.get("status") or "Open").title()
                if status not in self.VACANCY_STATUSES:
                    problems.append(f"status '{rec.get('status')}' must be one of "
                                    f"{', '.join(self.VACANCY_STATUSES)}")
                out["status"] = status
                out["location"] = rec.get("location", "")
                out["required_course"] = rec.get("required_course", "")
                out["description"] = rec.get("description", "") or (
                    f"Level {prog.level} apprenticeship standard" if prog and prog.level else "")
                if problems:
                    errors.append(f"Row {line}: " + "; ".join(problems))
                else:
                    rows.append((line, out))
        if errors:
            return {"added": 0, "skipped": [], "errors": errors}
        added, skipped = 0, []
        conn = self.db.conn
        try:
            for line, r in rows:
                dup = conn.execute(
                    "SELECT 1 FROM apprenticeships WHERE employer_id = ? AND LOWER(title) = ? "
                    "AND status = ?", (r["employer_id"], r["title"].lower(), r["status"])
                ).fetchone()
                if dup:
                    skipped.append(f"Row {line}: '{r['title']}' is already listed")
                    continue
                conn.execute(
                    """INSERT INTO apprenticeships
                           (title, employer_id, description, duration_months, salary,
                            location, required_course, min_year, positions_available, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (r["title"], r["employer_id"], r["description"], r["duration_months"],
                     r["salary"], r["location"], r["required_course"], r["min_year"],
                     r["positions_available"], r["status"]))
                added += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {"added": added, "skipped": skipped, "errors": []}

    @staticmethod
    def _csv_int(value, label, problems, minimum=None, required=False):
        value = str(value if value is not None else "").strip()
        if not value:
            if required:
                problems.append(f"{label} is missing")
            return None
        try:
            number = int(value)
        except ValueError:
            problems.append(f"{label} '{value}' is not a whole number")
            return None
        if minimum is not None and number < minimum:
            problems.append(f"{label} must be at least {minimum}")
        return number

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
        from education_system.systems.university.domains.admissions.domain.prior_learning_recognition.services.prior_learning_service import (
            PriorLearningService,
        )
        return PriorLearningService().create_evidence_from_placement(
            student_id,
            employer=employer,
            total_hours=0.0,
            signed_off_hours=0.0,
            target_course=course,
        )
