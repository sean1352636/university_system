"""FtP service layer — pure data access, no Tk.

Extracted from ``fitness_to_practise.py`` (8.117.141). The original
``FtPDataAccess`` class lives here unchanged so existing imports
``from ...fitness_to_practise import FtPDataAccess`` continue to
resolve via the shim re-export.
"""

from __future__ import annotations

import sqlite3

from education_system.post_18.university_system.core.paths import (
    DEFAULT_DB_PATH,
)
from education_system.post_18.university_system.modules.domain.operations.legal.disciplinary.fitness_to_practise._db_init import (
    ensure_ftp_schema,
)


def current_username() -> str:
    """Best-effort lookup of the active user, falling back to "Admin"."""
    try:
        from education_system.post_18.university_system.infrastructure.auth import (
            get_global_auth,
        )
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            user = ga.current_user
            return (user.get('username')
                    or user.get('email')
                    or str(user.get('id') or 'Admin'))
    except Exception:
        pass
    return 'Admin'


class FtPDataAccess:
    """Thin wrapper around the FtP tables on the central DB.

    Schema lives in ``_db_init.ensure_ftp_schema``; this class only
    does reads/writes against it. Returns plain tuples so the Tk
    Treeviews can ingest results directly without a row-to-record
    translation step."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        ensure_ftp_schema(self.db_path)

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.execute("PRAGMA foreign_keys = ON")
        return c

    # ---- Students (read-only projection) ----
    def search_students(self, q):
        conn = self._conn()
        try:
            like = f"%{q}%"
            cur = conn.execute(
                "SELECT student_id, first_name, last_name, "
                "       COALESCE(course,'') FROM students "
                "WHERE student_id LIKE ? OR first_name LIKE ? "
                "   OR last_name LIKE ? OR course LIKE ? "
                "ORDER BY last_name LIMIT 200",
                (like, like, like, like))
            return cur.fetchall()
        finally:
            conn.close()

    # ---- Cases ----
    def list_cases(self, stage=None, regulator=None, search=None):
        sql = (
            "SELECT c.case_id, c.student_id, "
            "       COALESCE(s.first_name||' '||s.last_name, c.student_id), "
            "       c.programme, c.regulator, c.stage, c.risk_level, "
            "       c.case_officer, c.date_opened "
            "FROM ftp_cases c "
            "LEFT JOIN students s ON s.student_id = c.student_id "
            "WHERE 1=1 "
        )
        params = []
        if stage and stage != 'All':
            sql += "AND c.stage = ? "
            params.append(stage)
        if regulator and regulator != 'All':
            sql += "AND c.regulator = ? "
            params.append(regulator)
        if search:
            sql += ("AND (c.student_id LIKE ? OR s.first_name LIKE ? "
                    "  OR s.last_name LIKE ? OR c.programme LIKE ?) ")
            like = f"%{search}%"
            params.extend([like, like, like, like])
        sql += "ORDER BY c.updated_at DESC"
        conn = self._conn()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_case(self, case_id):
        conn = self._conn()
        try:
            cur = conn.execute(
                "SELECT case_id, student_id, programme, regulator, "
                "       registration_no, stage, risk_level, interim_order, "
                "       placement_status, date_opened, date_closed, "
                "       case_officer, panel_chair, summary, "
                "       source_record_id "
                "FROM ftp_cases WHERE case_id = ?", (case_id,))
            return cur.fetchone()
        finally:
            conn.close()

    def create_case(self, data):
        """data: dict with keys matching the column names."""
        cols = ('student_id', 'programme', 'regulator', 'registration_no',
                'stage', 'risk_level', 'interim_order', 'placement_status',
                'case_officer', 'panel_chair', 'summary', 'source_record_id')
        values = [data.get(k) for k in cols]
        placeholders = ", ".join("?" * len(cols))
        conn = self._conn()
        try:
            cur = conn.execute(
                f"INSERT INTO ftp_cases ({', '.join(cols)}) "
                f"VALUES ({placeholders})", values)
            case_id = cur.lastrowid
            conn.execute(
                "INSERT INTO ftp_events (case_id, event_type, notes, actor) "
                "VALUES (?, 'Case Opened', ?, ?)",
                (case_id, f"Stage: {data.get('stage')}", current_username()))
            conn.commit()
            return case_id
        finally:
            conn.close()

    def update_stage(self, case_id, new_stage, notes=''):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE ftp_cases SET stage = ? WHERE case_id = ?",
                (new_stage, case_id))
            conn.execute(
                "INSERT INTO ftp_events (case_id, event_type, notes, actor) "
                "VALUES (?, 'Stage Change', ?, ?)",
                (case_id, f"→ {new_stage}. {notes}".strip(),
                 current_username()))
            if new_stage == 'Closed':
                conn.execute(
                    "UPDATE ftp_cases SET date_closed = CURRENT_TIMESTAMP "
                    "WHERE case_id = ? AND date_closed IS NULL", (case_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_case(self, case_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM ftp_cases WHERE case_id = ?",
                         (case_id,))
            conn.commit()
        finally:
            conn.close()

    # ---- Concerns ----
    def list_concerns(self, case_id):
        conn = self._conn()
        try:
            return conn.execute(
                "SELECT concern_id, category, description, raised_by, "
                "       raised_at FROM ftp_concerns "
                "WHERE case_id = ? ORDER BY raised_at DESC",
                (case_id,)).fetchall()
        finally:
            conn.close()

    def add_concern(self, case_id, category, description):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO ftp_concerns "
                "(case_id, category, description, raised_by) "
                "VALUES (?, ?, ?, ?)",
                (case_id, category, description, current_username()))
            conn.execute(
                "INSERT INTO ftp_events (case_id, event_type, notes, actor) "
                "VALUES (?, 'Concern Added', ?, ?)",
                (case_id, f"{category}: {description[:80]}",
                 current_username()))
            conn.commit()
        finally:
            conn.close()

    # ---- Events ----
    def list_events(self, case_id):
        conn = self._conn()
        try:
            return conn.execute(
                "SELECT event_id, event_type, notes, actor, occurred_at "
                "FROM ftp_events WHERE case_id = ? "
                "ORDER BY occurred_at DESC", (case_id,)).fetchall()
        finally:
            conn.close()

    def add_event(self, case_id, event_type, notes):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO ftp_events (case_id, event_type, notes, actor) "
                "VALUES (?, ?, ?, ?)",
                (case_id, event_type, notes, current_username()))
            conn.commit()
        finally:
            conn.close()

    # ---- Outcomes ----
    def list_outcomes(self, case_id):
        conn = self._conn()
        try:
            return conn.execute(
                "SELECT outcome_id, outcome, sanction, conditions, "
                "       review_date, decided_by, decided_at "
                "FROM ftp_outcomes WHERE case_id = ? "
                "ORDER BY decided_at DESC", (case_id,)).fetchall()
        finally:
            conn.close()

    def add_outcome(self, case_id, outcome, sanction, conditions, review):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO ftp_outcomes "
                "(case_id, outcome, sanction, conditions, review_date, "
                " decided_by) VALUES (?, ?, ?, ?, ?, ?)",
                (case_id, outcome, sanction, conditions, review,
                 current_username()))
            conn.execute(
                "INSERT INTO ftp_events (case_id, event_type, notes, actor) "
                "VALUES (?, 'Outcome Recorded', ?, ?)",
                (case_id, outcome, current_username()))
            conn.commit()
        finally:
            conn.close()

    # ---- Dashboard stats ----
    def stats(self):
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*), "
                "  SUM(CASE WHEN stage NOT IN ('Closed') THEN 1 ELSE 0 END),"
                "  SUM(CASE WHEN stage='At Hearing' THEN 1 ELSE 0 END),"
                "  SUM(CASE WHEN risk_level='High' THEN 1 ELSE 0 END) "
                "FROM ftp_cases").fetchone()
            return {
                'total':   row[0] or 0,
                'open':    row[1] or 0,
                'hearing': row[2] or 0,
                'high':    row[3] or 0,
            }
        finally:
            conn.close()
