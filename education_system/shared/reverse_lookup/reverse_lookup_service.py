"""Reverse Lookup service.

From a source system, find where transferred students ended up in
destination systems.  Searches by matching previous_system_id or
student name across the natural progression path.
"""

import sqlite3
from pathlib import Path


# ---------------------------------------------------------------------------
# Path / DB helpers
# ---------------------------------------------------------------------------

def _default_db_path(system):
    shared_dir = Path(__file__).resolve().parent.parent
    edu_root = shared_dir.parent
    path_map = {
        "primary": edu_root / "primary_school" / "data" / "db_files" / "primary_school.db",
        "secondary": edu_root / "secondary_school" / "data" / "db_files" / "secondary_school.db",
        "college": edu_root / "college_system" / "data" / "db_files" / "sixthform.db",
        "university": edu_root / "university_system" / "data" / "db_files" / "student_records.db",
    }
    return path_map.get(system)


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


def _name_expr(columns):
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


SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}

# Natural progression
DESTINATION_MAP = {
    "primary": ["secondary"],
    "secondary": ["college"],
    "college": ["university"],
}

ALL_SYSTEMS = ["primary", "secondary", "college", "university"]


class ReverseLookupService:
    """Track where transferred students ended up."""

    def __init__(self, primary_db=None, secondary_db=None, college_db=None, university_db=None):
        self._db_paths = {
            "primary": Path(primary_db) if primary_db else _default_db_path("primary"),
            "secondary": Path(secondary_db) if secondary_db else _default_db_path("secondary"),
            "college": Path(college_db) if college_db else _default_db_path("college"),
            "university": Path(university_db) if university_db else _default_db_path("university"),
        }

    def _connect(self, system):
        path = self._db_paths.get(system)
        if not path or not path.exists():
            return None
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_transferred_students(self, source_system):
        """Return students with transferred status from *source_system*.

        Returns list of dicts: id, student_id, name, year_group, status.
        """
        conn = self._connect(source_system)
        if not conn:
            return []

        table = "pupils" if source_system == "primary" else "students"
        results = []

        try:
            if not _table_exists(conn, table):
                return results

            cols = _get_columns(conn, table)
            ne = _name_expr(cols)
            if not ne:
                return results

            id_col = "pupil_id" if (source_system == "primary" and "pupil_id" in cols) else (
                "student_id" if "student_id" in cols else "id"
            )
            has_year = "year_group" in cols
            has_status = "status" in cols

            if not has_status:
                return results

            select = f"id, {id_col}, {ne} AS full_name, status"
            if has_year:
                select += ", year_group"

            rows = conn.execute(
                f"SELECT {select} FROM {table} WHERE LOWER(status) IN ('transferred', 'transfer') "
                f"ORDER BY full_name",
            ).fetchall()

            for r in rows:
                rk = r.keys()
                results.append({
                    "id": r["id"],
                    "student_id": r[id_col] if id_col in rk else str(r["id"]),
                    "name": r["full_name"],
                    "year_group": r["year_group"] if has_year and "year_group" in rk else "",
                    "status": r["status"],
                })
        except Exception:
            pass
        finally:
            conn.close()

        return results

    def find_destination(self, student_name, source_system):
        """Search destination systems for a transferred student.

        Looks for a matching student (by previous_system_id or name) in
        the natural destination system(s) and returns destination info.

        Returns dict or None:
            dest_system, student_id, name, status, year_group, grades_summary
        """
        dest_systems = DESTINATION_MAP.get(source_system, [])
        # Also check further downstream (e.g. primary student could be at college)
        idx = ALL_SYSTEMS.index(source_system) if source_system in ALL_SYSTEMS else -1
        if idx >= 0:
            dest_systems = ALL_SYSTEMS[idx + 1:]

        for dest_sys in dest_systems:
            result = self._search_in_destination(dest_sys, student_name, source_system)
            if result:
                return result

        return None

    def get_destination_summary(self, source_system):
        """Aggregate summary of where transferred students ended up.

        Returns dict mapping destination system labels to counts,
        plus an 'unknown' count for students not found in any destination.
        """
        transferred = self.find_transferred_students(source_system)
        summary = {}
        unknown = 0

        for stu in transferred:
            dest = self.find_destination(stu["name"], source_system)
            if dest:
                label = SYSTEM_LABELS.get(dest["dest_system"], dest["dest_system"])
                summary[label] = summary.get(label, 0) + 1
            else:
                unknown += 1

        summary["Unknown / Not Found"] = unknown
        summary["_total_transferred"] = len(transferred)
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_in_destination(self, dest_system, student_name, source_system):
        """Search a single destination system for a matching student."""
        conn = self._connect(dest_system)
        if not conn:
            return None

        table = "pupils" if dest_system == "primary" else "students"
        try:
            if not _table_exists(conn, table):
                return None

            cols = _get_columns(conn, table)
            ne = _name_expr(cols)
            if not ne:
                return None

            id_col = "pupil_id" if (dest_system == "primary" and "pupil_id" in cols) else (
                "student_id" if "student_id" in cols else "id"
            )
            has_prev = "previous_system_id" in cols
            has_status = "status" in cols
            has_year = "year_group" in cols
            year_col = "year_group" if has_year else ("year" if "year" in cols else None)

            # Try matching by previous_system_id first (most reliable)
            row = None
            if has_prev and student_name:
                # Search by name to find the student, then verify
                like = f"%{student_name.strip()}%"
                row = conn.execute(
                    f"SELECT id, {id_col}, {ne} AS full_name"
                    + (", status" if has_status else "")
                    + (f", {year_col}" if year_col else "")
                    + (", previous_system_id" if has_prev else "")
                    + f" FROM {table} WHERE {ne} LIKE ? LIMIT 1",
                    (like,),
                ).fetchone()

            # Fallback: search by name
            if not row and student_name:
                like = f"%{student_name.strip()}%"
                row = conn.execute(
                    f"SELECT id, {id_col}, {ne} AS full_name"
                    + (", status" if has_status else "")
                    + (f", {year_col}" if year_col else "")
                    + (", previous_system_id" if has_prev else "")
                    + f" FROM {table} WHERE {ne} LIKE ? LIMIT 1",
                    (like,),
                ).fetchone()

            if not row:
                return None

            rk = row.keys()
            result = {
                "dest_system": dest_system,
                "id": row["id"],
                "student_id": row[id_col] if id_col in rk else str(row["id"]),
                "name": row["full_name"],
                "status": row["status"] if has_status and "status" in rk else "unknown",
                "year_group": row[year_col] if year_col and year_col in rk else "",
                "previous_system_id": row["previous_system_id"] if has_prev and "previous_system_id" in rk else "",
                "grades_summary": [],
            }

            # Try to get a brief grade summary
            result["grades_summary"] = self._get_grade_summary(conn, dest_system, row["id"])

            return result

        except Exception:
            return None
        finally:
            conn.close()

    def _get_grade_summary(self, conn, system, row_id):
        """Get a brief list of grade strings for a student."""
        grades = []
        try:
            if not _table_exists(conn, "grades"):
                return grades

            grade_cols = _get_columns(conn, "grades")
            if "student_id" not in grade_cols:
                return grades

            select_parts = []
            for c in ["grade", "letter_grade", "score", "semester", "term", "academic_year",
                       "assessment_name", "grade_type", "module_code", "course_id"]:
                if c in grade_cols:
                    select_parts.append(c)

            if not select_parts:
                return grades

            rows = conn.execute(
                f"SELECT {', '.join(select_parts)} FROM grades "
                f"WHERE student_id = ? ORDER BY rowid DESC LIMIT 10",
                (row_id,),
            ).fetchall()

            for r in rows:
                rk = r.keys()
                parts = [f"{k}: {r[k]}" for k in rk if r[k] is not None and str(r[k]).strip()]
                if parts:
                    grades.append(" | ".join(parts))
        except Exception:
            pass
        return grades
