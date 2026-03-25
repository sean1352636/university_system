"""Bulk student transfer service.

Provides methods to identify students eligible for transfer between education
systems (primary -> secondary -> college -> university) and to execute batch
transfers using the existing academic history extraction functions.
"""

import sqlite3
import datetime
from pathlib import Path

from education_system.shared.transfer.academic_history import (
    extract_primary_history,
    extract_secondary_history,
    extract_college_history,
)


# ---------------------------------------------------------------------------
# Path helpers (mirrors journey_service pattern)
# ---------------------------------------------------------------------------

def _default_db_path(system):
    """Resolve the default database path for a given system."""
    shared_dir = Path(__file__).resolve().parent.parent  # .../shared
    edu_root = shared_dir.parent  # .../education_system
    path_map = {
        "primary": edu_root / "primary_school" / "data" / "db_files" / "primary_school.db",
        "secondary": edu_root / "secondary_school" / "data" / "db_files" / "secondary_school.db",
        "college": edu_root / "college_system" / "data" / "db_files" / "sixthform.db",
        "university": edu_root / "university_system" / "data" / "db_files" / "student_records.db",
    }
    return path_map.get(system)


def _table_exists(conn, table_name):
    """Check whether *table_name* exists in the SQLite database."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    """Return the set of column names for *table_name*."""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


def _name_expr(columns):
    """Build a SQL expression that yields a full name from available columns."""
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
    return None


# Natural progression map: source_system -> destination_system
DESTINATION_MAP = {
    "primary": "secondary",
    "secondary": "college",
    "college": "university",
}

# Year groups that are eligible for transfer out of each system
ELIGIBLE_YEARS = {
    "primary": {"Year 6", "6", "Y6"},
    "secondary": {"Year 11", "11", "Y11"},
    "college": {"Year 13", "13", "Y13"},
}


class BulkTransferService:
    """Manage batch student transfers between education systems."""

    def __init__(self, primary_db=None, secondary_db=None, college_db=None, university_db=None):
        self._db_paths = {
            "primary": Path(primary_db) if primary_db else _default_db_path("primary"),
            "secondary": Path(secondary_db) if secondary_db else _default_db_path("secondary"),
            "college": Path(college_db) if college_db else _default_db_path("college"),
            "university": Path(university_db) if university_db else _default_db_path("university"),
        }
        self._last_results = None

    def _connect(self, system):
        """Open a connection to a system DB.  Returns None if DB missing."""
        path = self._db_paths.get(system)
        if not path or not path.exists():
            return None
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_eligible_students(self, source_system):
        """Return a list of students eligible for transfer from *source_system*.

        Each entry is a dict with: id, student_id, name, year_group, status.
        Eligibility is based on year_group matching the final year for that
        system and having an active status (not already transferred).
        """
        if source_system not in ELIGIBLE_YEARS:
            return []

        conn = self._connect(source_system)
        if not conn:
            return []

        table = "pupils" if source_system == "primary" else "students"
        results = []

        try:
            if not _table_exists(conn, table):
                return results

            cols = _get_columns(conn, table)
            name_sql = _name_expr(cols)
            if not name_sql:
                return results

            id_col = "pupil_id" if (source_system == "primary" and "pupil_id" in cols) else (
                "student_id" if "student_id" in cols else "id"
            )
            has_year = "year_group" in cols
            has_status = "status" in cols

            select_cols = f"id, {id_col}, {name_sql} AS full_name"
            if has_year:
                select_cols += ", year_group"
            if has_status:
                select_cols += ", status"

            # Build WHERE clause
            conditions = []
            params = []

            if has_year:
                eligible = ELIGIBLE_YEARS[source_system]
                placeholders = ", ".join("?" for _ in eligible)
                conditions.append(f"year_group IN ({placeholders})")
                params.extend(eligible)

            if has_status:
                # Exclude already transferred students
                conditions.append("LOWER(status) NOT IN ('transferred', 'inactive', 'withdrawn')")

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            rows = conn.execute(
                f"SELECT {select_cols} FROM {table} {where} ORDER BY full_name",
                params,
            ).fetchall()

            for r in rows:
                rk = r.keys()
                results.append({
                    "id": r["id"],
                    "student_id": r[id_col] if id_col in rk else str(r["id"]),
                    "name": r["full_name"],
                    "year_group": r["year_group"] if has_year and "year_group" in rk else "",
                    "status": r["status"] if has_status and "status" in rk else "active",
                })
        except Exception:
            pass
        finally:
            conn.close()

        return results

    def get_destination_system(self, source_system):
        """Return the natural destination system name for a given source."""
        return DESTINATION_MAP.get(source_system)

    def transfer_batch(self, source_system, dest_system, student_ids):
        """Transfer a batch of students from source to destination system.

        For each student:
        1. Extract academic history using shared.transfer.academic_history
        2. Insert a record into academic_transfer_history in the destination DB
        3. Mark student as 'Transferred' in the source DB (soft delete)

        Args:
            source_system: 'primary', 'secondary', or 'college'
            dest_system: 'secondary', 'college', or 'university'
            student_ids: list of student/pupil IDs (the text IDs, not row ids)

        Returns:
            dict with keys: transferred, failed, details (list of per-student results)
        """
        summary = {
            "transferred": 0,
            "failed": 0,
            "details": [],
            "source_system": source_system,
            "dest_system": dest_system,
            "timestamp": datetime.datetime.now().isoformat(),
        }

        source_conn = self._connect(source_system)
        dest_conn = self._connect(dest_system)

        if not source_conn:
            summary["details"].append({"error": f"Cannot connect to {source_system} database"})
            summary["failed"] = len(student_ids)
            self._last_results = summary
            return summary
        if not dest_conn:
            source_conn.close()
            summary["details"].append({"error": f"Cannot connect to {dest_system} database"})
            summary["failed"] = len(student_ids)
            self._last_results = summary
            return summary

        source_db_path = self._db_paths[source_system]

        try:
            # Ensure destination has academic_transfer_history table
            self._ensure_transfer_table(dest_conn)

            for sid in student_ids:
                detail = {"student_id": sid, "success": False}
                try:
                    # 1. Get student info and row id from source
                    student_info = self._get_student_info(source_conn, source_system, sid)
                    if not student_info:
                        detail["error"] = "Student not found in source"
                        summary["failed"] += 1
                        summary["details"].append(detail)
                        continue

                    detail["name"] = student_info.get("name", "")

                    # 2. Extract academic history
                    history = self._extract_history(source_system, source_db_path, student_info)

                    # 3. Insert transfer record in destination
                    self._insert_transfer_record(dest_conn, source_system, sid, detail["name"], history)

                    # 4. Mark as transferred in source
                    self._mark_transferred(source_conn, source_system, student_info)

                    detail["success"] = True
                    summary["transferred"] += 1

                except Exception as exc:
                    detail["error"] = str(exc)
                    summary["failed"] += 1

                summary["details"].append(detail)

            source_conn.commit()
            dest_conn.commit()

        except Exception as exc:
            summary["details"].append({"error": f"Batch error: {exc}"})
        finally:
            source_conn.close()
            dest_conn.close()

        self._last_results = summary
        return summary

    def get_last_results(self):
        """Return the summary from the most recent transfer_batch call."""
        return self._last_results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_student_info(self, conn, system, student_id):
        """Look up a student by their text ID and return basic info dict."""
        table = "pupils" if system == "primary" else "students"
        try:
            if not _table_exists(conn, table):
                return None
            cols = _get_columns(conn, table)
            name_sql = _name_expr(cols)
            id_col = "pupil_id" if (system == "primary" and "pupil_id" in cols) else (
                "student_id" if "student_id" in cols else "id"
            )

            row = conn.execute(
                f"SELECT id, {id_col}, {name_sql} AS full_name FROM {table} WHERE {id_col} = ?",
                (student_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "row_id": row["id"],
                "student_id": row[id_col] if id_col in row.keys() else str(row["id"]),
                "name": row["full_name"],
            }
        except Exception:
            return None

    def _extract_history(self, source_system, db_path, student_info):
        """Call the appropriate extract function from academic_history."""
        try:
            if source_system == "primary":
                return extract_primary_history(db_path, student_info["student_id"])
            elif source_system == "secondary":
                return extract_secondary_history(db_path, student_info["row_id"])
            elif source_system == "college":
                return extract_college_history(db_path, student_info["row_id"])
        except Exception:
            pass
        return {"source_system": source_system, "source_student_id": student_info["student_id"]}

    def _ensure_transfer_table(self, conn):
        """Create academic_transfer_history table if it does not exist.

        Uses the same schema as the per-system schemas (college, secondary,
        university) which store all history data as JSON in ``data_json``.
        """
        conn.execute("""
            CREATE TABLE IF NOT EXISTS academic_transfer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_system TEXT NOT NULL,
                source_student_id TEXT NOT NULL,
                transfer_date TEXT NOT NULL DEFAULT (datetime('now')),
                data_json TEXT NOT NULL
            )
        """)
        # Migration: add data_json column if table was created with old schema
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(academic_transfer_history)").fetchall()}
        if "data_json" not in cols:
            conn.execute(
                "ALTER TABLE academic_transfer_history ADD COLUMN data_json TEXT NOT NULL DEFAULT '{}'"
            )
        conn.commit()

    def _insert_transfer_record(self, dest_conn, source_system, student_id, name, history):
        """Insert an academic_transfer_history record in the destination DB."""
        import json
        # Package everything into data_json to match the per-system schema
        data = dict(history) if history else {}
        data["student_name"] = name
        dest_conn.execute(
            """INSERT INTO academic_transfer_history
               (source_system, source_student_id, transfer_date, data_json)
               VALUES (?, ?, ?, ?)""",
            (
                source_system,
                student_id,
                datetime.datetime.now().isoformat(),
                json.dumps(data),
            ),
        )

    def _mark_transferred(self, conn, system, student_info):
        """Set student status to 'Transferred' in the source DB."""
        table = "pupils" if system == "primary" else "students"
        try:
            cols = _get_columns(conn, table)
            if "status" in cols:
                conn.execute(
                    f"UPDATE {table} SET status = 'Transferred' WHERE id = ?",
                    (student_info["row_id"],),
                )
        except Exception:
            pass
