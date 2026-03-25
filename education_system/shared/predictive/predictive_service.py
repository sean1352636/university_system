"""Predictive alerts service.

Analyzes patterns from previous education systems to flag at-risk students
in their current system.  Checks academic_transfer_history for indicators
such as poor attendance (<80%) or low grades, and generates risk
assessments.
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

PREV_SYSTEM = {
    "secondary": "primary",
    "college": "secondary",
    "university": "college",
}

# Thresholds for risk classification
ATTENDANCE_LOW = 80.0       # below this is a risk factor
ATTENDANCE_CRITICAL = 60.0  # below this is high risk
GRADE_LOW = 50.0            # below this numeric threshold is a risk factor
GRADE_CRITICAL = 30.0       # below this is high risk


class PredictiveService:
    """Analyzes cross-system data to identify at-risk students."""

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

    def get_at_risk_students(self, system, db_path=None):
        """Identify at-risk students in *system*.

        Looks at current students who have previous_system_id set, then
        checks their academic_transfer_history for poor attendance (<80%)
        or low grades.

        Returns a list of dicts with keys:
            student_id, student_name, system, risk_level (High/Medium/Low),
            risk_score, risk_factors (list of strings),
            previous_system, attendance_pct, grade_average
        """
        results = []
        conn = self._connect(system)
        if not conn:
            return results

        try:
            table = self._student_table(system)
            if not _table_exists(conn, table):
                return results
            cols = _get_columns(conn, table)

            # Only consider students with a previous system link
            if "previous_system_id" not in cols:
                return results

            name_ex = self._name_expr(cols)
            id_col = self._id_column(system, cols)
            if not name_ex:
                return results

            status_col = "status" if "status" in cols else None

            # Get active students with previous_system_id
            where_clause = "previous_system_id IS NOT NULL AND previous_system_id != ''"
            if status_col:
                where_clause += f" AND LOWER({status_col}) IN ('active', 'enrolled', 'current')"

            select = f"{id_col}, previous_system_id, {name_ex} AS full_name"
            if status_col:
                select += f", {status_col}"

            rows = conn.execute(
                f"SELECT {select} FROM {table} WHERE {where_clause}"
            ).fetchall()

            for r in rows:
                student_id = r[id_col] if id_col in r.keys() else r[0]
                prev_id = r["previous_system_id"]
                name = r["full_name"] or ""

                # Gather risk factors from transfer history and previous system
                risk_factors = []
                attendance_pct = None
                grade_average = None
                prev_system = PREV_SYSTEM.get(system, "unknown")

                # Check transfer history in current system
                history = self._get_transfer_history(conn, system, student_id)
                for h in history:
                    att = self._extract_attendance(h)
                    if att is not None:
                        attendance_pct = att
                    gr = self._extract_grade(h)
                    if gr is not None:
                        grade_average = gr

                # Also check previous system for attendance/grades
                prev_att, prev_grade = self._check_previous_system(
                    prev_system, prev_id, name
                )
                if attendance_pct is None:
                    attendance_pct = prev_att
                if grade_average is None:
                    grade_average = prev_grade

                # Also check current system attendance table
                curr_att = self._check_current_attendance(conn, system, student_id)
                if curr_att is not None:
                    # Use current attendance if available (more relevant)
                    attendance_pct = curr_att

                # Build risk factors
                if attendance_pct is not None and attendance_pct < ATTENDANCE_LOW:
                    if attendance_pct < ATTENDANCE_CRITICAL:
                        risk_factors.append(
                            f"Critical attendance: {attendance_pct:.1f}% (below {ATTENDANCE_CRITICAL}%)"
                        )
                    else:
                        risk_factors.append(
                            f"Low attendance: {attendance_pct:.1f}% (below {ATTENDANCE_LOW}%)"
                        )

                if grade_average is not None and grade_average < GRADE_LOW:
                    if grade_average < GRADE_CRITICAL:
                        risk_factors.append(
                            f"Critical grades: {grade_average:.1f} (below {GRADE_CRITICAL})"
                        )
                    else:
                        risk_factors.append(
                            f"Low grades: {grade_average:.1f} (below {GRADE_LOW})"
                        )

                # Check for multiple system transfers (instability indicator)
                transfer_count = len(history)
                if transfer_count >= 2:
                    risk_factors.append(
                        f"Multiple transfers: {transfer_count} recorded transitions"
                    )

                # Only include students with actual risk factors
                if not risk_factors:
                    # Still flag students from previous system with no data as low risk
                    risk_factors.append(
                        "Limited historical data from previous system"
                    )

                # Calculate risk score and level
                risk_score = self._calculate_risk_score(
                    attendance_pct, grade_average, transfer_count
                )
                risk_level = self._score_to_level(risk_score)

                results.append({
                    "student_id": student_id,
                    "student_name": name,
                    "system": system,
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "risk_factors": risk_factors,
                    "previous_system": prev_system,
                    "attendance_pct": attendance_pct,
                    "grade_average": grade_average,
                })

        except Exception:
            pass
        finally:
            conn.close()

        # Sort by risk score descending (highest risk first)
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def get_risk_factors(self, student_id, system):
        """Return detailed risk factors for a specific student.

        Returns a dict with keys:
            student_id, student_name, system, risk_level, risk_score,
            risk_factors, attendance_history, grade_history,
            transfer_history, previous_system_info
        """
        conn = self._connect(system)
        if not conn:
            return {"student_id": student_id, "system": system,
                    "error": "Database not available"}
        try:
            table = self._student_table(system)
            if not _table_exists(conn, table):
                return {"student_id": student_id, "system": system,
                        "error": "Student table not found"}

            cols = _get_columns(conn, table)
            id_col = self._id_column(system, cols)
            name_ex = self._name_expr(cols)

            row = conn.execute(
                f"SELECT * FROM {table} WHERE {id_col} = ?",
                (student_id,),
            ).fetchone()

            if not row:
                return {"student_id": student_id, "system": system,
                        "error": "Student not found"}

            rk = row.keys()
            name = ""
            if name_ex:
                try:
                    name_row = conn.execute(
                        f"SELECT {name_ex} AS full_name FROM {table} WHERE {id_col} = ?",
                        (student_id,),
                    ).fetchone()
                    name = name_row["full_name"] if name_row else ""
                except Exception:
                    pass

            prev_id = row["previous_system_id"] if "previous_system_id" in rk else None
            prev_system = PREV_SYSTEM.get(system, "unknown")

            # Gather detailed history
            transfer_history = self._get_transfer_history(conn, system, student_id)
            attendance_history = self._get_attendance_history(conn, system, student_id)
            grade_history = self._get_grade_history(conn, system, student_id)

            # Previous system info
            prev_info = {}
            if prev_id and prev_system in SYSTEM_ORDER:
                prev_info = self._get_previous_system_info(prev_system, prev_id, name)

            # Calculate risk from all at-risk students
            all_risks = self.get_at_risk_students(system)
            student_risk = next(
                (r for r in all_risks if str(r["student_id"]) == str(student_id)),
                None,
            )

            result = {
                "student_id": student_id,
                "student_name": name,
                "system": system,
                "risk_level": student_risk["risk_level"] if student_risk else "Unknown",
                "risk_score": student_risk["risk_score"] if student_risk else 0,
                "risk_factors": student_risk["risk_factors"] if student_risk else [],
                "attendance_history": attendance_history,
                "grade_history": grade_history,
                "transfer_history": transfer_history,
                "previous_system_info": prev_info,
            }
            return result

        except Exception as exc:
            return {"student_id": student_id, "system": system,
                    "error": str(exc)}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # internal: data extraction
    # ------------------------------------------------------------------

    def _get_transfer_history(self, conn, system, student_id):
        """Get transfer history records for a student."""
        try:
            if not _table_exists(conn, "academic_transfer_history"):
                return []
            cols = _get_columns(conn, "academic_transfer_history")
            id_col = None
            for c in ("student_id", "pupil_id", "source_student_id"):
                if c in cols:
                    id_col = c
                    break
            if not id_col:
                return []
            rows = conn.execute(
                f"SELECT * FROM academic_transfer_history WHERE {id_col} = ? ORDER BY rowid",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _get_attendance_history(self, conn, system, student_id):
        """Get attendance records for a student."""
        records = []
        for table_name in ("attendance", "attendance_records", "student_attendance"):
            if not _table_exists(conn, table_name):
                continue
            try:
                cols = _get_columns(conn, table_name)
                id_col = None
                for c in ("student_id", "pupil_id"):
                    if c in cols:
                        id_col = c
                        break
                if not id_col:
                    continue
                rows = conn.execute(
                    f"SELECT * FROM {table_name} WHERE {id_col} = ? ORDER BY rowid DESC LIMIT 50",
                    (student_id,),
                ).fetchall()
                records.extend([dict(r) for r in rows])
            except Exception:
                pass
        return records

    def _get_grade_history(self, conn, system, student_id):
        """Get grade records for a student."""
        records = []
        for table_name in ("grades", "grade_records", "student_grades"):
            if not _table_exists(conn, table_name):
                continue
            try:
                cols = _get_columns(conn, table_name)
                id_col = None
                for c in ("student_id", "pupil_id"):
                    if c in cols:
                        id_col = c
                        break
                if not id_col:
                    continue
                rows = conn.execute(
                    f"SELECT * FROM {table_name} WHERE {id_col} = ? ORDER BY rowid DESC LIMIT 50",
                    (student_id,),
                ).fetchall()
                records.extend([dict(r) for r in rows])
            except Exception:
                pass
        return records

    def _check_current_attendance(self, conn, system, student_id):
        """Check current system attendance percentage."""
        for table_name in ("attendance", "attendance_records", "student_attendance"):
            if not _table_exists(conn, table_name):
                continue
            try:
                cols = _get_columns(conn, table_name)
                id_col = None
                for c in ("student_id", "pupil_id"):
                    if c in cols:
                        id_col = c
                        break
                if not id_col:
                    continue

                # Try percentage column first
                for pct_col in ("attendance_percentage", "percentage", "attendance_pct"):
                    if pct_col in cols:
                        row = conn.execute(
                            f"SELECT AVG(CAST({pct_col} AS REAL)) AS avg_pct "
                            f"FROM {table_name} WHERE {id_col} = ? AND {pct_col} IS NOT NULL",
                            (student_id,),
                        ).fetchone()
                        if row and row["avg_pct"] is not None:
                            return round(row["avg_pct"], 1)

                # Try status-based calculation (present/absent)
                if "status" in cols:
                    total = conn.execute(
                        f"SELECT COUNT(*) FROM {table_name} WHERE {id_col} = ?",
                        (student_id,),
                    ).fetchone()[0]
                    if total > 0:
                        present = conn.execute(
                            f"SELECT COUNT(*) FROM {table_name} "
                            f"WHERE {id_col} = ? AND LOWER(status) IN ('present', 'p', 'late', 'l')",
                            (student_id,),
                        ).fetchone()[0]
                        return round(present / total * 100, 1)
            except Exception:
                pass
        return None

    def _check_previous_system(self, prev_system, prev_id, name):
        """Check previous system for attendance and grade data."""
        attendance = None
        grade = None

        conn = self._connect(prev_system)
        if not conn:
            return attendance, grade

        try:
            # Try to find student by prev_id or name
            table = self._student_table(prev_system)
            if not _table_exists(conn, table):
                return attendance, grade

            cols = _get_columns(conn, table)
            id_col = self._id_column(prev_system, cols)

            # Check if student exists
            row = conn.execute(
                f"SELECT {id_col} FROM {table} WHERE {id_col} = ? LIMIT 1",
                (prev_id,),
            ).fetchone()

            if not row and name:
                name_ex = self._name_expr(cols)
                if name_ex:
                    row = conn.execute(
                        f"SELECT {id_col} FROM {table} WHERE {name_ex} LIKE ? LIMIT 1",
                        (f"%{name}%",),
                    ).fetchone()

            if not row:
                return attendance, grade

            sid = row[0]

            # Check attendance
            attendance = self._check_current_attendance(conn, prev_system, sid)

            # Check grades
            for grade_table in ("grades", "grade_records", "student_grades"):
                if not _table_exists(conn, grade_table):
                    continue
                gcols = _get_columns(conn, grade_table)
                gid_col = None
                for c in ("student_id", "pupil_id"):
                    if c in gcols:
                        gid_col = c
                        break
                if not gid_col:
                    continue

                for g_col in ("grade", "score", "mark", "percentage"):
                    if g_col not in gcols:
                        continue
                    grow = conn.execute(
                        f"SELECT AVG(CAST({g_col} AS REAL)) AS avg_grade "
                        f"FROM {grade_table} WHERE {gid_col} = ? AND {g_col} IS NOT NULL",
                        (sid,),
                    ).fetchone()
                    if grow and grow["avg_grade"] is not None:
                        grade = round(grow["avg_grade"], 2)
                        break
                if grade is not None:
                    break

        except Exception:
            pass
        finally:
            conn.close()

        return attendance, grade

    def _get_previous_system_info(self, prev_system, prev_id, name):
        """Get summary info about a student from their previous system."""
        conn = self._connect(prev_system)
        if not conn:
            return {"system": prev_system, "available": False}

        try:
            table = self._student_table(prev_system)
            if not _table_exists(conn, table):
                return {"system": prev_system, "available": False}

            cols = _get_columns(conn, table)
            id_col = self._id_column(prev_system, cols)
            name_ex = self._name_expr(cols)

            row = conn.execute(
                f"SELECT * FROM {table} WHERE {id_col} = ? LIMIT 1",
                (prev_id,),
            ).fetchone()

            if not row and name and name_ex:
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE {name_ex} LIKE ? LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()

            if not row:
                return {"system": prev_system, "available": False}

            rk = row.keys()
            return {
                "system": prev_system,
                "label": SYSTEM_LABELS.get(prev_system, prev_system),
                "available": True,
                "student_id": row[id_col] if id_col in rk else str(row[0]),
                "status": row["status"] if "status" in rk else "unknown",
                "year_group": row["year_group"] if "year_group" in rk else "",
            }
        except Exception:
            return {"system": prev_system, "available": False}
        finally:
            conn.close()

    @staticmethod
    def _extract_attendance(history_record):
        """Extract attendance percentage from a transfer history record."""
        for key in ("attendance", "attendance_pct", "attendance_percentage",
                     "prev_attendance"):
            val = history_record.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
        return None

    @staticmethod
    def _extract_grade(history_record):
        """Extract grade average from a transfer history record."""
        for key in ("grade", "average_grade", "grade_average", "score",
                     "prev_grade"):
            val = history_record.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
        return None

    @staticmethod
    def _calculate_risk_score(attendance_pct, grade_average, transfer_count):
        """Calculate a numeric risk score from 0 (no risk) to 100 (highest risk)."""
        score = 0

        # Attendance component (max 40 points)
        if attendance_pct is not None:
            if attendance_pct < ATTENDANCE_CRITICAL:
                score += 40
            elif attendance_pct < ATTENDANCE_LOW:
                # Linear scale between 80% and 60%
                frac = (ATTENDANCE_LOW - attendance_pct) / (ATTENDANCE_LOW - ATTENDANCE_CRITICAL)
                score += int(20 + frac * 20)
            elif attendance_pct < 90:
                score += 10  # Minor concern

        # Grade component (max 40 points)
        if grade_average is not None:
            if grade_average < GRADE_CRITICAL:
                score += 40
            elif grade_average < GRADE_LOW:
                frac = (GRADE_LOW - grade_average) / (GRADE_LOW - GRADE_CRITICAL)
                score += int(20 + frac * 20)
            elif grade_average < 60:
                score += 10

        # Transfer instability (max 20 points)
        if transfer_count >= 3:
            score += 20
        elif transfer_count >= 2:
            score += 10

        # If no data at all, assign a base risk for uncertainty
        if attendance_pct is None and grade_average is None:
            score = max(score, 15)

        return min(score, 100)

    @staticmethod
    def _score_to_level(score):
        """Convert a numeric risk score to a level string."""
        if score >= 60:
            return "High"
        elif score >= 30:
            return "Medium"
        return "Low"
