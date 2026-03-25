"""Transcript generation service.

Provides per-system transcript generation that queries the local database
for grades/results and builds a structured transcript.  Works with any of
the four subsystems (primary, secondary, college, university) by accepting
a ``db_path`` and using the standard ``connect()`` helper.

Usage::

    svc = TranscriptService(db_path)
    data = svc.generate_transcript("STU001", academic_year="2025/26")
    html = svc.export_transcript_html("STU001")
    svc.export_transcript_csv("STU001", "/tmp/transcript.csv")
"""

import csv
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from string import Template

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# ---------------------------------------------------------------------------
# Institution labels (fallback when DB doesn't provide one)
# ---------------------------------------------------------------------------
_INSTITUTIONS = {
    "primary_school": "Primary School",
    "secondary_school": "Secondary School",
    "sixthform": "Sixth Form College",
    "student_records": "University",
}


def _detect_institution(db_path: str | None) -> str:
    """Best-effort institution name from the database path."""
    if not db_path:
        return "Education Institution"
    p = str(db_path).lower()
    for key, label in _INSTITUTIONS.items():
        if key in p:
            return label
    return "Education Institution"


def _connect(db_path: str | None):
    """Open a connection to the given SQLite database."""
    path = db_path or ":memory:"
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


class TranscriptService:
    """Generates academic transcripts from a single subsystem database."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return _connect(self._db_path)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def generate_transcript(self, student_id, academic_year=None) -> dict:
        """Query grades/results and build a transcript data structure.

        Returns::

            {
                "student_name": str,
                "student_id": str,
                "institution": str,
                "academic_year": str,
                "subjects": [{"name", "grade", "credits", "date"}, ...],
                "gpa": float | str,
                "generated_at": str,
                "transcript_id": str,
            }
        """
        conn = self._conn()
        try:
            student_name, sid_display = self._resolve_student(conn, student_id)
            subjects = self._collect_subjects(conn, student_id, academic_year)
            gpa = self._compute_gpa(subjects)
            transcript_id = f"TR-{uuid.uuid4().hex[:12].upper()}"

            transcript = {
                "student_name": student_name,
                "student_id": sid_display,
                "institution": _detect_institution(self._db_path),
                "academic_year": academic_year or "All Years",
                "subjects": subjects,
                "gpa": gpa,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "transcript_id": transcript_id,
            }

            # Log the request if the table exists
            self._log_request(conn, student_id, academic_year, transcript_id)

            return transcript
        finally:
            conn.close()

    def export_transcript_html(self, student_id, academic_year=None) -> str:
        """Render transcript as an HTML string suitable for printing/PDF."""
        data = self.generate_transcript(student_id, academic_year)
        return self._render_html(data)

    def export_transcript_csv(self, student_id, filepath, academic_year=None):
        """Export transcript subjects to a CSV file."""
        data = self.generate_transcript(student_id, academic_year)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Student Name", "Student ID", "Institution",
                             "Academic Year", "Generated"])
            writer.writerow([data["student_name"], data["student_id"],
                             data["institution"], data["academic_year"],
                             data["generated_at"]])
            writer.writerow([])
            writer.writerow(["Subject", "Grade", "Credits", "Date"])
            for s in data["subjects"]:
                writer.writerow([s["name"], s["grade"], s["credits"], s["date"]])
            writer.writerow([])
            writer.writerow(["GPA / Average", data["gpa"]])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_student(self, conn, student_id) -> tuple[str, str]:
        """Look up student name and display ID from various table schemas."""
        # Try 'students' table first, then 'pupils' (primary)
        for table in ("students", "pupils"):
            if not _table_exists(conn, table):
                continue
            cols = _get_columns(conn, table)
            # Try matching by student_id/pupil_id text column, then by integer id
            id_col = None
            for candidate in ("student_id", "pupil_id"):
                if candidate in cols:
                    id_col = candidate
                    break
            if id_col:
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE {id_col} = ? LIMIT 1",
                    (student_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE id = ? LIMIT 1",
                    (student_id,),
                ).fetchone()
            if row:
                rk = row.keys()
                name_parts = []
                for fn in ("first_name", "forename"):
                    if fn in rk and row[fn]:
                        name_parts.append(row[fn])
                        break
                for ln in ("last_name", "surname"):
                    if ln in rk and row[ln]:
                        name_parts.append(row[ln])
                        break
                if "full_name" in rk and row["full_name"]:
                    name = row["full_name"]
                elif "name" in rk and row["name"]:
                    name = row["name"]
                elif name_parts:
                    name = " ".join(name_parts)
                else:
                    name = str(student_id)

                display_id = row[id_col] if id_col and id_col in rk else str(row["id"])
                return name, str(display_id)

        return str(student_id), str(student_id)

    def _collect_subjects(self, conn, student_id, academic_year=None) -> list[dict]:
        """Gather subject/grade records from the grades or assessments table."""
        subjects = []

        # Resolve the integer PK if needed
        pk = self._resolve_pk(conn, student_id)

        # Try grades table (secondary, college, university)
        if _table_exists(conn, "grades"):
            cols = _get_columns(conn, "grades")
            sql = "SELECT g.* FROM grades g WHERE g.student_id = ?"
            params: list = [pk]
            if academic_year and "academic_year" in cols:
                sql += " AND g.academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY rowid"
            try:
                rows = conn.execute(sql, params).fetchall()
                for r in rows:
                    rk = r.keys()
                    # Try to get subject name
                    subject_name = self._subject_name(conn, r, rk)
                    grade = ""
                    for gc in ("grade", "letter_grade", "score", "level"):
                        if gc in rk and r[gc] is not None:
                            grade = str(r[gc])
                            break
                    credits = str(r["credits"]) if "credits" in rk and r["credits"] else ""
                    date = ""
                    for dc in ("graded_at", "date", "created_at", "academic_year"):
                        if dc in rk and r[dc]:
                            date = str(r[dc])
                            break
                    subjects.append({
                        "name": subject_name,
                        "grade": grade,
                        "credits": credits,
                        "date": date,
                    })
            except Exception as e:
                logger.debug("Error collecting grades: %s", e)

        # Try assessments table (primary)
        if _table_exists(conn, "assessments"):
            cols = _get_columns(conn, "assessments")
            id_col = "pupil_id" if "pupil_id" in cols else "student_id"
            sql = f"SELECT * FROM assessments WHERE {id_col} = ?"
            params = [pk]
            if academic_year and "academic_year" in cols:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY rowid"
            try:
                rows = conn.execute(sql, params).fetchall()
                for r in rows:
                    rk = r.keys()
                    name = r["subject_code"] if "subject_code" in rk else ""
                    grade = ""
                    for gc in ("level", "grade", "score"):
                        if gc in rk and r[gc] is not None:
                            grade = str(r[gc])
                            break
                    credits = str(r["score"]) if "score" in rk and r["score"] else ""
                    date = ""
                    for dc in ("created_at", "academic_year"):
                        if dc in rk and r[dc]:
                            date = str(r[dc])
                            break
                    subjects.append({
                        "name": name,
                        "grade": grade,
                        "credits": credits,
                        "date": date,
                    })
            except Exception as e:
                logger.debug("Error collecting assessments: %s", e)

        return subjects

    def _resolve_pk(self, conn, student_id):
        """Resolve student_id text to integer PK."""
        for table in ("students", "pupils"):
            if not _table_exists(conn, table):
                continue
            cols = _get_columns(conn, table)
            for id_col in ("student_id", "pupil_id"):
                if id_col in cols:
                    row = conn.execute(
                        f"SELECT id FROM {table} WHERE {id_col} = ? LIMIT 1",
                        (student_id,),
                    ).fetchone()
                    if row:
                        return row["id"]
        # Fallback: assume it's already a PK
        try:
            return int(student_id)
        except (ValueError, TypeError):
            return student_id

    def _subject_name(self, conn, grade_row, rk) -> str:
        """Try to resolve a human-readable subject name."""
        # Direct column on grades
        for col in ("subject_name", "course_name", "subject", "course_code", "subject_code"):
            if col in rk and grade_row[col]:
                return str(grade_row[col])
        # Join via subject_id or course_id
        if "subject_id" in rk and grade_row["subject_id"]:
            for table, name_col in [("subjects", "title"), ("subjects", "subject_code"),
                                     ("courses", "course_name"), ("courses", "title")]:
                if _table_exists(conn, table) and name_col in _get_columns(conn, table):
                    row = conn.execute(
                        f"SELECT {name_col} FROM {table} WHERE id = ? LIMIT 1",
                        (grade_row["subject_id"],),
                    ).fetchone()
                    if row and row[0]:
                        return str(row[0])
        if "course_id" in rk and grade_row["course_id"]:
            for table in ("courses",):
                if _table_exists(conn, table):
                    for nc in ("course_name", "title", "name"):
                        cols = _get_columns(conn, table)
                        if nc in cols:
                            row = conn.execute(
                                f"SELECT {nc} FROM {table} WHERE id = ? LIMIT 1",
                                (grade_row["course_id"],),
                            ).fetchone()
                            if row and row[0]:
                                return str(row[0])
        return "Unknown Subject"

    def _compute_gpa(self, subjects: list[dict]) -> str:
        """Compute a simple average from numeric grades."""
        scores = []
        for s in subjects:
            try:
                scores.append(float(s["grade"]))
            except (ValueError, TypeError):
                continue
        if scores:
            avg = sum(scores) / len(scores)
            return f"{avg:.2f}"
        return "N/A"

    def _log_request(self, conn, student_id, academic_year, transcript_id):
        """Log the transcript request if the transcript_requests table exists."""
        if not _table_exists(conn, "transcript_requests"):
            return
        try:
            conn.execute(
                """INSERT INTO transcript_requests
                   (student_id, requested_by, academic_year, status, generated_at)
                   VALUES (?, ?, ?, 'completed', datetime('now'))""",
                (student_id, "system", academic_year or "All"),
            )
            conn.commit()
        except Exception as e:
            logger.debug("Could not log transcript request: %s", e)

    def _render_html(self, data: dict) -> str:
        """Render transcript data using the HTML template."""
        template_path = _TEMPLATE_DIR / "transcript_template.html"
        tpl_str = template_path.read_text(encoding="utf-8")

        # Build subjects table HTML
        if data["subjects"]:
            rows_html = []
            for s in data["subjects"]:
                rows_html.append(
                    f"  <tr>"
                    f"<td>{_esc(s['name'])}</td>"
                    f"<td class='grade-cell'>{_esc(s['grade'])}</td>"
                    f"<td>{_esc(s['credits'])}</td>"
                    f"<td>{_esc(s['date'])}</td>"
                    f"</tr>"
                )
            subjects_table = (
                "<table>\n"
                "<thead><tr>"
                "<th>Subject / Module</th>"
                "<th>Grade</th>"
                "<th>Credits</th>"
                "<th>Date</th>"
                "</tr></thead>\n"
                "<tbody>\n" + "\n".join(rows_html) + "\n</tbody>\n</table>"
            )
        else:
            subjects_table = '<div class="no-records">No academic records found.</div>'

        tpl = Template(tpl_str)
        return tpl.safe_substitute(
            institution=_esc(data["institution"]),
            student_name=_esc(data["student_name"]),
            student_id=_esc(data["student_id"]),
            academic_year=_esc(data["academic_year"]),
            generated_at=_esc(data["generated_at"]),
            transcript_id=_esc(data.get("transcript_id", "")),
            subjects_table=subjects_table,
            gpa=_esc(str(data["gpa"])),
            total_subjects=str(len(data["subjects"])),
        )


def _esc(value: str) -> str:
    """Basic HTML escaping."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
