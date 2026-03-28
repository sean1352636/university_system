"""Student Self-Service Portal service layer.

Provides methods for students to view their own journey, retrieve their
records from any system, and submit / track record requests.  Admin
helpers allow staff to view and resolve pending requests.

The ``student_record_requests`` table is stored in the shared auth DB.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from education_system.shared.database.paths import (
    SYSTEM_DB_PATHS as _DB_PATHS,
    AUTH_DB as _AUTH_DB,
)

REQUEST_TYPES = ("transcript", "data_export", "correction", "other")


# ---------------------------------------------------------------------------
# Table initialisation (run once on import)
# ---------------------------------------------------------------------------

def _init_requests_table():
    """Create the student_record_requests table if it does not exist."""
    _AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_AUTH_DB), timeout=30)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_record_requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT NOT NULL,
                request_type TEXT NOT NULL,
                details     TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


_init_requests_table()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_conn():
    """Return a connection to the shared auth DB."""
    conn = sqlite3.connect(str(_AUTH_DB), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _sys_conn(system):
    """Return a connection to a system DB, or None if the file is missing."""
    path = _DB_PATHS.get(system)
    if not path or not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


def _name_search_expr(columns):
    """Build a SQL expression that yields the full name."""
    if "full_name" in columns:
        return "full_name"
    if "name" in columns:
        return "name"
    if "first_name" in columns and "last_name" in columns:
        return "(first_name || ' ' || last_name)"
    if "forename" in columns and "surname" in columns:
        return "(forename || ' ' || surname)"
    if "first_name" in columns and "surname" in columns:
        return "(first_name || ' ' || surname)"
    if "forename" in columns and "last_name" in columns:
        return "(forename || ' ' || last_name)"
    return None


# ---------------------------------------------------------------------------
# Resolve username -> full_name from auth DB
# ---------------------------------------------------------------------------

def _resolve_student_name(username):
    """Look up the user's full_name (or display_name / first+last) from auth."""
    conn = _auth_conn()
    try:
        if not _table_exists(conn, "users"):
            return None
        cols = _get_columns(conn, "users")
        name_expr = _name_search_expr(cols)
        if not name_expr:
            # Try display_name or username fallback
            if "display_name" in cols:
                name_expr = "display_name"
            else:
                return username  # last resort

        row = conn.execute(
            f"SELECT {name_expr} AS resolved_name FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row and row["resolved_name"]:
            return row["resolved_name"]
        return username
    except Exception:
        return username
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class PortalService:
    """Student self-service portal business logic."""

    # ---- Journey (reuses JourneyService pattern but filtered to one user) --

    def get_my_journey(self, username):
        """Return journey stages for the student identified by *username*.

        Resolves the username to a full name via the auth DB, then searches
        each system DB for matching student records.
        """
        student_name = _resolve_student_name(username)
        if not student_name:
            return []

        stages = []
        for sys_key in ("primary", "secondary", "college", "university"):
            stage = self._find_in_system(sys_key, student_name)
            if stage:
                stages.append(stage)
        return stages

    # ---- Records -----------------------------------------------------------

    def get_my_records(self, username, system):
        """Return grades, attendance, and transfer history for *username* in *system*."""
        student_name = _resolve_student_name(username)
        if not student_name:
            return {"grades": [], "attendance": {}, "transfers": []}

        conn = _sys_conn(system)
        if not conn:
            return {"grades": [], "attendance": {}, "transfers": []}

        try:
            result = {"grades": [], "attendance": {}, "transfers": []}

            if system == "primary":
                result = self._records_primary(conn, student_name)
            elif system == "secondary":
                result = self._records_secondary(conn, student_name)
            elif system == "college":
                result = self._records_college(conn, student_name)
            elif system == "university":
                result = self._records_university(conn, student_name)

            # Transfer history
            if _table_exists(conn, "academic_transfer_history"):
                try:
                    rows = conn.execute(
                        "SELECT * FROM academic_transfer_history ORDER BY rowid"
                    ).fetchall()
                    result["transfers"] = [dict(r) for r in rows]
                except Exception:
                    pass

            return result
        finally:
            conn.close()

    # ---- Record requests ---------------------------------------------------

    def submit_record_request(self, username, request_type, details):
        """Create a new record request.  Returns the new row id."""
        if request_type not in REQUEST_TYPES:
            raise ValueError(f"Invalid request_type: {request_type}")
        conn = _auth_conn()
        try:
            cur = conn.execute(
                "INSERT INTO student_record_requests "
                "(username, request_type, details, status, created_at) "
                "VALUES (?, ?, ?, 'pending', ?)",
                (username, request_type, details, datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_my_requests(self, username):
        """Return all requests submitted by *username*."""
        conn = _auth_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM student_record_requests WHERE username = ? ORDER BY created_at DESC",
                (username,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_pending_requests(self):
        """Return all pending requests (admin view)."""
        conn = _auth_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM student_record_requests WHERE status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def resolve_request(self, request_id, resolved_by, status="resolved"):
        """Mark a request as resolved (or rejected)."""
        conn = _auth_conn()
        try:
            conn.execute(
                "UPDATE student_record_requests SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
                (status, datetime.now().isoformat(timespec="seconds"), resolved_by, request_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ---- Internal helpers --------------------------------------------------

    def _find_in_system(self, system, student_name):
        """Search a single system DB for a student by name; return a stage dict."""
        conn = _sys_conn(system)
        if not conn:
            return None
        try:
            table = "pupils" if system == "primary" else "students"
            if not _table_exists(conn, table):
                return None
            cols = _get_columns(conn, table)
            name_expr = _name_search_expr(cols)
            if not name_expr:
                return None
            id_col = "pupil_id" if (system == "primary" and "pupil_id" in cols) else (
                "student_id" if "student_id" in cols else "id"
            )
            status_col = "status" if "status" in cols else None
            year_col = "year_group" if "year_group" in cols else ("year" if "year" in cols else None)

            row = conn.execute(
                f"SELECT *, {name_expr} AS full_name FROM {table} WHERE {name_expr} LIKE ? LIMIT 1",
                (f"%{student_name}%",),
            ).fetchone()
            if not row:
                return None

            rk = row.keys()
            enrolled_date = ""
            for col in ("admission_date", "enrollment_date", "enrolled_date"):
                if col in rk and row[col]:
                    enrolled_date = row[col]
                    break

            return {
                "system": system,
                "student_id": row[id_col] if id_col in rk else "",
                "name": row["full_name"],
                "year_group": row[year_col] if year_col and year_col in rk else "",
                "status": row["status"] if status_col and "status" in rk else "unknown",
                "enrolled_date": enrolled_date,
            }
        except Exception:
            return None
        finally:
            conn.close()

    # -- per-system records --------------------------------------------------

    def _records_primary(self, conn, student_name):
        grades, attendance = [], {}
        # Find pupil id
        pid = self._find_id(conn, "pupils", student_name, "pupil_id")
        if not pid:
            return {"grades": grades, "attendance": attendance, "transfers": []}

        if _table_exists(conn, "assessments"):
            try:
                rows = conn.execute(
                    "SELECT * FROM assessments WHERE pupil_id = ? ORDER BY academic_year, term",
                    (pid,),
                ).fetchall()
                grades = [dict(r) for r in rows]
            except Exception:
                pass

        if _table_exists(conn, "sats_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM sats_results WHERE pupil_id = ? ORDER BY academic_year",
                    (pid,),
                ).fetchall()
                grades.extend([dict(r) for r in rows])
            except Exception:
                pass

        if _table_exists(conn, "phonics_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM phonics_results WHERE pupil_id = ? ORDER BY academic_year",
                    (pid,),
                ).fetchall()
                grades.extend([dict(r) for r in rows])
            except Exception:
                pass

        attendance = self._attendance_primary(conn, pid)
        return {"grades": grades, "attendance": attendance, "transfers": []}

    def _records_secondary(self, conn, student_name):
        grades, attendance = [], {}
        sid = self._find_id(conn, "students", student_name, "id")
        if not sid:
            return {"grades": grades, "attendance": attendance, "transfers": []}

        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY academic_year, term",
                    (sid,),
                ).fetchall()
                grades = [dict(r) for r in rows]
            except Exception:
                pass

        if _table_exists(conn, "exam_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM exam_results WHERE student_id = ? ORDER BY rowid",
                    (sid,),
                ).fetchall()
                grades.extend([dict(r) for r in rows])
            except Exception:
                pass

        attendance = self._attendance_secondary(conn, sid)
        return {"grades": grades, "attendance": attendance, "transfers": []}

    def _records_college(self, conn, student_name):
        grades, attendance = [], {}
        sid = self._find_id(conn, "students", student_name, "id")
        if not sid:
            return {"grades": grades, "attendance": attendance, "transfers": []}

        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY semester, term",
                    (sid,),
                ).fetchall()
                grades = [dict(r) for r in rows]
            except Exception:
                pass

        attendance = self._attendance_college(conn, sid)
        return {"grades": grades, "attendance": attendance, "transfers": []}

    def _records_university(self, conn, student_name):
        grades, attendance = [], {}
        sid = self._find_id(conn, "students", student_name, "id")
        if not sid:
            return {"grades": grades, "attendance": attendance, "transfers": []}

        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY rowid",
                    (sid,),
                ).fetchall()
                grades = [dict(r) for r in rows]
            except Exception:
                pass

        # university uses "attendance", others use "attendance_records"
        att_table = None
        for _tbl in ("attendance", "attendance_records"):
            if _table_exists(conn, _tbl):
                att_table = _tbl
                break
        if att_table:
            try:
                total = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {att_table} WHERE student_id = ?", (sid,)
                ).fetchone()["c"]
                present = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {att_table} WHERE student_id = ? AND status IN ('present','late')",
                    (sid,),
                ).fetchone()["c"]
                attendance = {
                    "total_sessions": total,
                    "present": present,
                    "percentage": round(present / total * 100, 1) if total > 0 else 0,
                }
            except Exception:
                pass

        return {"grades": grades, "attendance": attendance, "transfers": []}

    # -- attendance helpers --------------------------------------------------

    @staticmethod
    def _attendance_primary(conn, pupil_id):
        if not _table_exists(conn, "attendance_records"):
            return {}
        try:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM attendance_records WHERE pupil_id = ?", (pupil_id,)
            ).fetchone()["c"]
            present = conn.execute(
                "SELECT COUNT(*) AS c FROM attendance_records WHERE pupil_id = ? AND status IN ('Present','Late')",
                (pupil_id,),
            ).fetchone()["c"]
            return {
                "total_sessions": total,
                "present": present,
                "percentage": round(present / total * 100, 1) if total > 0 else 0,
            }
        except Exception:
            return {}

    @staticmethod
    def _attendance_secondary(conn, student_id):
        if not _table_exists(conn, "attendance_records"):
            return {}
        try:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM attendance_records WHERE student_id = ?", (student_id,)
            ).fetchone()["c"]
            present = conn.execute(
                "SELECT COUNT(*) AS c FROM attendance_records WHERE student_id = ? AND status IN ('present','late')",
                (student_id,),
            ).fetchone()["c"]
            return {
                "total_sessions": total,
                "present": present,
                "percentage": round(present / total * 100, 1) if total > 0 else 0,
            }
        except Exception:
            return {}

    @staticmethod
    def _attendance_college(conn, student_id):
        if not _table_exists(conn, "attendance_records"):
            return {}
        try:
            join_clause = ""
            if _table_exists(conn, "attendance_sessions"):
                join_clause = "JOIN attendance_sessions s ON ar.session_id = s.id"
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM attendance_records ar {join_clause} WHERE ar.student_id = ?",
                (student_id,),
            ).fetchone()["c"]
            present = conn.execute(
                f"SELECT COUNT(*) AS c FROM attendance_records ar {join_clause} "
                f"WHERE ar.student_id = ? AND ar.status IN ('present','late')",
                (student_id,),
            ).fetchone()["c"]
            return {
                "total_sessions": total,
                "present": present,
                "percentage": round(present / total * 100, 1) if total > 0 else 0,
            }
        except Exception:
            return {}

    # -- generic id finder ---------------------------------------------------

    @staticmethod
    def _find_id(conn, table, student_name, id_col):
        """Find the id for a student by name in *table*."""
        cols = _get_columns(conn, table)
        name_expr = _name_search_expr(cols)
        if not name_expr:
            return None
        try:
            row = conn.execute(
                f"SELECT {id_col} FROM {table} WHERE {name_expr} LIKE ? LIMIT 1",
                (f"%{student_name}%",),
            ).fetchone()
            return row[0] if row else None
        except Exception:
            return None
