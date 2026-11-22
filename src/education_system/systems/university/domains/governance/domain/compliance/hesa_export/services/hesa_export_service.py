"""HESA data export service for statutory XML returns."""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction


class HESAExportService:
    """Service for managing HESA statutory data returns."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hesa_returns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year TEXT NOT NULL,
                    return_type TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    submitted_at TEXT,
                    xml_data TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hesa_field_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    return_type TEXT NOT NULL,
                    hesa_field TEXT NOT NULL,
                    local_field TEXT NOT NULL,
                    transform_rule TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hesa_submission_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    return_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    performed_by TEXT,
                    performed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (return_id) REFERENCES hesa_returns(id)
                )
            """)
            conn.commit()

    def create_return(self, academic_year: str, return_type: str, created_by: str = None, notes: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO hesa_returns (academic_year, return_type, created_by, notes) VALUES (?, ?, ?, ?)",
                (academic_year, return_type, created_by, notes)
            )
            conn.commit()
            return cursor.lastrowid

    def get_return(self, return_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM hesa_returns WHERE id = ?", (return_id,)).fetchone()
            return dict(row) if row else None

    def list_returns(self, status: str = None) -> List[Dict]:
        with get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM hesa_returns WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM hesa_returns ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def update_return_status(self, return_id: int, status: str, performed_by: str = None) -> bool:
        with transaction() as conn:
            conn.execute("UPDATE hesa_returns SET status = ? WHERE id = ?", (status, return_id))
            if status == 'submitted':
                conn.execute("UPDATE hesa_returns SET submitted_at = ? WHERE id = ?", (datetime.now().isoformat(), return_id))
            conn.execute(
                "INSERT INTO hesa_submission_log (return_id, action, details, performed_by) VALUES (?, ?, ?, ?)",
                (return_id, f"Status changed to {status}", None, performed_by)
            )
            conn.commit()
            return True

    def generate_xml_export(self, return_id: int, actor: Optional[dict] = None) -> str:
        """Build the return's XML from the student records.

        A ``Student`` return is the HESA Data Futures build in
        ``application/statutory/hesa_return`` (institution UKPRN and HESA
        provider id required, validation report stored on the return, upload
        file written to the hesa_jisc connector folder when there are no
        errors). ``actor`` is the signed-in user (admin or registry).
        The staff return is built in Staff HR (HESA staff return); other
        return types are not produced by this system, so they are refused
        rather than filled with placeholder data.
        """
        ret = self.get_return(return_id)
        if not ret:
            return ""
        if ret['return_type'] == 'Staff':
            raise ValueError("The HESA staff return is built in Staff HR → Compliance "
                             "(HESA staff return)")
        if ret['return_type'] != 'Student':
            raise ValueError(f"{ret['return_type']} returns are not produced by this system")
        from education_system.systems.university.application.statutory import hesa_return
        hesa_return.build(actor, ret['academic_year'], ret.get('period_start'),
                          ret.get('period_end'), ret.get('reference_period') or "",
                          return_id=return_id)
        return self.get_return(return_id).get('xml_data') or ""

    def add_field_mapping(self, return_type: str, hesa_field: str, local_field: str, transform_rule: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO hesa_field_mappings (return_type, hesa_field, local_field, transform_rule) VALUES (?, ?, ?, ?)",
                (return_type, hesa_field, local_field, transform_rule)
            )
            conn.commit()
            return cursor.lastrowid

    def get_field_mappings(self, return_type: str = None) -> List[Dict]:
        with get_connection() as conn:
            if return_type:
                rows = conn.execute("SELECT * FROM hesa_field_mappings WHERE return_type = ?", (return_type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM hesa_field_mappings").fetchall()
            return [dict(r) for r in rows]

    def log_submission_action(self, return_id: int, action: str, details: str = None, performed_by: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO hesa_submission_log (return_id, action, details, performed_by) VALUES (?, ?, ?, ?)",
                (return_id, action, details, performed_by)
            )
            conn.commit()
            return cursor.lastrowid

    def get_submission_log(self, return_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM hesa_submission_log WHERE return_id = ? ORDER BY performed_at DESC", (return_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_return_statistics(self) -> Dict:
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM hesa_returns").fetchone()[0]
            by_status = {}
            for row in conn.execute("SELECT status, COUNT(*) as cnt FROM hesa_returns GROUP BY status").fetchall():
                by_status[row[0]] = row[1]
            return {"total": total, "by_status": by_status}
