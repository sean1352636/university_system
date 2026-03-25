"""Cross-system student journey service.

Queries all 4 education system databases (primary, secondary, college,
university) to build a unified view of a student's educational journey.
"""

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_db_path(system):
    """Resolve the default database path for a given system.

    Tries importing the canonical paths module for each system first, then
    falls back to a conventional relative path from the shared directory.
    """
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


class JourneyService:
    """Queries all 4 system databases to build a student's educational journey."""

    def __init__(self, primary_db=None, secondary_db=None, college_db=None, university_db=None):
        self._db_paths = {
            "primary": Path(primary_db) if primary_db else _default_db_path("primary"),
            "secondary": Path(secondary_db) if secondary_db else _default_db_path("secondary"),
            "college": Path(college_db) if college_db else _default_db_path("college"),
            "university": Path(university_db) if university_db else _default_db_path("university"),
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _connect(self, system):
        """Open a read-only connection to a system DB. Returns None if DB missing."""
        path = self._db_paths.get(system)
        if not path or not path.exists():
            return None
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def search_student(self, name_query):
        """Search for a student across all 4 systems by name.

        Returns a list of dicts, each with keys:
            system, id, student_id, name, status
        """
        results = []
        if not name_query or not name_query.strip():
            return results

        query = f"%{name_query.strip()}%"

        # --- Primary ---
        results.extend(self._search_primary(query))
        # --- Secondary ---
        results.extend(self._search_secondary(query))
        # --- College ---
        results.extend(self._search_college(query))
        # --- University ---
        results.extend(self._search_university(query))

        return results

    def get_journey(self, student_name=None, student_id=None, system=None):
        """Get the full educational journey for a student.

        If *system* and *student_id* are provided the lookup starts in that
        system and follows ``previous_system_id`` links where available.

        If *student_name* is provided every system is queried by name match
        and the results are combined into chronological order.

        Returns a list of journey stage dicts ordered primary -> university,
        each containing:
            system, student_id, name, dob, year_group, status,
            academic_history, enrolled_date
        """
        stages = []

        if system and student_id:
            # Start from the specified system
            stage = self._query_system(system, student_id=student_id)
            if stage:
                stages.append(stage)
                # Try to follow links in both directions
                stages = self._follow_links(stage, stages)
        elif student_name:
            # Search all systems by name
            for sys_key in ("primary", "secondary", "college", "university"):
                found = self._query_system(sys_key, name=student_name)
                if found:
                    stages.append(found)

        # Deduplicate and order: primary -> secondary -> college -> university
        order = {"primary": 0, "secondary": 1, "college": 2, "university": 3}
        seen = set()
        ordered = []
        for s in sorted(stages, key=lambda s: order.get(s["system"], 99)):
            key = (s["system"], s.get("student_id") or s.get("id"))
            if key not in seen:
                seen.add(key)
                ordered.append(s)

        return ordered

    # ------------------------------------------------------------------
    # Per-system search helpers
    # ------------------------------------------------------------------

    def _search_primary(self, like_pattern):
        results = []
        conn = self._connect("primary")
        if not conn:
            return results
        try:
            if not _table_exists(conn, "pupils"):
                return results
            cols = _get_columns(conn, "pupils")
            name_expr = self._name_search_expr(cols, "pupils")
            if not name_expr:
                return results

            id_col = "pupil_id" if "pupil_id" in cols else "id"
            status_col = "status" if "status" in cols else None
            year_col = "year_group" if "year_group" in cols else None

            select_cols = f"{id_col}, {name_expr} AS full_name"
            if status_col:
                select_cols += f", {status_col}"
            if year_col:
                select_cols += f", {year_col}"

            rows = conn.execute(
                f"SELECT {select_cols} FROM pupils WHERE {name_expr} LIKE ? LIMIT 50",
                (like_pattern,),
            ).fetchall()
            for r in rows:
                results.append({
                    "system": "primary",
                    "id": r[id_col] if id_col in r.keys() else r[0],
                    "student_id": r[id_col] if id_col in r.keys() else r[0],
                    "name": r["full_name"],
                    "status": r["status"] if status_col and "status" in r.keys() else "unknown",
                    "year_group": r["year_group"] if year_col and "year_group" in r.keys() else "",
                })
        except Exception as e:
            logger.warning("Error searching primary students: %s", e)
        finally:
            conn.close()
        return results

    def _search_secondary(self, like_pattern):
        results = []
        conn = self._connect("secondary")
        if not conn:
            return results
        try:
            if not _table_exists(conn, "students"):
                return results
            cols = _get_columns(conn, "students")
            name_expr = self._name_search_expr(cols, "students")
            if not name_expr:
                return results

            id_col = "student_id" if "student_id" in cols else "id"
            status_col = "status" if "status" in cols else None
            year_col = "year_group" if "year_group" in cols else None

            select_cols = f"id, {id_col}, {name_expr} AS full_name"
            if status_col:
                select_cols += f", {status_col}"
            if year_col:
                select_cols += f", {year_col}"

            rows = conn.execute(
                f"SELECT {select_cols} FROM students WHERE {name_expr} LIKE ? LIMIT 50",
                (like_pattern,),
            ).fetchall()
            for r in rows:
                results.append({
                    "system": "secondary",
                    "id": r["id"],
                    "student_id": r[id_col] if id_col in r.keys() else str(r["id"]),
                    "name": r["full_name"],
                    "status": r["status"] if status_col and "status" in r.keys() else "unknown",
                    "year_group": r["year_group"] if year_col and "year_group" in r.keys() else "",
                })
        except Exception as e:
            logger.warning("Error searching secondary students: %s", e)
        finally:
            conn.close()
        return results

    def _search_college(self, like_pattern):
        results = []
        conn = self._connect("college")
        if not conn:
            return results
        try:
            if not _table_exists(conn, "students"):
                return results
            cols = _get_columns(conn, "students")
            name_expr = self._name_search_expr(cols, "students")
            if not name_expr:
                return results

            id_col = "student_id" if "student_id" in cols else "id"
            status_col = "status" if "status" in cols else None
            year_col = "year_group" if "year_group" in cols else None

            select_cols = f"id, {id_col}, {name_expr} AS full_name"
            if status_col:
                select_cols += f", {status_col}"
            if year_col:
                select_cols += f", {year_col}"

            rows = conn.execute(
                f"SELECT {select_cols} FROM students WHERE {name_expr} LIKE ? LIMIT 50",
                (like_pattern,),
            ).fetchall()
            for r in rows:
                results.append({
                    "system": "college",
                    "id": r["id"],
                    "student_id": r[id_col] if id_col in r.keys() else str(r["id"]),
                    "name": r["full_name"],
                    "status": r["status"] if status_col and "status" in r.keys() else "unknown",
                    "year_group": r["year_group"] if year_col and "year_group" in r.keys() else "",
                })
        except Exception as e:
            logger.warning("Error searching college students: %s", e)
        finally:
            conn.close()
        return results

    def _search_university(self, like_pattern):
        results = []
        conn = self._connect("university")
        if not conn:
            return results
        try:
            if not _table_exists(conn, "students"):
                return results
            cols = _get_columns(conn, "students")
            name_expr = self._name_search_expr(cols, "students")
            if not name_expr:
                return results

            id_col = "student_id" if "student_id" in cols else "id"
            status_col = "status" if "status" in cols else None
            year_col = "year_group" if "year_group" in cols else ("year" if "year" in cols else None)

            select_cols = f"{id_col}, {name_expr} AS full_name"
            if "id" in cols and id_col != "id":
                select_cols = f"id, {select_cols}"
            if status_col:
                select_cols += f", {status_col}"
            if year_col:
                select_cols += f", {year_col}"

            rows = conn.execute(
                f"SELECT {select_cols} FROM students WHERE {name_expr} LIKE ? LIMIT 50",
                (like_pattern,),
            ).fetchall()
            for r in rows:
                rk = r.keys()
                yr = ""
                if year_col and year_col in rk:
                    yr = r[year_col]
                row_id = r["id"] if "id" in rk else r[id_col]
                results.append({
                    "system": "university",
                    "id": row_id,
                    "student_id": r[id_col] if id_col in rk else str(row_id),
                    "name": r["full_name"],
                    "status": r["status"] if status_col and "status" in r.keys() else "unknown",
                    "year_group": yr,
                })
        except Exception as e:
            logger.warning("Error searching university students: %s", e)
        finally:
            conn.close()
        return results

    # ------------------------------------------------------------------
    # Per-system detailed query (for journey building)
    # ------------------------------------------------------------------

    def _query_system(self, system, name=None, student_id=None):
        """Query a single system DB and return a journey stage dict or None."""
        if system == "primary":
            return self._query_primary(name=name, student_id=student_id)
        elif system == "secondary":
            return self._query_secondary(name=name, student_id=student_id)
        elif system == "college":
            return self._query_college(name=name, student_id=student_id)
        elif system == "university":
            return self._query_university(name=name, student_id=student_id)
        return None

    def _query_primary(self, name=None, student_id=None):
        conn = self._connect("primary")
        if not conn:
            return None
        try:
            if not _table_exists(conn, "pupils"):
                return None
            cols = _get_columns(conn, "pupils")
            name_expr = self._name_search_expr(cols, "pupils")
            id_col = "pupil_id" if "pupil_id" in cols else "id"

            if student_id:
                row = conn.execute(
                    f"SELECT * FROM pupils WHERE {id_col} = ?", (student_id,)
                ).fetchone()
            elif name and name_expr:
                row = conn.execute(
                    f"SELECT * FROM pupils WHERE {name_expr} LIKE ? LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()
            else:
                return None

            if not row:
                return None

            rk = row.keys()
            stage = {
                "system": "primary",
                "student_id": row[id_col] if id_col in rk else str(row["id"]) if "id" in rk else "",
                "name": self._extract_name(row, cols),
                "dob": row["date_of_birth"] if "date_of_birth" in rk else row["dob"] if "dob" in rk else "",
                "year_group": row["year_group"] if "year_group" in rk else "",
                "status": row["status"] if "status" in rk else "unknown",
                "enrolled_date": row["admission_date"] if "admission_date" in rk else (
                    row["enrolled_date"] if "enrolled_date" in rk else ""
                ),
                "academic_history": [],
            }

            # Pull academic transfer history if table exists
            stage["academic_history"] = self._get_transfer_history(conn, "primary", stage["student_id"])

            return stage
        except Exception as e:
            logger.warning("Error querying primary student journey: %s", e)
            return None
        finally:
            conn.close()

    def _query_secondary(self, name=None, student_id=None):
        conn = self._connect("secondary")
        if not conn:
            return None
        try:
            if not _table_exists(conn, "students"):
                return None
            cols = _get_columns(conn, "students")
            name_expr = self._name_search_expr(cols, "students")
            id_col = "student_id" if "student_id" in cols else "id"

            if student_id:
                # Try text id first, then numeric
                row = conn.execute(
                    f"SELECT * FROM students WHERE {id_col} = ?", (student_id,)
                ).fetchone()
                if not row and id_col != "id" and "id" in cols:
                    row = conn.execute(
                        "SELECT * FROM students WHERE id = ?", (student_id,)
                    ).fetchone()
            elif name and name_expr:
                row = conn.execute(
                    f"SELECT * FROM students WHERE {name_expr} LIKE ? LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()
            else:
                return None

            if not row:
                return None

            rk = row.keys()
            stage = {
                "system": "secondary",
                "student_id": row[id_col] if id_col in rk else str(row["id"]) if "id" in rk else "",
                "name": self._extract_name(row, cols),
                "dob": row["date_of_birth"] if "date_of_birth" in rk else row["dob"] if "dob" in rk else "",
                "year_group": row["year_group"] if "year_group" in rk else "",
                "status": row["status"] if "status" in rk else "unknown",
                "enrolled_date": row["admission_date"] if "admission_date" in rk else (
                    row["enrolled_date"] if "enrolled_date" in rk else ""
                ),
                "previous_system_id": row["previous_system_id"] if "previous_system_id" in rk else "",
                "academic_history": [],
            }

            stage["academic_history"] = self._get_transfer_history(conn, "secondary", stage["student_id"])

            return stage
        except Exception as e:
            logger.warning("Error querying secondary student journey: %s", e)
            return None
        finally:
            conn.close()

    def _query_college(self, name=None, student_id=None):
        conn = self._connect("college")
        if not conn:
            return None
        try:
            if not _table_exists(conn, "students"):
                return None
            cols = _get_columns(conn, "students")
            name_expr = self._name_search_expr(cols, "students")
            id_col = "student_id" if "student_id" in cols else "id"

            if student_id:
                row = conn.execute(
                    f"SELECT * FROM students WHERE {id_col} = ?", (student_id,)
                ).fetchone()
                if not row and id_col != "id" and "id" in cols:
                    row = conn.execute(
                        "SELECT * FROM students WHERE id = ?", (student_id,)
                    ).fetchone()
            elif name and name_expr:
                row = conn.execute(
                    f"SELECT * FROM students WHERE {name_expr} LIKE ? LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()
            else:
                return None

            if not row:
                return None

            rk = row.keys()
            stage = {
                "system": "college",
                "student_id": row[id_col] if id_col in rk else str(row["id"]) if "id" in rk else "",
                "name": self._extract_name(row, cols),
                "dob": row["date_of_birth"] if "date_of_birth" in rk else row["dob"] if "dob" in rk else "",
                "year_group": row["year_group"] if "year_group" in rk else "",
                "status": row["status"] if "status" in rk else "unknown",
                "enrolled_date": row["enrollment_date"] if "enrollment_date" in rk else (
                    row["enrolled_date"] if "enrolled_date" in rk else ""
                ),
                "previous_system_id": row["previous_system_id"] if "previous_system_id" in rk else "",
                "academic_history": [],
            }

            stage["academic_history"] = self._get_transfer_history(conn, "college", stage["student_id"])

            return stage
        except Exception as e:
            logger.warning("Error querying college student journey: %s", e)
            return None
        finally:
            conn.close()

    def _query_university(self, name=None, student_id=None):
        conn = self._connect("university")
        if not conn:
            return None
        try:
            if not _table_exists(conn, "students"):
                return None
            cols = _get_columns(conn, "students")
            name_expr = self._name_search_expr(cols, "students")
            id_col = "student_id" if "student_id" in cols else "id"

            if student_id:
                row = conn.execute(
                    f"SELECT * FROM students WHERE {id_col} = ?", (student_id,)
                ).fetchone()
                if not row and id_col != "id" and "id" in cols:
                    row = conn.execute(
                        "SELECT * FROM students WHERE id = ?", (student_id,)
                    ).fetchone()
            elif name and name_expr:
                row = conn.execute(
                    f"SELECT * FROM students WHERE {name_expr} LIKE ? LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()
            else:
                return None

            if not row:
                return None

            rk = row.keys()
            year_col = "year_group" if "year_group" in rk else ("year" if "year" in rk else None)
            stage = {
                "system": "university",
                "student_id": row[id_col] if id_col in rk else str(row["id"]) if "id" in rk else "",
                "name": self._extract_name(row, cols),
                "dob": row["date_of_birth"] if "date_of_birth" in rk else row["dob"] if "dob" in rk else "",
                "year_group": row[year_col] if year_col else "",
                "status": row["status"] if "status" in rk else "unknown",
                "enrolled_date": row["enrollment_date"] if "enrollment_date" in rk else (
                    row["enrolled_date"] if "enrolled_date" in rk else ""
                ),
                "previous_system_id": row["previous_system_id"] if "previous_system_id" in rk else "",
                "academic_history": [],
            }

            stage["academic_history"] = self._get_transfer_history(conn, "university", stage["student_id"])

            return stage
        except Exception as e:
            logger.warning("Error querying university student journey: %s", e)
            return None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Link following
    # ------------------------------------------------------------------

    def _follow_links(self, start_stage, stages):
        """Follow previous_system_id links to find earlier stages.

        Also checks later systems for references to the start stage.
        """
        order = ["primary", "secondary", "college", "university"]
        found_systems = {s["system"] for s in stages}

        # Follow backward links
        current = start_stage
        while current.get("previous_system_id"):
            prev_id = current["previous_system_id"]
            idx = order.index(current["system"]) if current["system"] in order else -1
            if idx <= 0:
                break
            prev_system = order[idx - 1]
            if prev_system in found_systems:
                break
            prev_stage = self._query_system(prev_system, student_id=prev_id)
            if not prev_stage:
                break
            stages.append(prev_stage)
            found_systems.add(prev_system)
            current = prev_stage

        # Try to find forward links by searching later systems by name
        start_name = start_stage.get("name", "")
        if start_name:
            start_idx = order.index(start_stage["system"]) if start_stage["system"] in order else -1
            for i in range(start_idx + 1, len(order)):
                sys_key = order[i]
                if sys_key in found_systems:
                    continue
                later_stage = self._query_system(sys_key, name=start_name)
                if later_stage:
                    stages.append(later_stage)
                    found_systems.add(sys_key)

        return stages

    # ------------------------------------------------------------------
    # Transfer history
    # ------------------------------------------------------------------

    def _get_transfer_history(self, conn, system, student_id):
        """Look for academic_transfer_history table and return records."""
        try:
            if not _table_exists(conn, "academic_transfer_history"):
                return []
            cols = _get_columns(conn, "academic_transfer_history")
            # Try to match on student_id column
            id_col = None
            for candidate in ("student_id", "pupil_id", "source_student_id"):
                if candidate in cols:
                    id_col = candidate
                    break
            if not id_col:
                return []

            rows = conn.execute(
                f"SELECT * FROM academic_transfer_history WHERE {id_col} = ? "
                f"ORDER BY rowid",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("Error getting transfer history for %s in %s: %s", student_id, system, e)
            return []

    # ------------------------------------------------------------------
    # Name utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _name_search_expr(columns, table=None):
        """Build a SQL expression for a full-name search.

        Handles schemas with ``full_name``, ``name``, or separate
        ``first_name``/``last_name`` (or ``forename``/``surname``) columns.
        """
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

    @staticmethod
    def _extract_name(row, columns):
        """Extract the student name from a row given the column set."""
        rk = row.keys() if hasattr(row, "keys") else []
        if "full_name" in rk:
            return row["full_name"] or ""
        if "name" in rk:
            return row["name"] or ""
        parts = []
        for fn in ("first_name", "forename"):
            if fn in rk and row[fn]:
                parts.append(row[fn])
                break
        for ln in ("last_name", "surname"):
            if ln in rk and row[ln]:
                parts.append(row[ln])
                break
        return " ".join(parts) if parts else ""
