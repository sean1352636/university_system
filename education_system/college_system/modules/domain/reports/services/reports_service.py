"""Reports service for managing progress reports and report entries."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import ReportsError


class ReportsService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._migrated = False

    def _conn(self):
        conn = connect(self._db_path)
        if not self._migrated:
            self._ensure_columns(conn)
            self._migrated = True
        return conn

    def _ensure_columns(self, conn):
        """Ensure progress_reports and report_entries have the columns the service needs."""
        pr_cols = {row["name"] for row in conn.execute(
            "PRAGMA table_info(progress_reports)").fetchall()}
        re_cols = {row["name"] for row in conn.execute(
            "PRAGMA table_info(report_entries)").fetchall()}
        needs_pr = "title" not in pr_cols
        needs_re = "student_id" not in re_cols

        if not needs_pr and not needs_re:
            return

        conn.execute("PRAGMA foreign_keys = OFF")

        if needs_pr:
            # Recreate progress_reports with title, due_date and nullable student_id
            conn.execute("DROP TABLE IF EXISTS _pr_old")
            conn.execute("ALTER TABLE progress_reports RENAME TO _pr_old")
            conn.execute("""
                CREATE TABLE progress_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    student_id INTEGER,
                    report_type TEXT NOT NULL DEFAULT 'interim'
                        CHECK(report_type IN ('interim','full','final')),
                    academic_year TEXT,
                    term TEXT,
                    due_date TEXT,
                    overall_comment TEXT,
                    tutor_comment TEXT,
                    status TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft','published','sent')),
                    published_at TEXT,
                    created_by INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            """)
            conn.execute("""
                INSERT INTO progress_reports
                    (id, student_id, report_type, academic_year, term,
                     overall_comment, tutor_comment, status, published_at,
                     created_by, created_at)
                SELECT id, student_id, report_type, academic_year, term,
                       overall_comment, tutor_comment, status, published_at,
                       created_by, created_at
                FROM _pr_old
            """)
            conn.execute("DROP TABLE _pr_old")

        if needs_re:
            # Recreate report_entries with the columns the service needs
            conn.execute("DROP TABLE IF EXISTS _re_old")
            conn.execute("ALTER TABLE report_entries RENAME TO _re_old")
            conn.execute("""
                CREATE TABLE report_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL,
                    student_id INTEGER,
                    course_id INTEGER NOT NULL,
                    teacher_id INTEGER,
                    current_grade TEXT,
                    target_grade TEXT,
                    effort_grade TEXT,
                    attainment_grade TEXT,
                    attendance_pct REAL,
                    attendance_rate REAL,
                    comment TEXT,
                    teacher_comment TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (report_id) REFERENCES progress_reports(id),
                    FOREIGN KEY (course_id) REFERENCES courses(id)
                )
            """)
            conn.execute("""
                INSERT INTO report_entries
                    (id, report_id, course_id, effort_grade,
                     attainment_grade, target_grade, teacher_comment, attendance_rate)
                SELECT id, report_id, course_id, effort_grade,
                       attainment_grade, target_grade, teacher_comment, attendance_rate
                FROM _re_old
            """)
            conn.execute("DROP TABLE _re_old")

        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    # --- Progress Reports ---

    def create_report(self, title: str, report_type: str = "interim",
                       academic_year: str = None, term: str = None,
                       due_date: str = None, created_by: int = None,
                       student_id: int = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO progress_reports
                   (title, report_type, academic_year, term, due_date, created_by, student_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, report_type, academic_year, term, due_date, created_by, student_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM progress_reports WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ReportsError(f"Failed to create report: {e}")
        finally:
            conn.close()

    def list_reports(self, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM progress_reports WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM progress_reports ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_report(self, report_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM progress_reports WHERE id = ?", (report_id,)
            ).fetchone()
            if not row:
                raise ReportsError(f"Report {report_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_report_status(self, report_id: int, status: str) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE progress_reports SET status = ? WHERE id = ?",
                (status, report_id),
            )
            conn.commit()
            return self.get_report(report_id)
        except ReportsError:
            raise
        except Exception as e:
            raise ReportsError(f"Failed to update report: {e}")
        finally:
            conn.close()

    # --- Report Entries ---

    def add_entry(self, report_id: int, student_id: int, course_id: int,
                   teacher_id: int, current_grade: str = None,
                   target_grade: str = None, effort_grade: str = None,
                   attendance_pct: float = None, comment: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO report_entries
                   (report_id, student_id, course_id, teacher_id,
                    current_grade, target_grade, effort_grade, attendance_pct, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (report_id, student_id, course_id, teacher_id,
                 current_grade, target_grade, effort_grade, attendance_pct, comment),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM report_entries WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ReportsError(f"Failed to add report entry: {e}")
        finally:
            conn.close()

    def list_entries(self, report_id: int, student_id: int = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT re.*, s.first_name, s.last_name, c.title AS course_name
                       FROM report_entries re
                       LEFT JOIN students s ON re.student_id = s.id
                       LEFT JOIN courses c ON re.course_id = c.id
                       WHERE re.report_id = ?"""
            params = [report_id]
            if student_id:
                query += " AND re.student_id = ?"
                params.append(student_id)
            query += " ORDER BY s.last_name, c.title"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_entry(self, entry_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"current_grade", "target_grade", "effort_grade",
                        "attendance_pct", "comment"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise ReportsError("No valid fields to update")
            params.append(entry_id)
            conn.execute(f"UPDATE report_entries SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM report_entries WHERE id = ?", (entry_id,)).fetchone()
            return dict(row) if row else {}
        except ReportsError:
            raise
        except Exception as e:
            raise ReportsError(f"Failed to update entry: {e}")
        finally:
            conn.close()

    def get_student_report(self, report_id: int, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT re.*, c.title AS course_name FROM report_entries re
                   LEFT JOIN courses c ON re.course_id = c.id
                   WHERE re.report_id = ? AND re.student_id = ?
                   ORDER BY c.title""",
                (report_id, student_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
