"""DfE School Census and ILR automated data extraction for statutory returns."""

from education_system.college_system.core.exceptions import CensusILRError
from education_system.college_system.infrastructure.database.db import connect
import logging
from xml.etree.ElementTree import Element, SubElement, tostring  # nosec  # write-only XML generation, no parsing of untrusted input
from datetime import datetime

logger = logging.getLogger(__name__)


class CensusILRService:
    """Service for managing DfE Census and ILR data returns."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _ensure_tables(self, conn):
        """Create tables if they don't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS census_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_type TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                term TEXT,
                collection_period TEXT,
                submission_deadline TEXT,
                status TEXT DEFAULT 'draft',
                validation_errors TEXT,
                record_count INTEGER DEFAULT 0,
                submitted_by INTEGER,
                submitted_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS census_student_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                census_id INTEGER NOT NULL REFERENCES census_returns(id),
                student_id INTEGER NOT NULL,
                uln TEXT,
                upn TEXT,
                ethnicity TEXT,
                fsm_eligible INTEGER DEFAULT 0,
                send_provision TEXT,
                ehcp INTEGER DEFAULT 0,
                hours_at_provider REAL,
                hours_at_employer REAL,
                planned_hours REAL,
                funding_model TEXT,
                programme_type TEXT,
                valid INTEGER DEFAULT 1,
                validation_notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ilr_learning_aims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                census_id INTEGER NOT NULL REFERENCES census_returns(id),
                student_id INTEGER NOT NULL,
                learning_aim_ref TEXT NOT NULL,
                aim_type TEXT,
                start_date TEXT,
                planned_end_date TEXT,
                actual_end_date TEXT,
                completion_status TEXT,
                outcome TEXT,
                funding_model TEXT,
                delivery_location TEXT,
                partner_ukprn TEXT,
                valid INTEGER DEFAULT 1,
                validation_notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    def create_return(self, return_type, academic_year, term, collection_period, submission_deadline):
        """Create a new census/ILR return."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            if return_type not in ("census", "ilr", "hesa"):
                raise CensusILRError(f"Invalid return type: {return_type}")
            cur = conn.execute(
                """INSERT INTO census_returns
                   (return_type, academic_year, term, collection_period, submission_deadline)
                   VALUES (?, ?, ?, ?, ?)""",
                (return_type, academic_year, term, collection_period, submission_deadline),
            )
            conn.commit()
            logger.info("Created %s return id=%d for %s", return_type, cur.lastrowid, academic_year)
            return cur.lastrowid
        except CensusILRError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create return: %s", exc)
            raise CensusILRError(f"Failed to create return: {exc}") from exc
        finally:
            conn.close()

    def list_returns(self, return_type=None, academic_year=None):
        """List census/ILR returns with optional filters."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            sql = "SELECT * FROM census_returns WHERE 1=1"
            params = []
            if return_type:
                sql += " AND return_type = ?"
                params.append(return_type)
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY created_at DESC"
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Failed to list returns: %s", exc)
            raise CensusILRError(f"Failed to list returns: {exc}") from exc
        finally:
            conn.close()

    def get_return(self, return_id):
        """Get a single return by ID."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            cur = conn.execute("SELECT * FROM census_returns WHERE id = ?", (return_id,))
            row = cur.fetchone()
            if not row:
                raise CensusILRError(f"Return {return_id} not found")
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        except CensusILRError:
            raise
        except Exception as exc:
            logger.error("Failed to get return: %s", exc)
            raise CensusILRError(f"Failed to get return: {exc}") from exc
        finally:
            conn.close()

    def generate_census_data(self, return_id):
        """Populate census_student_records from students table."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            if ret["return_type"] != "census":
                raise CensusILRError("Return is not a census type")
            # Clear existing records for this return
            conn.execute("DELETE FROM census_student_records WHERE census_id = ?", (return_id,))
            # Pull students - best effort from students table
            try:
                cur = conn.execute("SELECT id, uln FROM students")
                students = cur.fetchall()
            except Exception:
                students = []
            count = 0
            for student in students:
                conn.execute(
                    """INSERT INTO census_student_records (census_id, student_id, uln)
                       VALUES (?, ?, ?)""",
                    (return_id, student[0], student[1] if len(student) > 1 else None),
                )
                count += 1
            conn.execute(
                "UPDATE census_returns SET record_count = ?, updated_at = datetime('now') WHERE id = ?",
                (count, return_id),
            )
            conn.commit()
            logger.info("Generated %d census student records for return %d", count, return_id)
            return count
        except CensusILRError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to generate census data: %s", exc)
            raise CensusILRError(f"Failed to generate census data: {exc}") from exc
        finally:
            conn.close()

    def generate_ilr_data(self, return_id):
        """Populate ilr_learning_aims from funding_records."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            if ret["return_type"] != "ilr":
                raise CensusILRError("Return is not an ILR type")
            conn.execute("DELETE FROM ilr_learning_aims WHERE census_id = ?", (return_id,))
            try:
                cur = conn.execute(
                    "SELECT student_id, learning_aim_ref, start_date, planned_end_date, funding_model "
                    "FROM funding_records"
                )
                records = cur.fetchall()
            except Exception:
                records = []
            count = 0
            for rec in records:
                conn.execute(
                    """INSERT INTO ilr_learning_aims
                       (census_id, student_id, learning_aim_ref, start_date, planned_end_date, funding_model)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (return_id, rec[0], rec[1], rec[2], rec[3], rec[4] if len(rec) > 4 else None),
                )
                count += 1
            conn.execute(
                "UPDATE census_returns SET record_count = ?, updated_at = datetime('now') WHERE id = ?",
                (count, return_id),
            )
            conn.commit()
            logger.info("Generated %d ILR learning aims for return %d", count, return_id)
            return count
        except CensusILRError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to generate ILR data: %s", exc)
            raise CensusILRError(f"Failed to generate ILR data: {exc}") from exc
        finally:
            conn.close()

    def validate_return(self, return_id):
        """Validate data and update validation_errors."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            errors = []
            if ret["return_type"] == "census":
                cur = conn.execute(
                    "SELECT * FROM census_student_records WHERE census_id = ?", (return_id,)
                )
                cols = [d[0] for d in cur.description]
                records = [dict(zip(cols, r)) for r in cur.fetchall()]
                for rec in records:
                    if not rec.get("uln") and not rec.get("upn"):
                        errors.append(f"Student {rec['student_id']}: missing ULN and UPN")
                        conn.execute(
                            "UPDATE census_student_records SET valid = 0, validation_notes = ? WHERE id = ?",
                            ("Missing ULN and UPN", rec["id"]),
                        )
            elif ret["return_type"] == "ilr":
                cur = conn.execute(
                    "SELECT * FROM ilr_learning_aims WHERE census_id = ?", (return_id,)
                )
                cols = [d[0] for d in cur.description]
                records = [dict(zip(cols, r)) for r in cur.fetchall()]
                for rec in records:
                    if not rec.get("learning_aim_ref"):
                        errors.append(f"Student {rec['student_id']}: missing learning aim reference")
                        conn.execute(
                            "UPDATE ilr_learning_aims SET valid = 0, validation_notes = ? WHERE id = ?",
                            ("Missing learning aim reference", rec["id"]),
                        )
                    if not rec.get("start_date"):
                        errors.append(f"Student {rec['student_id']}: missing start date")
            error_text = "\n".join(errors) if errors else None
            status = "validated" if not errors else "draft"
            conn.execute(
                "UPDATE census_returns SET validation_errors = ?, status = ?, updated_at = datetime('now') WHERE id = ?",
                (error_text, status, return_id),
            )
            conn.commit()
            logger.info("Validated return %d: %d errors", return_id, len(errors))
            return errors
        except CensusILRError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to validate return: %s", exc)
            raise CensusILRError(f"Failed to validate return: {exc}") from exc
        finally:
            conn.close()

    def get_validation_errors(self, return_id):
        """Get validation errors for a return."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            errors_text = ret.get("validation_errors") or ""
            return errors_text.split("\n") if errors_text else []
        except CensusILRError:
            raise
        except Exception as exc:
            logger.error("Failed to get validation errors: %s", exc)
            raise CensusILRError(f"Failed to get validation errors: {exc}") from exc
        finally:
            conn.close()

    def export_census_xml(self, return_id):
        """Export census data as XML string."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            root = Element("CensusReturn")
            header = SubElement(root, "Header")
            SubElement(header, "ReturnType").text = ret["return_type"]
            SubElement(header, "AcademicYear").text = ret["academic_year"]
            SubElement(header, "Term").text = ret.get("term") or ""
            SubElement(header, "CollectionPeriod").text = ret.get("collection_period") or ""
            students_el = SubElement(root, "Students")
            cur = conn.execute(
                "SELECT * FROM census_student_records WHERE census_id = ? AND valid = 1",
                (return_id,),
            )
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                student_el = SubElement(students_el, "Student")
                SubElement(student_el, "StudentID").text = str(rec["student_id"])
                SubElement(student_el, "ULN").text = rec.get("uln") or ""
                SubElement(student_el, "UPN").text = rec.get("upn") or ""
                SubElement(student_el, "Ethnicity").text = rec.get("ethnicity") or ""
                SubElement(student_el, "FSMEligible").text = str(rec.get("fsm_eligible", 0))
                SubElement(student_el, "SENDProvision").text = rec.get("send_provision") or ""
                SubElement(student_el, "EHCP").text = str(rec.get("ehcp", 0))
            xml_str = tostring(root, encoding="unicode", xml_declaration=True)
            logger.info("Exported census XML for return %d", return_id)
            return xml_str
        except CensusILRError:
            raise
        except Exception as exc:
            logger.error("Failed to export census XML: %s", exc)
            raise CensusILRError(f"Failed to export census XML: {exc}") from exc
        finally:
            conn.close()

    def export_ilr_xml(self, return_id):
        """Export ILR data as XML string."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            root = Element("ILRReturn")
            header = SubElement(root, "Header")
            SubElement(header, "AcademicYear").text = ret["academic_year"]
            SubElement(header, "CollectionPeriod").text = ret.get("collection_period") or ""
            aims_el = SubElement(root, "LearningAims")
            cur = conn.execute(
                "SELECT * FROM ilr_learning_aims WHERE census_id = ? AND valid = 1",
                (return_id,),
            )
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                aim_el = SubElement(aims_el, "LearningAim")
                SubElement(aim_el, "StudentID").text = str(rec["student_id"])
                SubElement(aim_el, "LearningAimRef").text = rec.get("learning_aim_ref") or ""
                SubElement(aim_el, "AimType").text = rec.get("aim_type") or ""
                SubElement(aim_el, "StartDate").text = rec.get("start_date") or ""
                SubElement(aim_el, "PlannedEndDate").text = rec.get("planned_end_date") or ""
                SubElement(aim_el, "ActualEndDate").text = rec.get("actual_end_date") or ""
                SubElement(aim_el, "CompletionStatus").text = rec.get("completion_status") or ""
                SubElement(aim_el, "Outcome").text = rec.get("outcome") or ""
                SubElement(aim_el, "FundingModel").text = rec.get("funding_model") or ""
            xml_str = tostring(root, encoding="unicode", xml_declaration=True)
            logger.info("Exported ILR XML for return %d", return_id)
            return xml_str
        except CensusILRError:
            raise
        except Exception as exc:
            logger.error("Failed to export ILR XML: %s", exc)
            raise CensusILRError(f"Failed to export ILR XML: {exc}") from exc
        finally:
            conn.close()

    def submit_return(self, return_id, submitted_by):
        """Mark a return as submitted."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            if ret["status"] not in ("validated", "draft"):
                raise CensusILRError(f"Cannot submit return in status: {ret['status']}")
            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE census_returns
                   SET status = 'submitted', submitted_by = ?, submitted_at = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (submitted_by, now, return_id),
            )
            conn.commit()
            logger.info("Submitted return %d by user %d", return_id, submitted_by)
        except CensusILRError:
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to submit return: %s", exc)
            raise CensusILRError(f"Failed to submit return: {exc}") from exc
        finally:
            conn.close()

    def get_return_stats(self, return_id):
        """Get statistics for a return - record counts, valid/invalid."""
        conn = self._conn()
        try:
            self._ensure_tables(conn)
            ret = self._get_return_row(conn, return_id)
            stats = {"return_id": return_id, "return_type": ret["return_type"], "status": ret["status"]}
            if ret["return_type"] == "census":
                cur = conn.execute(
                    "SELECT COUNT(*) as total, SUM(CASE WHEN valid=1 THEN 1 ELSE 0 END) as valid_count "
                    "FROM census_student_records WHERE census_id = ?",
                    (return_id,),
                )
                row = cur.fetchone()
                stats["total_records"] = row[0] or 0
                stats["valid_records"] = row[1] or 0
                stats["invalid_records"] = stats["total_records"] - stats["valid_records"]
            elif ret["return_type"] == "ilr":
                cur = conn.execute(
                    "SELECT COUNT(*) as total, SUM(CASE WHEN valid=1 THEN 1 ELSE 0 END) as valid_count "
                    "FROM ilr_learning_aims WHERE census_id = ?",
                    (return_id,),
                )
                row = cur.fetchone()
                stats["total_records"] = row[0] or 0
                stats["valid_records"] = row[1] or 0
                stats["invalid_records"] = stats["total_records"] - stats["valid_records"]
            return stats
        except CensusILRError:
            raise
        except Exception as exc:
            logger.error("Failed to get return stats: %s", exc)
            raise CensusILRError(f"Failed to get return stats: {exc}") from exc
        finally:
            conn.close()

    # ── helpers ──

    def _get_return_row(self, conn, return_id):
        """Fetch a return row as dict using an existing connection."""
        cur = conn.execute("SELECT * FROM census_returns WHERE id = ?", (return_id,))
        row = cur.fetchone()
        if not row:
            raise CensusILRError(f"Return {return_id} not found")
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
