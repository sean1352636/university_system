"""Transfer Documents service.

Generates well-formatted plain-text transition reports for students being
transferred between education systems.  Queries the source system DB and
the academic_transfer_history table to compile a comprehensive report.
"""

import json
import sqlite3
import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Path / DB helpers
# ---------------------------------------------------------------------------

def _default_db_path(system):
    """Resolve the default database path for a given system."""
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

ALL_SYSTEMS = ["primary", "secondary", "college", "university"]


class TransferDocsService:
    """Generate transition reports for students."""

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
    # Student search (across all systems)
    # ------------------------------------------------------------------

    def search_students(self, name_query):
        """Search for students across all systems by name.

        Returns list of dicts: system, student_id, name, year_group, status.
        """
        results = []
        if not name_query or not name_query.strip():
            return results

        like = f"%{name_query.strip()}%"

        for system in ALL_SYSTEMS:
            conn = self._connect(system)
            if not conn:
                continue
            table = "pupils" if system == "primary" else "students"
            try:
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                ne = _name_expr(cols)
                if not ne:
                    continue

                id_col = "pupil_id" if (system == "primary" and "pupil_id" in cols) else (
                    "student_id" if "student_id" in cols else "id"
                )
                has_year = "year_group" in cols
                has_status = "status" in cols

                select = f"id, {id_col}, {ne} AS full_name"
                if has_year:
                    select += ", year_group"
                if has_status:
                    select += ", status"

                rows = conn.execute(
                    f"SELECT {select} FROM {table} WHERE {ne} LIKE ? LIMIT 50",
                    (like,),
                ).fetchall()

                for r in rows:
                    rk = r.keys()
                    results.append({
                        "system": system,
                        "id": r["id"],
                        "student_id": r[id_col] if id_col in rk else str(r["id"]),
                        "name": r["full_name"],
                        "year_group": r["year_group"] if has_year and "year_group" in rk else "",
                        "status": r["status"] if has_status and "status" in rk else "unknown",
                    })
            except Exception:
                pass
            finally:
                conn.close()

        return results

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self, student_name, source_system, student_id):
        """Generate a comprehensive plain-text transition report.

        Queries the source DB for student info, attendance, grades, and
        the academic_transfer_history table for prior transfer records.

        Returns the report as a string.
        """
        conn = self._connect(source_system)
        if not conn:
            return f"ERROR: Could not connect to {source_system} database."

        table = "pupils" if source_system == "primary" else "students"
        report_lines = []

        try:
            report_lines.append("=" * 70)
            report_lines.append("         STUDENT TRANSITION REPORT")
            report_lines.append("=" * 70)
            report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append(f"Source System: {SYSTEM_LABELS.get(source_system, source_system)}")
            report_lines.append("")

            # --- Section 1: Student Info ---
            student_info = self._get_student_detail(conn, table, source_system, student_id)
            report_lines.append("-" * 70)
            report_lines.append("SECTION 1: STUDENT INFORMATION")
            report_lines.append("-" * 70)
            if student_info:
                for key, val in student_info.items():
                    if val:
                        report_lines.append(f"  {key:<25} {val}")
            else:
                report_lines.append(f"  Student ID {student_id} not found in {source_system} database.")
            report_lines.append("")

            # --- Section 2: Academic Summary ---
            report_lines.append("-" * 70)
            report_lines.append("SECTION 2: ACADEMIC SUMMARY")
            report_lines.append("-" * 70)
            grades = self._get_grades(conn, source_system, student_id, student_info)
            if grades:
                for g in grades[:30]:
                    report_lines.append(f"  {g}")
            else:
                report_lines.append("  No academic records found.")
            report_lines.append("")

            # --- Section 3: Attendance Summary ---
            report_lines.append("-" * 70)
            report_lines.append("SECTION 3: ATTENDANCE SUMMARY")
            report_lines.append("-" * 70)
            attendance = self._get_attendance_summary(conn, source_system, student_id, student_info)
            if attendance:
                for key, val in attendance.items():
                    report_lines.append(f"  {key:<25} {val}")
            else:
                report_lines.append("  No attendance records found.")
            report_lines.append("")

            # --- Section 4: Special Notes (SEN) ---
            report_lines.append("-" * 70)
            report_lines.append("SECTION 4: SPECIAL NOTES")
            report_lines.append("-" * 70)
            sen_info = self._get_sen_info(conn, table, student_id, student_info)
            if sen_info:
                for note in sen_info:
                    report_lines.append(f"  {note}")
            else:
                report_lines.append("  No special educational needs records found.")
            report_lines.append("")

            # --- Section 5: Transfer History ---
            report_lines.append("-" * 70)
            report_lines.append("SECTION 5: TRANSFER DETAILS")
            report_lines.append("-" * 70)
            transfer_records = self._get_transfer_history(conn, source_system, student_id)
            if transfer_records:
                for rec in transfer_records:
                    report_lines.append(f"  From: {rec.get('source_system', 'N/A')}")
                    report_lines.append(f"  Source ID: {rec.get('source_student_id', 'N/A')}")
                    report_lines.append(f"  Transfer Date: {rec.get('transfer_date', rec.get('transferred_at', 'N/A'))}")
                    gs = rec.get("grades_summary", "")
                    if gs and gs != "[]":
                        try:
                            parsed = json.loads(gs) if isinstance(gs, str) else gs
                            if parsed:
                                report_lines.append(f"  Prior Grades: {len(parsed)} record(s)")
                        except (json.JSONDecodeError, TypeError):
                            pass
                    report_lines.append("")
            else:
                report_lines.append("  No prior transfer records.")
            report_lines.append("")

            report_lines.append("=" * 70)
            report_lines.append("                    END OF REPORT")
            report_lines.append("=" * 70)

        except Exception as exc:
            report_lines.append(f"\nERROR generating report: {exc}")
        finally:
            conn.close()

        return "\n".join(report_lines)

    def save_report(self, report_text, output_path):
        """Save a report string to a file.

        Args:
            report_text: The report content.
            output_path: Destination file path (str or Path).

        Returns:
            The absolute path of the saved file as a string.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report_text, encoding="utf-8")
        return str(path.resolve())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_student_detail(self, conn, table, system, student_id):
        """Retrieve detailed student information."""
        try:
            if not _table_exists(conn, table):
                return None
            cols = _get_columns(conn, table)
            id_col = "pupil_id" if (system == "primary" and "pupil_id" in cols) else (
                "student_id" if "student_id" in cols else "id"
            )

            row = conn.execute(
                f"SELECT * FROM {table} WHERE {id_col} = ?", (student_id,)
            ).fetchone()
            if not row:
                return None

            rk = row.keys()
            info = {}
            info["Student ID"] = str(row[id_col]) if id_col in rk else str(row["id"])

            # Name
            ne = _name_expr(cols)
            if ne:
                name_row = conn.execute(
                    f"SELECT {ne} AS full_name FROM {table} WHERE {id_col} = ?",
                    (student_id,),
                ).fetchone()
                if name_row:
                    info["Name"] = name_row["full_name"]

            for field, label in [
                ("date_of_birth", "Date of Birth"),
                ("dob", "Date of Birth"),
                ("year_group", "Year Group"),
                ("status", "Status"),
                ("email", "Email"),
                ("phone", "Phone"),
                ("address", "Address"),
                ("admission_date", "Admission Date"),
                ("enrollment_date", "Enrolment Date"),
                ("enrolled_date", "Enrolment Date"),
                ("gender", "Gender"),
                ("ethnicity", "Ethnicity"),
            ]:
                if field in rk and row[field] and label not in info:
                    info[label] = str(row[field])

            return info
        except Exception:
            return None

    def _get_grades(self, conn, system, student_id, student_info):
        """Return a list of grade summary strings."""
        lines = []
        row_id = student_info.get("row_id") if student_info else None

        try:
            if system == "primary":
                if _table_exists(conn, "assessments"):
                    rows = conn.execute(
                        "SELECT subject_code, level, score, term, academic_year "
                        "FROM assessments WHERE pupil_id = ? ORDER BY academic_year, term LIMIT 30",
                        (student_id,),
                    ).fetchall()
                    for r in rows:
                        parts = []
                        if r["subject_code"]:
                            parts.append(r["subject_code"])
                        if r["level"]:
                            parts.append(f"Level: {r['level']}")
                        if r["score"] is not None:
                            parts.append(f"Score: {r['score']}")
                        if r["term"]:
                            parts.append(f"Term: {r['term']}")
                        if r["academic_year"]:
                            parts.append(f"Year: {r['academic_year']}")
                        lines.append(" | ".join(parts))

            elif system == "secondary":
                if _table_exists(conn, "grades"):
                    # Need the row id
                    cols = _get_columns(conn, "students")
                    id_col = "student_id" if "student_id" in cols else "id"
                    stu_row = conn.execute(
                        f"SELECT id FROM students WHERE {id_col} = ?", (student_id,)
                    ).fetchone()
                    pk = stu_row["id"] if stu_row else student_id
                    rows = conn.execute(
                        "SELECT assessment_name, grade, score, term, academic_year "
                        "FROM grades WHERE student_id = ? ORDER BY academic_year, term LIMIT 30",
                        (pk,),
                    ).fetchall()
                    for r in rows:
                        rk = r.keys()
                        parts = []
                        if "assessment_name" in rk and r["assessment_name"]:
                            parts.append(r["assessment_name"])
                        if "grade" in rk and r["grade"]:
                            parts.append(f"Grade: {r['grade']}")
                        if "score" in rk and r["score"] is not None:
                            parts.append(f"Score: {r['score']}")
                        if "term" in rk and r["term"]:
                            parts.append(f"Term: {r['term']}")
                        if "academic_year" in rk and r["academic_year"]:
                            parts.append(f"Year: {r['academic_year']}")
                        lines.append(" | ".join(parts))

            elif system == "college":
                if _table_exists(conn, "grades"):
                    cols = _get_columns(conn, "students")
                    id_col = "student_id" if "student_id" in cols else "id"
                    stu_row = conn.execute(
                        f"SELECT id FROM students WHERE {id_col} = ?", (student_id,)
                    ).fetchone()
                    pk = stu_row["id"] if stu_row else student_id
                    rows = conn.execute(
                        "SELECT letter_grade, score, semester, grade_type "
                        "FROM grades WHERE student_id = ? ORDER BY semester LIMIT 30",
                        (pk,),
                    ).fetchall()
                    for r in rows:
                        rk = r.keys()
                        parts = []
                        if "grade_type" in rk and r["grade_type"]:
                            parts.append(r["grade_type"])
                        if "letter_grade" in rk and r["letter_grade"]:
                            parts.append(f"Grade: {r['letter_grade']}")
                        if "score" in rk and r["score"] is not None:
                            parts.append(f"Score: {r['score']}")
                        if "semester" in rk and r["semester"]:
                            parts.append(f"Semester: {r['semester']}")
                        lines.append(" | ".join(parts))

            elif system == "university":
                if _table_exists(conn, "grades"):
                    cols = _get_columns(conn, "students")
                    id_col = "student_id" if "student_id" in cols else "id"
                    stu_row = conn.execute(
                        f"SELECT id FROM students WHERE {id_col} = ?", (student_id,)
                    ).fetchone()
                    pk = stu_row["id"] if stu_row else student_id

                    grade_cols = _get_columns(conn, "grades")
                    select_parts = []
                    for c in ["grade", "letter_grade", "score", "semester", "module_code", "course_id"]:
                        if c in grade_cols:
                            select_parts.append(c)
                    if select_parts:
                        rows = conn.execute(
                            f"SELECT {', '.join(select_parts)} FROM grades "
                            f"WHERE student_id = ? LIMIT 30",
                            (pk,),
                        ).fetchall()
                        for r in rows:
                            rk = r.keys()
                            parts = [f"{k}: {r[k]}" for k in rk if r[k] is not None]
                            lines.append(" | ".join(parts))

        except Exception:
            pass

        return lines

    def _get_attendance_summary(self, conn, system, student_id, student_info):
        """Return attendance summary as a dict."""
        try:
            if system == "primary":
                if not _table_exists(conn, "attendance_records"):
                    return None
                total = conn.execute(
                    "SELECT COUNT(*) as c FROM attendance_records WHERE pupil_id = ?",
                    (student_id,),
                ).fetchone()["c"]
                present = conn.execute(
                    "SELECT COUNT(*) as c FROM attendance_records WHERE pupil_id = ? "
                    "AND status IN ('Present', 'Late')",
                    (student_id,),
                ).fetchone()["c"]
                return {
                    "Total Sessions": total,
                    "Present": present,
                    "Attendance %": f"{round(present / total * 100, 1)}%" if total > 0 else "N/A",
                }
            else:
                if not _table_exists(conn, "attendance_records"):
                    return None
                # Get row ID
                table = "students"
                cols = _get_columns(conn, table)
                id_col = "student_id" if "student_id" in cols else "id"
                stu_row = conn.execute(
                    f"SELECT id FROM {table} WHERE {id_col} = ?", (student_id,)
                ).fetchone()
                pk = stu_row["id"] if stu_row else student_id

                att_cols = _get_columns(conn, "attendance_records")
                att_id_col = "student_id" if "student_id" in att_cols else "pupil_id"

                total = conn.execute(
                    f"SELECT COUNT(*) as c FROM attendance_records WHERE {att_id_col} = ?",
                    (pk,),
                ).fetchone()["c"]
                present = conn.execute(
                    f"SELECT COUNT(*) as c FROM attendance_records WHERE {att_id_col} = ? "
                    f"AND LOWER(status) IN ('present', 'late')",
                    (pk,),
                ).fetchone()["c"]
                return {
                    "Total Sessions": total,
                    "Present": present,
                    "Attendance %": f"{round(present / total * 100, 1)}%" if total > 0 else "N/A",
                }
        except Exception:
            return None

    def _get_sen_info(self, conn, table, student_id, student_info):
        """Check for SEN/SEND status on the student record or a dedicated table."""
        notes = []
        try:
            cols = _get_columns(conn, table)
            id_col = "pupil_id" if ("pupil_id" in cols and table == "pupils") else (
                "student_id" if "student_id" in cols else "id"
            )

            row = conn.execute(
                f"SELECT * FROM {table} WHERE {id_col} = ?", (student_id,)
            ).fetchone()
            if row:
                rk = row.keys()
                for field in ("sen_status", "send_status", "send_provision", "sen_provision",
                              "ehcp", "special_needs", "medical_notes", "additional_needs"):
                    if field in rk and row[field]:
                        notes.append(f"{field}: {row[field]}")

            # Check for a dedicated SEN/SEND table
            for sen_table in ("sen_records", "send_records", "special_needs"):
                if _table_exists(conn, sen_table):
                    sen_cols = _get_columns(conn, sen_table)
                    sen_id = None
                    for candidate in ("student_id", "pupil_id"):
                        if candidate in sen_cols:
                            sen_id = candidate
                            break
                    if sen_id:
                        pk = student_id
                        if sen_id == "student_id" and table == "students":
                            stu_row = conn.execute(
                                f"SELECT id FROM {table} WHERE {id_col} = ?", (student_id,)
                            ).fetchone()
                            if stu_row:
                                pk = stu_row["id"]
                        rows = conn.execute(
                            f"SELECT * FROM {sen_table} WHERE {sen_id} = ? LIMIT 10",
                            (pk,),
                        ).fetchall()
                        for r in rows:
                            parts = [f"{k}: {r[k]}" for k in r.keys() if r[k] and k != sen_id]
                            if parts:
                                notes.append(" | ".join(parts))
        except Exception:
            pass
        return notes

    def _get_transfer_history(self, conn, system, student_id):
        """Fetch academic_transfer_history records."""
        try:
            if not _table_exists(conn, "academic_transfer_history"):
                return []
            cols = _get_columns(conn, "academic_transfer_history")
            id_col = None
            for candidate in ("student_id", "pupil_id", "source_student_id"):
                if candidate in cols:
                    id_col = candidate
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
