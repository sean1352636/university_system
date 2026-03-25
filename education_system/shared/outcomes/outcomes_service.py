"""Student outcome tracking service.

Tracks what happens to students after leaving each education system by
querying academic_transfer_history and student records across all 4 systems.
"""

import sqlite3
from pathlib import Path


def _default_db_paths():
    """Return a dict of system -> default database Path."""
    shared_dir = Path(__file__).resolve().parent.parent  # .../shared
    edu_root = shared_dir.parent  # .../education_system
    return {
        "primary": edu_root / "primary_school" / "data" / "db_files" / "primary_school.db",
        "secondary": edu_root / "secondary_school" / "data" / "db_files" / "secondary_school.db",
        "college": edu_root / "college_system" / "data" / "db_files" / "sixthform.db",
        "university": edu_root / "university_system" / "data" / "db_files" / "student_records.db",
    }


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


SYSTEM_ORDER = ["primary", "secondary", "college", "university"]

SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}

# Map each system to the next system in the progression
NEXT_SYSTEM = {
    "primary": "secondary",
    "secondary": "college",
    "college": "university",
}


class OutcomesService:
    """Tracks student outcomes after leaving each education system."""

    def __init__(self, primary_db=None, secondary_db=None, college_db=None, university_db=None):
        defaults = _default_db_paths()
        self._db_paths = {
            "primary": Path(primary_db) if primary_db else defaults["primary"],
            "secondary": Path(secondary_db) if secondary_db else defaults["secondary"],
            "college": Path(college_db) if college_db else defaults["college"],
            "university": Path(university_db) if university_db else defaults["university"],
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _connect(self, system):
        """Open a read-only connection.  Returns None if DB missing."""
        path = self._db_paths.get(system)
        if not path or not path.exists():
            return None
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    def _student_table(self, system):
        return "pupils" if system == "primary" else "students"

    def _id_column(self, system, columns):
        if system == "primary":
            return "pupil_id" if "pupil_id" in columns else "id"
        return "student_id" if "student_id" in columns else "id"

    @staticmethod
    def _name_expr(columns):
        """Build a SQL expression for full name."""
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

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get_outcomes_for_system(self, source_system):
        """Get outcomes for students who left *source_system*.

        Returns a list of dicts with keys:
            student_name, student_id, source_system, destination_system,
            destination_status, grade_average, transfer_date
        """
        results = []
        if source_system not in SYSTEM_ORDER:
            return results

        dest_system = NEXT_SYSTEM.get(source_system)
        if not dest_system:
            # University is the last system; check for graduated students
            return self._get_university_outcomes()

        # Strategy 1: Check destination system for students with previous_system_id
        results.extend(self._outcomes_from_destination(source_system, dest_system))

        # Strategy 2: Check academic_transfer_history in both systems
        results.extend(self._outcomes_from_transfer_history(source_system, dest_system))

        # Deduplicate by student name (rough dedup)
        seen = set()
        deduped = []
        for r in results:
            key = (r.get("student_name", "").lower(), r.get("destination_system", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        return deduped

    def get_progression_stats(self, source_system):
        """Get aggregate progression statistics for a source system.

        Returns a dict with keys:
            source_system, source_label, total_left, progressed_count,
            progression_rate, avg_grade_at_destination,
            destination_status_breakdown
        """
        outcomes = self.get_outcomes_for_system(source_system)
        total_left = len(outcomes)
        progressed = [o for o in outcomes if o.get("destination_status") in
                      ("active", "enrolled", "current", "graduated", "completed")]
        grades = [o["grade_average"] for o in outcomes
                  if o.get("grade_average") is not None and o["grade_average"] > 0]

        # Status breakdown
        status_counts = {}
        for o in outcomes:
            st = o.get("destination_status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1

        return {
            "source_system": source_system,
            "source_label": SYSTEM_LABELS.get(source_system, source_system),
            "total_left": total_left,
            "progressed_count": len(progressed),
            "progression_rate": round(len(progressed) / total_left * 100, 1) if total_left > 0 else 0.0,
            "avg_grade_at_destination": round(sum(grades) / len(grades), 2) if grades else None,
            "destination_status_breakdown": status_counts,
        }

    def search_student_outcome(self, name_query):
        """Search for a student across systems and return their outcomes.

        Returns a list of outcome dicts for any student matching *name_query*.
        """
        if not name_query or not name_query.strip():
            return []

        results = []
        pattern = f"%{name_query.strip()}%"

        for sys_key in SYSTEM_ORDER:
            conn = self._connect(sys_key)
            if not conn:
                continue
            try:
                table = self._student_table(sys_key)
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_ex = self._name_expr(cols)
                if not name_ex:
                    continue
                id_col = self._id_column(sys_key, cols)
                status_col = "status" if "status" in cols else None

                select = f"{id_col}, {name_ex} AS full_name"
                if status_col:
                    select += f", {status_col}"

                rows = conn.execute(
                    f"SELECT {select} FROM {table} WHERE {name_ex} LIKE ? LIMIT 20",
                    (pattern,),
                ).fetchall()

                for r in rows:
                    sid = r[0]
                    name = r["full_name"]
                    status = r["status"] if status_col and "status" in r.keys() else "unknown"

                    # Check if they appear in a later system
                    dest_info = self._find_in_later_systems(sys_key, name)

                    results.append({
                        "student_name": name,
                        "student_id": sid,
                        "source_system": sys_key,
                        "source_status": status,
                        "destination_system": dest_info.get("system", "N/A"),
                        "destination_status": dest_info.get("status", "N/A"),
                        "grade_average": dest_info.get("grade_average"),
                    })
            except Exception:
                pass
            finally:
                conn.close()

        return results

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _outcomes_from_destination(self, source_system, dest_system):
        """Find students in dest_system who have previous_system_id set."""
        results = []
        conn = self._connect(dest_system)
        if not conn:
            return results
        try:
            table = self._student_table(dest_system)
            if not _table_exists(conn, table):
                return results
            cols = _get_columns(conn, table)
            if "previous_system_id" not in cols:
                return results

            name_ex = self._name_expr(cols)
            id_col = self._id_column(dest_system, cols)
            status_col = "status" if "status" in cols else None

            select = f"{id_col}, previous_system_id, {name_ex} AS full_name"
            if status_col:
                select += f", {status_col}"

            rows = conn.execute(
                f"SELECT {select} FROM {table} "
                f"WHERE previous_system_id IS NOT NULL AND previous_system_id != ''"
            ).fetchall()

            for r in rows:
                grade_avg = self._get_grade_average(conn, dest_system, r[id_col] if id_col in r.keys() else r[0])
                results.append({
                    "student_name": r["full_name"] or "",
                    "student_id": r["previous_system_id"],
                    "source_system": source_system,
                    "destination_system": dest_system,
                    "destination_status": r["status"] if status_col and "status" in r.keys() else "unknown",
                    "grade_average": grade_avg,
                    "transfer_date": "",
                })
        except Exception:
            pass
        finally:
            conn.close()
        return results

    def _outcomes_from_transfer_history(self, source_system, dest_system):
        """Find outcomes via academic_transfer_history tables."""
        results = []

        # Check transfer history in destination system
        conn = self._connect(dest_system)
        if not conn:
            return results
        try:
            if not _table_exists(conn, "academic_transfer_history"):
                return results
            cols = _get_columns(conn, "academic_transfer_history")

            source_col = None
            for c in ("source_system", "from_system", "previous_system"):
                if c in cols:
                    source_col = c
                    break

            if not source_col:
                return results

            id_col = None
            for c in ("student_id", "pupil_id", "source_student_id"):
                if c in cols:
                    id_col = c
                    break

            if not id_col:
                return results

            rows = conn.execute(
                f"SELECT * FROM academic_transfer_history WHERE {source_col} = ?",
                (source_system,),
            ).fetchall()

            for r in rows:
                rk = r.keys()
                name = ""
                for n in ("student_name", "name", "full_name"):
                    if n in rk and r[n]:
                        name = r[n]
                        break

                grade = None
                for g in ("grade", "score", "average_grade"):
                    if g in rk and r[g] is not None:
                        try:
                            grade = float(r[g])
                        except (ValueError, TypeError):
                            pass
                        break

                transfer_date = ""
                for d in ("transfer_date", "date", "created_at"):
                    if d in rk and r[d]:
                        transfer_date = str(r[d])
                        break

                results.append({
                    "student_name": name,
                    "student_id": r[id_col],
                    "source_system": source_system,
                    "destination_system": dest_system,
                    "destination_status": r["status"] if "status" in rk else "transferred",
                    "grade_average": grade,
                    "transfer_date": transfer_date,
                })
        except Exception:
            pass
        finally:
            conn.close()

        return results

    def _get_university_outcomes(self):
        """For university (terminal system), get graduated students."""
        results = []
        conn = self._connect("university")
        if not conn:
            return results
        try:
            if not _table_exists(conn, "students"):
                return results
            cols = _get_columns(conn, "students")
            name_ex = self._name_expr(cols)
            id_col = self._id_column("university", cols)
            if not name_ex:
                return results

            status_col = "status" if "status" in cols else None
            if not status_col:
                return results

            rows = conn.execute(
                f"SELECT {id_col}, {name_ex} AS full_name, {status_col} "
                f"FROM students WHERE LOWER({status_col}) IN ('graduated', 'completed')"
            ).fetchall()

            for r in rows:
                results.append({
                    "student_name": r["full_name"] or "",
                    "student_id": r[0],
                    "source_system": "university",
                    "destination_system": "graduated",
                    "destination_status": r["status"],
                    "grade_average": self._get_grade_average(conn, "university", r[0]),
                    "transfer_date": "",
                })
        except Exception:
            pass
        finally:
            conn.close()
        return results

    def _get_grade_average(self, conn, system, student_id):
        """Try to compute a grade average for a student in the given system."""
        try:
            # Try grades table
            for table in ("grades", "grade_records", "student_grades"):
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)

                id_col = None
                for c in ("student_id", "pupil_id"):
                    if c in cols:
                        id_col = c
                        break
                if not id_col:
                    continue

                grade_col = None
                for c in ("grade", "score", "mark", "percentage"):
                    if c in cols:
                        grade_col = c
                        break
                if not grade_col:
                    continue

                row = conn.execute(
                    f"SELECT AVG(CAST({grade_col} AS REAL)) AS avg_grade "
                    f"FROM {table} WHERE {id_col} = ? AND {grade_col} IS NOT NULL",
                    (student_id,),
                ).fetchone()

                if row and row["avg_grade"] is not None:
                    return round(row["avg_grade"], 2)
        except Exception:
            pass
        return None

    def _find_in_later_systems(self, source_system, student_name):
        """Check if student_name appears in any system after source_system."""
        idx = SYSTEM_ORDER.index(source_system) if source_system in SYSTEM_ORDER else -1
        if idx < 0:
            return {}

        for i in range(idx + 1, len(SYSTEM_ORDER)):
            sys_key = SYSTEM_ORDER[i]
            conn = self._connect(sys_key)
            if not conn:
                continue
            try:
                table = self._student_table(sys_key)
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_ex = self._name_expr(cols)
                if not name_ex:
                    continue
                id_col = self._id_column(sys_key, cols)

                row = conn.execute(
                    f"SELECT {id_col}, {name_ex} AS full_name, "
                    f"{'status, ' if 'status' in cols else ''}"
                    f"1 AS found FROM {table} WHERE {name_ex} LIKE ? LIMIT 1",
                    (f"%{student_name}%",),
                ).fetchone()

                if row:
                    rk = row.keys()
                    grade_avg = self._get_grade_average(conn, sys_key, row[0])
                    return {
                        "system": sys_key,
                        "status": row["status"] if "status" in rk else "unknown",
                        "grade_average": grade_avg,
                    }
            except Exception:
                pass
            finally:
                conn.close()

        return {}
