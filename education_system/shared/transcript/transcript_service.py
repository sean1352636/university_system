"""Digital Transcript service layer.

Auto-generates a comprehensive transcript by querying all four system
databases: primary, secondary, college, and university.

Methods:
  generate_transcript(student_name) -> structured dict
  format_transcript(transcript_data) -> formatted text string
  save_transcript(text, output_path)
  get_transcript_summary(student_name) -> one-paragraph summary string
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from education_system.shared.database.paths import (
    SYSTEM_DB_PATHS as _DB_PATHS,
    SYSTEM_ORDER,
    SYSTEM_LABELS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _connect(system):
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


def _extract_name(row, columns):
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TranscriptService:
    """Generates comprehensive cross-system transcripts."""

    def search_students(self, name_query):
        """Search all 4 systems for students matching *name_query*.

        Returns a list of dicts: system, student_id, name, year_group, status.
        """
        results = []
        if not name_query or not name_query.strip():
            return results
        like = f"%{name_query.strip()}%"

        for sys_key in SYSTEM_ORDER:
            conn = _connect(sys_key)
            if not conn:
                continue
            try:
                table = "pupils" if sys_key == "primary" else "students"
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_expr = _name_search_expr(cols)
                if not name_expr:
                    continue
                id_col = "pupil_id" if (sys_key == "primary" and "pupil_id" in cols) else (
                    "student_id" if "student_id" in cols else "id"
                )
                status_col = "status" if "status" in cols else None
                year_col = "year_group" if "year_group" in cols else ("year" if "year" in cols else None)

                rows = conn.execute(
                    f"SELECT *, {name_expr} AS full_name FROM {table} "
                    f"WHERE {name_expr} LIKE ? LIMIT 50",
                    (like,),
                ).fetchall()
                for r in rows:
                    rk = r.keys()
                    results.append({
                        "system": sys_key,
                        "student_id": r[id_col] if id_col in rk else "",
                        "name": r["full_name"],
                        "year_group": r[year_col] if year_col and year_col in rk else "",
                        "status": r["status"] if status_col and "status" in rk else "unknown",
                    })
            except Exception:
                pass
            finally:
                conn.close()
        return results

    # -----------------------------------------------------------------------
    # Transcript generation
    # -----------------------------------------------------------------------

    def generate_transcript(self, student_name):
        """Build a structured transcript dict for *student_name*.

        The dict contains:
          personal_info, systems (list of per-system dicts with dates,
          grades, attendance, qualifications), transfers.
        """
        transcript = {
            "student_name": student_name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "personal_info": {},
            "systems": [],
            "transfers": [],
        }

        for sys_key in SYSTEM_ORDER:
            sys_data = self._collect_system_data(sys_key, student_name)
            if sys_data:
                transcript["systems"].append(sys_data)
                # Merge personal info (later systems override)
                if sys_data.get("personal_info"):
                    transcript["personal_info"].update(sys_data["personal_info"])
                if sys_data.get("transfers"):
                    transcript["transfers"].extend(sys_data["transfers"])

        return transcript

    def format_transcript(self, transcript_data):
        """Convert a transcript dict to a well-formatted text report."""
        lines = []
        lines.append("=" * 70)
        lines.append("DIGITAL TRANSCRIPT")
        lines.append("=" * 70)
        lines.append(f"Student: {transcript_data.get('student_name', 'N/A')}")
        lines.append(f"Generated: {transcript_data.get('generated_at', '')}")
        lines.append("")

        # Personal Information
        pi = transcript_data.get("personal_info", {})
        if pi:
            lines.append("-" * 40)
            lines.append("PERSONAL INFORMATION")
            lines.append("-" * 40)
            for key in ("name", "date_of_birth", "dob", "gender", "email", "address"):
                val = pi.get(key)
                if val:
                    lines.append(f"  {key.replace('_', ' ').title()}: {val}")
            lines.append("")

        # Educational History per system
        for sys_data in transcript_data.get("systems", []):
            sys_label = SYSTEM_LABELS.get(sys_data["system"], sys_data["system"].title())
            lines.append("-" * 40)
            lines.append(f"EDUCATIONAL HISTORY: {sys_label.upper()}")
            lines.append("-" * 40)

            if sys_data.get("enrolled_date"):
                lines.append(f"  Enrolled: {sys_data['enrolled_date']}")
            if sys_data.get("year_group"):
                lines.append(f"  Year/Group: {sys_data['year_group']}")
            if sys_data.get("status"):
                lines.append(f"  Status: {sys_data['status']}")
            lines.append("")

            # Grades
            grades = sys_data.get("grades", [])
            if grades:
                lines.append("  Courses / Subjects / Grades:")
                for g in grades:
                    parts = []
                    for k in ("subject_code", "course_code", "subject", "assessment_type",
                              "grade", "letter_grade", "score", "level", "outcome",
                              "academic_year", "term", "semester"):
                        v = g.get(k)
                        if v is not None and str(v).strip():
                            parts.append(f"{k}={v}")
                    lines.append(f"    {', '.join(parts)}")
                lines.append("")

            # Attendance
            att = sys_data.get("attendance", {})
            if att:
                lines.append("  Attendance:")
                total = att.get("total_sessions", 0)
                present = att.get("present", 0)
                pct = att.get("percentage", 0)
                lines.append(f"    Total sessions: {total}")
                lines.append(f"    Present: {present}")
                lines.append(f"    Attendance rate: {pct}%")
                lines.append("")

            # Qualifications
            quals = sys_data.get("qualifications", [])
            if quals:
                lines.append("  Qualifications & Awards:")
                for q in quals:
                    parts = [f"{k}={v}" for k, v in q.items() if v is not None and str(v).strip()]
                    lines.append(f"    {', '.join(parts)}")
                lines.append("")

        # Transfer History
        transfers = transcript_data.get("transfers", [])
        if transfers:
            lines.append("-" * 40)
            lines.append("TRANSFER HISTORY")
            lines.append("-" * 40)
            for t in transfers:
                parts = [f"{k}={v}" for k, v in t.items() if v is not None and str(v).strip()]
                lines.append(f"  {', '.join(parts)}")
            lines.append("")

        lines.append("=" * 70)
        lines.append("END OF TRANSCRIPT")
        lines.append("=" * 70)
        return "\n".join(lines)

    def save_transcript(self, text, output_path):
        """Save formatted transcript text to a file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def get_transcript_summary(self, student_name):
        """Return a brief one-paragraph summary of the student's transcript."""
        transcript = self.generate_transcript(student_name)
        systems = transcript.get("systems", [])
        if not systems:
            return f"No records found for {student_name} across any education system."

        parts = []
        parts.append(f"{student_name} has records in {len(systems)} education system(s)")

        system_names = []
        total_grades = 0
        for s in systems:
            system_names.append(SYSTEM_LABELS.get(s["system"], s["system"]))
            total_grades += len(s.get("grades", []))

        parts.append(f"({', '.join(system_names)})")

        if total_grades > 0:
            parts.append(f"with {total_grades} grade/assessment record(s) in total")

        # Best attendance
        best_att = 0
        for s in systems:
            pct = s.get("attendance", {}).get("percentage", 0)
            if pct > best_att:
                best_att = pct
        if best_att > 0:
            parts.append(f"and a best attendance rate of {best_att}%")

        transfers = transcript.get("transfers", [])
        if transfers:
            parts.append(f"with {len(transfers)} recorded transfer(s)")

        return " ".join(parts) + "."

    # -----------------------------------------------------------------------
    # Per-system data collection
    # -----------------------------------------------------------------------

    def _collect_system_data(self, system, student_name):
        """Collect all transcript data from a single system."""
        conn = _connect(system)
        if not conn:
            return None
        try:
            if system == "primary":
                return self._collect_primary(conn, student_name)
            elif system == "secondary":
                return self._collect_secondary(conn, student_name)
            elif system == "college":
                return self._collect_college(conn, student_name)
            elif system == "university":
                return self._collect_university(conn, student_name)
        except Exception:
            return None
        finally:
            conn.close()

    # -- Primary -------------------------------------------------------------

    def _collect_primary(self, conn, student_name):
        if not _table_exists(conn, "pupils"):
            return None
        cols = _get_columns(conn, "pupils")
        name_expr = _name_search_expr(cols)
        if not name_expr:
            return None

        row = conn.execute(
            f"SELECT * FROM pupils WHERE {name_expr} LIKE ? LIMIT 1",
            (f"%{student_name}%",),
        ).fetchone()
        if not row:
            return None

        rk = row.keys()
        id_col = "pupil_id" if "pupil_id" in rk else "id"
        pid = row[id_col]

        data = {
            "system": "primary",
            "student_id": pid,
            "name": _extract_name(row, cols),
            "year_group": row["year_group"] if "year_group" in rk else "",
            "status": row["status"] if "status" in rk else "unknown",
            "enrolled_date": "",
            "personal_info": {},
            "grades": [],
            "attendance": {},
            "qualifications": [],
            "transfers": [],
        }

        for col in ("admission_date", "enrollment_date", "enrolled_date"):
            if col in rk and row[col]:
                data["enrolled_date"] = row[col]
                break

        # Personal info
        for col in ("date_of_birth", "dob", "gender", "email", "address"):
            if col in rk and row[col]:
                data["personal_info"][col] = row[col]
        data["personal_info"]["name"] = data["name"]

        # Assessments
        if _table_exists(conn, "assessments"):
            try:
                rows = conn.execute(
                    "SELECT * FROM assessments WHERE pupil_id = ? ORDER BY academic_year, term",
                    (pid,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # SATs
        if _table_exists(conn, "sats_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM sats_results WHERE pupil_id = ? ORDER BY academic_year",
                    (pid,),
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    data["grades"].append(d)
                    # SATs with outcome are qualifications
                    if d.get("outcome"):
                        data["qualifications"].append({
                            "type": "SATs",
                            "subject": d.get("subject", ""),
                            "outcome": d["outcome"],
                            "academic_year": d.get("academic_year", ""),
                        })
            except Exception:
                pass

        # Phonics
        if _table_exists(conn, "phonics_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM phonics_results WHERE pupil_id = ? ORDER BY academic_year",
                    (pid,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Attendance
        if _table_exists(conn, "attendance_records"):
            try:
                total = conn.execute(
                    "SELECT COUNT(*) AS c FROM attendance_records WHERE pupil_id = ?", (pid,)
                ).fetchone()["c"]
                present = conn.execute(
                    "SELECT COUNT(*) AS c FROM attendance_records WHERE pupil_id = ? "
                    "AND LOWER(status) IN ('present','late')", (pid,)
                ).fetchone()["c"]
                data["attendance"] = {
                    "total_sessions": total,
                    "present": present,
                    "percentage": round(present / total * 100, 1) if total > 0 else 0,
                }
            except Exception:
                pass

        # Transfers
        if _table_exists(conn, "academic_transfer_history"):
            try:
                id_match = None
                th_cols = _get_columns(conn, "academic_transfer_history")
                for cand in ("pupil_id", "student_id", "source_student_id"):
                    if cand in th_cols:
                        id_match = cand
                        break
                if id_match:
                    rows = conn.execute(
                        f"SELECT * FROM academic_transfer_history WHERE {id_match} = ?", (pid,)
                    ).fetchall()
                    data["transfers"] = [dict(r) for r in rows]
            except Exception:
                pass

        return data

    # -- Secondary -----------------------------------------------------------

    def _collect_secondary(self, conn, student_name):
        if not _table_exists(conn, "students"):
            return None
        cols = _get_columns(conn, "students")
        name_expr = _name_search_expr(cols)
        if not name_expr:
            return None

        row = conn.execute(
            f"SELECT * FROM students WHERE {name_expr} LIKE ? LIMIT 1",
            (f"%{student_name}%",),
        ).fetchone()
        if not row:
            return None

        rk = row.keys()
        sid_col = "student_id" if "student_id" in rk else "id"
        sid = row[sid_col]
        pk = row["id"] if "id" in rk else sid

        data = {
            "system": "secondary",
            "student_id": sid,
            "name": _extract_name(row, cols),
            "year_group": row["year_group"] if "year_group" in rk else "",
            "status": row["status"] if "status" in rk else "unknown",
            "enrolled_date": "",
            "personal_info": {},
            "grades": [],
            "attendance": {},
            "qualifications": [],
            "transfers": [],
        }

        for col in ("admission_date", "enrollment_date", "enrolled_date"):
            if col in rk and row[col]:
                data["enrolled_date"] = row[col]
                break

        for col in ("date_of_birth", "dob", "gender", "email", "address"):
            if col in rk and row[col]:
                data["personal_info"][col] = row[col]
        data["personal_info"]["name"] = data["name"]

        # Grades
        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY academic_year, term",
                    (pk,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Exam results
        if _table_exists(conn, "exam_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM exam_results WHERE student_id = ? ORDER BY rowid",
                    (pk,),
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    data["grades"].append(d)
                    if d.get("grade"):
                        data["qualifications"].append({
                            "type": "Exam",
                            "grade": d["grade"],
                            "marks": d.get("marks_obtained", ""),
                        })
            except Exception:
                pass

        # Attendance
        if _table_exists(conn, "attendance_records"):
            try:
                total = conn.execute(
                    "SELECT COUNT(*) AS c FROM attendance_records WHERE student_id = ?", (pk,)
                ).fetchone()["c"]
                present = conn.execute(
                    "SELECT COUNT(*) AS c FROM attendance_records WHERE student_id = ? "
                    "AND LOWER(status) IN ('present','late')", (pk,)
                ).fetchone()["c"]
                data["attendance"] = {
                    "total_sessions": total,
                    "present": present,
                    "percentage": round(present / total * 100, 1) if total > 0 else 0,
                }
            except Exception:
                pass

        # Transfers
        if _table_exists(conn, "academic_transfer_history"):
            try:
                th_cols = _get_columns(conn, "academic_transfer_history")
                id_match = None
                for cand in ("student_id", "source_student_id"):
                    if cand in th_cols:
                        id_match = cand
                        break
                if id_match:
                    rows = conn.execute(
                        f"SELECT * FROM academic_transfer_history WHERE {id_match} = ?", (sid,)
                    ).fetchall()
                    data["transfers"] = [dict(r) for r in rows]
            except Exception:
                pass

        return data

    # -- College -------------------------------------------------------------

    def _collect_college(self, conn, student_name):
        if not _table_exists(conn, "students"):
            return None
        cols = _get_columns(conn, "students")
        name_expr = _name_search_expr(cols)
        if not name_expr:
            return None

        row = conn.execute(
            f"SELECT * FROM students WHERE {name_expr} LIKE ? LIMIT 1",
            (f"%{student_name}%",),
        ).fetchone()
        if not row:
            return None

        rk = row.keys()
        sid_col = "student_id" if "student_id" in rk else "id"
        sid = row[sid_col]
        pk = row["id"] if "id" in rk else sid

        data = {
            "system": "college",
            "student_id": sid,
            "name": _extract_name(row, cols),
            "year_group": row["year_group"] if "year_group" in rk else "",
            "status": row["status"] if "status" in rk else "unknown",
            "enrolled_date": "",
            "personal_info": {},
            "grades": [],
            "attendance": {},
            "qualifications": [],
            "transfers": [],
        }

        for col in ("enrollment_date", "enrolled_date", "admission_date"):
            if col in rk and row[col]:
                data["enrolled_date"] = row[col]
                break

        for col in ("date_of_birth", "dob", "gender", "email", "address"):
            if col in rk and row[col]:
                data["personal_info"][col] = row[col]
        data["personal_info"]["name"] = data["name"]

        # Grades
        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY semester, term",
                    (pk,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Attendance (two-table join)
        if _table_exists(conn, "attendance_records"):
            try:
                join = ""
                if _table_exists(conn, "attendance_sessions"):
                    join = "JOIN attendance_sessions s ON ar.session_id = s.id"
                total = conn.execute(
                    f"SELECT COUNT(*) AS c FROM attendance_records ar {join} WHERE ar.student_id = ?",
                    (pk,),
                ).fetchone()["c"]
                present = conn.execute(
                    f"SELECT COUNT(*) AS c FROM attendance_records ar {join} "
                    f"WHERE ar.student_id = ? AND LOWER(ar.status) IN ('present','late')",
                    (pk,),
                ).fetchone()["c"]
                data["attendance"] = {
                    "total_sessions": total,
                    "present": present,
                    "percentage": round(present / total * 100, 1) if total > 0 else 0,
                }
            except Exception:
                pass

        # Transfers
        if _table_exists(conn, "academic_transfer_history"):
            try:
                th_cols = _get_columns(conn, "academic_transfer_history")
                id_match = None
                for cand in ("student_id", "source_student_id"):
                    if cand in th_cols:
                        id_match = cand
                        break
                if id_match:
                    rows = conn.execute(
                        f"SELECT * FROM academic_transfer_history WHERE {id_match} = ?", (sid,)
                    ).fetchall()
                    data["transfers"] = [dict(r) for r in rows]
            except Exception:
                pass

        return data

    # -- University ----------------------------------------------------------

    def _collect_university(self, conn, student_name):
        if not _table_exists(conn, "students"):
            return None
        cols = _get_columns(conn, "students")
        name_expr = _name_search_expr(cols)
        if not name_expr:
            return None

        row = conn.execute(
            f"SELECT * FROM students WHERE {name_expr} LIKE ? LIMIT 1",
            (f"%{student_name}%",),
        ).fetchone()
        if not row:
            return None

        rk = row.keys()
        sid_col = "student_id" if "student_id" in rk else "id"
        sid = row[sid_col]
        pk = row["id"] if "id" in rk else sid
        year_col = "year_group" if "year_group" in rk else ("year" if "year" in rk else None)

        data = {
            "system": "university",
            "student_id": sid,
            "name": _extract_name(row, cols),
            "year_group": row[year_col] if year_col else "",
            "status": row["status"] if "status" in rk else "unknown",
            "enrolled_date": "",
            "personal_info": {},
            "grades": [],
            "attendance": {},
            "qualifications": [],
            "transfers": [],
        }

        for col in ("enrollment_date", "enrolled_date", "admission_date"):
            if col in rk and row[col]:
                data["enrolled_date"] = row[col]
                break

        for col in ("date_of_birth", "dob", "gender", "email", "address", "programme", "department"):
            if col in rk and row[col]:
                data["personal_info"][col] = row[col]
        data["personal_info"]["name"] = data["name"]

        # Grades
        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY rowid",
                    (pk,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Attendance — university uses "attendance", others use "attendance_records"
        att_table = None
        for _tbl in ("attendance", "attendance_records"):
            if _table_exists(conn, _tbl):
                att_table = _tbl
                break
        if att_table:
            try:
                total = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {att_table} WHERE student_id = ?", (pk,)
                ).fetchone()["c"]
                present = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {att_table} WHERE student_id = ? "
                    "AND LOWER(status) IN ('present','late')", (pk,)
                ).fetchone()["c"]
                data["attendance"] = {
                    "total_sessions": total,
                    "present": present,
                    "percentage": round(present / total * 100, 1) if total > 0 else 0,
                }
            except Exception:
                pass

        # Transfers
        if _table_exists(conn, "academic_transfer_history"):
            try:
                th_cols = _get_columns(conn, "academic_transfer_history")
                id_match = None
                for cand in ("student_id", "source_student_id"):
                    if cand in th_cols:
                        id_match = cand
                        break
                if id_match:
                    rows = conn.execute(
                        f"SELECT * FROM academic_transfer_history WHERE {id_match} = ?", (sid,)
                    ).fetchall()
                    data["transfers"] = [dict(r) for r in rows]
            except Exception:
                pass

        return data
