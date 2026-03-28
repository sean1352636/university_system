"""UCAS data export service in required XML format."""

from education_system.college_system.core.exceptions import UCASExportError
from education_system.college_system.infrastructure.database.db import connect
import logging
import defusedxml.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)


class UCASExportService:
    """Service for managing UCAS data exports."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _ensure_tables(self, conn):
        """Create tables if they don't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ucas_export_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                academic_year TEXT NOT NULL,
                export_type TEXT NOT NULL,
                record_count INTEGER DEFAULT 0,
                exported_by INTEGER,
                status TEXT DEFAULT 'draft',
                xml_data TEXT,
                export_date TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ucas_export_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER REFERENCES ucas_export_batches(id),
                student_id INTEGER,
                ucas_id TEXT,
                personal_id TEXT,
                course_choices TEXT,
                predicted_grades TEXT,
                reference_text TEXT,
                personal_statement_hash TEXT,
                export_status TEXT DEFAULT 'pending',
                error_notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    def create_batch(self, academic_year, export_type):
        """Create a new UCAS export batch."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if export_type not in ("applications", "references", "predictions"):
                raise UCASExportError(f"Invalid export type: {export_type}")
            cur = conn.execute(
                """INSERT INTO ucas_export_batches (academic_year, export_type)
                   VALUES (?, ?)""",
                (academic_year, export_type),
            )
            conn.commit()
            logger.info("Created UCAS export batch id=%d type=%s", cur.lastrowid, export_type)
            return cur.lastrowid
        except UCASExportError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create batch: %s", exc)
            raise UCASExportError(f"Failed to create batch: {exc}") from exc
        finally:
            conn.close()

    def list_batches(self, academic_year=None):
        """List export batches with optional year filter."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM ucas_export_batches WHERE 1=1"
            params = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY created_at DESC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list batches: %s", exc)
            raise UCASExportError(f"Failed to list batches: {exc}") from exc
        finally:
            conn.close()

    def generate_export_data(self, batch_id):
        """Pull data from ucas_records and students to populate export records."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            batch = self._get_batch_row(conn, batch_id)
            # Clear existing records
            conn.execute("DELETE FROM ucas_export_records WHERE batch_id = ?", (batch_id,))
            # Try to pull from ucas_records table first, then students
            count = 0
            try:
                cur = conn.execute(
                    """SELECT ur.student_id, ur.ucas_id, ur.personal_id,
                              ur.course_choices, ur.predicted_grades,
                              ur.reference_text, ur.personal_statement_hash
                       FROM ucas_records ur
                       WHERE ur.academic_year = ?""",
                    (batch["academic_year"],),
                )
                for row in cur.fetchall():
                    conn.execute(
                        """INSERT INTO ucas_export_records
                           (batch_id, student_id, ucas_id, personal_id, course_choices,
                            predicted_grades, reference_text, personal_statement_hash, export_status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                        (batch_id, row[0], row[1], row[2], row[3], row[4], row[5], row[6]),
                    )
                    count += 1
            except Exception:
                # Fallback: pull from students table
                try:
                    cur = conn.execute("SELECT id FROM students")
                    for row in cur.fetchall():
                        conn.execute(
                            """INSERT INTO ucas_export_records
                               (batch_id, student_id, export_status)
                               VALUES (?, ?, 'pending')""",
                            (batch_id, row[0]),
                        )
                        count += 1
                except Exception:
                    pass
            conn.execute(
                "UPDATE ucas_export_batches SET record_count = ?, status = 'generated', updated_at = datetime('now') WHERE id = ?",
                (count, batch_id),
            )
            conn.commit()
            logger.info("Generated %d export records for batch %d", count, batch_id)
            return count
        except UCASExportError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to generate export data: %s", exc)
            raise UCASExportError(f"Failed to generate export data: {exc}") from exc
        finally:
            conn.close()

    def validate_batch(self, batch_id):
        """Validate batch records and flag errors."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            self._get_batch_row(conn, batch_id)
            cur = conn.execute(
                "SELECT * FROM ucas_export_records WHERE batch_id = ?", (batch_id,)
            )
            cols = [d[0] for d in cur.description]
            records = [dict(zip(cols, r)) for r in cur.fetchall()]
            errors = []
            for rec in records:
                rec_errors = []
                if not rec.get("ucas_id"):
                    rec_errors.append("Missing UCAS ID")
                if not rec.get("personal_id"):
                    rec_errors.append("Missing personal ID")
                if rec_errors:
                    error_text = "; ".join(rec_errors)
                    conn.execute(
                        "UPDATE ucas_export_records SET export_status = 'error', error_notes = ? WHERE id = ?",
                        (error_text, rec["id"]),
                    )
                    errors.append(f"Student {rec['student_id']}: {error_text}")
                else:
                    conn.execute(
                        "UPDATE ucas_export_records SET export_status = 'included' WHERE id = ?",
                        (rec["id"],),
                    )
            conn.commit()
            logger.info("Validated batch %d: %d errors", batch_id, len(errors))
            return errors
        except UCASExportError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to validate batch: %s", exc)
            raise UCASExportError(f"Failed to validate batch: {exc}") from exc
        finally:
            conn.close()

    def generate_xml(self, batch_id):
        """Generate UCAS XML format for the batch."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            batch = self._get_batch_row(conn, batch_id)
            root = ET.Element("UCASExport")
            header = ET.SubElement(root, "Header")
            ET.SubElement(header, "AcademicYear").text = batch["academic_year"]
            ET.SubElement(header, "ExportType").text = batch["export_type"]
            ET.SubElement(header, "ExportDate").text = datetime.now().isoformat()

            records_el = ET.SubElement(root, "Records")
            cur = conn.execute(
                "SELECT * FROM ucas_export_records WHERE batch_id = ? AND export_status = 'included'",
                (batch_id,),
            )
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                rec_el = ET.SubElement(records_el, "Record")
                ET.SubElement(rec_el, "StudentID").text = str(rec["student_id"])
                ET.SubElement(rec_el, "UCASID").text = rec.get("ucas_id") or ""
                ET.SubElement(rec_el, "PersonalID").text = rec.get("personal_id") or ""
                ET.SubElement(rec_el, "CourseChoices").text = rec.get("course_choices") or ""
                ET.SubElement(rec_el, "PredictedGrades").text = rec.get("predicted_grades") or ""
                if batch["export_type"] == "references":
                    ET.SubElement(rec_el, "ReferenceText").text = rec.get("reference_text") or ""
                if batch["export_type"] == "applications":
                    ET.SubElement(rec_el, "PersonalStatementHash").text = rec.get("personal_statement_hash") or ""

            xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
            conn.execute(
                "UPDATE ucas_export_batches SET xml_data = ?, updated_at = datetime('now') WHERE id = ?",
                (xml_str, batch_id),
            )
            conn.commit()
            logger.info("Generated XML for batch %d", batch_id)
            return xml_str
        except UCASExportError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to generate XML: %s", exc)
            raise UCASExportError(f"Failed to generate XML: {exc}") from exc
        finally:
            conn.close()

    def mark_exported(self, batch_id, exported_by):
        """Mark a batch as exported."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            self._get_batch_row(conn, batch_id)
            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE ucas_export_batches
                   SET status = 'exported', exported_by = ?, export_date = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (exported_by, now, batch_id),
            )
            conn.execute(
                "UPDATE ucas_export_records SET export_status = 'exported' WHERE batch_id = ? AND export_status = 'included'",
                (batch_id,),
            )
            conn.commit()
            logger.info("Marked batch %d as exported by user %d", batch_id, exported_by)
        except UCASExportError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to mark exported: %s", exc)
            raise UCASExportError(f"Failed to mark exported: {exc}") from exc
        finally:
            conn.close()

    def get_batch_stats(self, batch_id):
        """Get statistics for a batch."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            batch = self._get_batch_row(conn, batch_id)
            cur = conn.execute(
                """SELECT export_status, COUNT(*) as cnt
                   FROM ucas_export_records WHERE batch_id = ?
                   GROUP BY export_status""",
                (batch_id,),
            )
            status_counts = {row[0]: row[1] for row in cur.fetchall()}
            return {
                "batch_id": batch_id,
                "export_type": batch["export_type"],
                "status": batch["status"],
                "total_records": batch.get("record_count", 0),
                "pending": status_counts.get("pending", 0),
                "included": status_counts.get("included", 0),
                "excluded": status_counts.get("excluded", 0),
                "error": status_counts.get("error", 0),
                "exported": status_counts.get("exported", 0),
            }
        except UCASExportError:
            raise
        except Exception as exc:
            logger.error("Failed to get batch stats: %s", exc)
            raise UCASExportError(f"Failed to get batch stats: {exc}") from exc
        finally:
            conn.close()

    def get_student_export_status(self, student_id):
        """Get export status for a student across all batches."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute(
                """SELECT r.*, b.academic_year, b.export_type, b.status as batch_status
                   FROM ucas_export_records r
                   JOIN ucas_export_batches b ON r.batch_id = b.id
                   WHERE r.student_id = ?
                   ORDER BY r.created_at DESC""",
                (student_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to get student export status: %s", exc)
            raise UCASExportError(f"Failed to get student export status: {exc}") from exc
        finally:
            conn.close()

    # ── helpers ──

    def _get_batch_row(self, conn, batch_id):
        """Fetch a batch row as dict using an existing connection."""
        cur = conn.execute("SELECT * FROM ucas_export_batches WHERE id = ?", (batch_id,))
        row = cur.fetchone()
        if not row:
            raise UCASExportError(f"Batch {batch_id} not found")
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
