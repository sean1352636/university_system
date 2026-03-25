"""Supply/cover agency integration service."""
from education_system.college_system.core.exceptions import CoverAgencyError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class CoverAgencyService:
    """Manage cover agency requests and invoicing."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ------------------------------------------------------------------
    # Agencies
    # ------------------------------------------------------------------

    def add_agency(self, agency_name, contact_name, contact_email, contact_phone,
                   day_rate, preferred_rank=0):
        """Register a new supply agency."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO cover_agencies
                   (agency_name, contact_name, contact_email, contact_phone,
                    day_rate, preferred_rank, is_active,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
                (agency_name, contact_name, contact_email, contact_phone,
                 day_rate, preferred_rank),
            )
            conn.commit()
            logger.info("Added agency '%s' (id=%s)", agency_name, cur.lastrowid)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to add agency: %s", exc)
            raise CoverAgencyError(f"Failed to add agency: {exc}") from exc
        finally:
            conn.close()

    def list_agencies(self, active_only=True):
        """List all agencies."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM cover_agencies"
            params = []
            if active_only:
                sql += " WHERE is_active = 1"
            sql += " ORDER BY preferred_rank ASC, agency_name"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list agencies: %s", exc)
            raise CoverAgencyError(f"Failed to list agencies: {exc}") from exc
        finally:
            conn.close()

    def update_agency(self, agency_id, **updates):
        """Update agency details."""
        conn = self._conn()
        try:
            allowed = {"agency_name", "contact_name", "contact_email", "contact_phone",
                        "address", "specialisms", "day_rate", "preferred_rank", "is_active",
                        "contract_start", "contract_end", "notes"}
            fields = {k: v for k, v in updates.items() if k in allowed}
            if not fields:
                return
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [agency_id]
            conn.execute(
                f"UPDATE cover_agencies SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Updated agency %s", agency_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update agency: %s", exc)
            raise CoverAgencyError(f"Failed to update agency: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Cover Requests
    # ------------------------------------------------------------------

    def create_cover_request(self, agency_id, date_required, subject_area,
                             start_time, end_time, year_group=None,
                             special_requirements=None, cover_arrangement_id=None):
        """Create a cover request to an agency."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO agency_cover_requests
                   (cover_arrangement_id, agency_id, subject_area, date_required,
                    start_time, end_time, year_group, special_requirements,
                    agency_response, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'draft',
                           datetime('now'), datetime('now'))""",
                (cover_arrangement_id, agency_id, subject_area, date_required,
                 start_time, end_time, year_group, special_requirements),
            )
            conn.commit()
            logger.info("Created cover request %s for agency %s", cur.lastrowid, agency_id)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create cover request: %s", exc)
            raise CoverAgencyError(f"Failed to create cover request: {exc}") from exc
        finally:
            conn.close()

    def auto_request_cover(self, cover_arrangement_id, subject_area):
        """Auto-request cover from the best-ranked agency."""
        conn = self._conn()
        try:
            agency = conn.execute(
                """SELECT * FROM cover_agencies
                   WHERE is_active = 1
                   ORDER BY preferred_rank ASC
                   LIMIT 1""",
            ).fetchone()
            if not agency:
                raise CoverAgencyError("No active agencies available")
            conn.close()

            # Get cover arrangement details (date etc) - use a generic date if not available
            return self.create_cover_request(
                agency_id=agency["id"],
                date_required="",  # caller should provide context
                subject_area=subject_area,
                start_time="09:00",
                end_time="15:30",
                cover_arrangement_id=cover_arrangement_id,
            )
        except CoverAgencyError:
            raise
        except Exception as exc:
            logger.error("Failed to auto-request cover: %s", exc)
            raise CoverAgencyError(f"Failed to auto-request cover: {exc}") from exc

    def list_requests(self, agency_id=None, status=None, date_from=None, date_to=None):
        """List cover requests with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM agency_cover_requests WHERE 1=1"
            params = []
            if agency_id is not None:
                sql += " AND agency_id = ?"
                params.append(agency_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if date_from:
                sql += " AND date_required >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND date_required <= ?"
                params.append(date_to)
            sql += " ORDER BY date_required DESC, id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list requests: %s", exc)
            raise CoverAgencyError(f"Failed to list requests: {exc}") from exc
        finally:
            conn.close()

    def update_request_response(self, request_id, agency_response, teacher_name=None,
                                day_rate=None):
        """Update the agency's response to a request."""
        conn = self._conn()
        try:
            status = "confirmed" if agency_response == "accepted" else "sent"
            conn.execute(
                """UPDATE agency_cover_requests
                   SET agency_response = ?, teacher_name = COALESCE(?, teacher_name),
                       day_rate = COALESCE(?, day_rate), status = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (agency_response, teacher_name, day_rate, status, request_id),
            )
            conn.commit()
            logger.info("Updated request %s response to %s", request_id, agency_response)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update request response: %s", exc)
            raise CoverAgencyError(f"Failed to update request response: {exc}") from exc
        finally:
            conn.close()

    def confirm_teacher(self, request_id, teacher_name):
        """Confirm a supply teacher for a request."""
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE agency_cover_requests
                   SET teacher_name = ?, teacher_confirmed = 1, status = 'confirmed',
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (teacher_name, request_id),
            )
            conn.commit()
            logger.info("Confirmed teacher '%s' for request %s", teacher_name, request_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to confirm teacher: %s", exc)
            raise CoverAgencyError(f"Failed to confirm teacher: {exc}") from exc
        finally:
            conn.close()

    def cancel_request(self, request_id):
        """Cancel a cover request."""
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE agency_cover_requests
                   SET status = 'cancelled', updated_at = datetime('now')
                   WHERE id = ?""",
                (request_id,),
            )
            conn.commit()
            logger.info("Cancelled request %s", request_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to cancel request: %s", exc)
            raise CoverAgencyError(f"Failed to cancel request: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    def create_invoice(self, agency_id, invoice_number, invoice_date, period_start,
                       period_end, days_covered, total_amount):
        """Create an agency invoice."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO agency_invoices
                   (agency_id, invoice_number, invoice_date, period_start,
                    period_end, days_covered, total_amount, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'received', datetime('now'))""",
                (agency_id, invoice_number, invoice_date, period_start,
                 period_end, days_covered, total_amount),
            )
            conn.commit()
            logger.info("Created invoice %s for agency %s", invoice_number, agency_id)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create invoice: %s", exc)
            raise CoverAgencyError(f"Failed to create invoice: {exc}") from exc
        finally:
            conn.close()

    def list_invoices(self, agency_id=None, status=None):
        """List agency invoices."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM agency_invoices WHERE 1=1"
            params = []
            if agency_id is not None:
                sql += " AND agency_id = ?"
                params.append(agency_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY invoice_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list invoices: %s", exc)
            raise CoverAgencyError(f"Failed to list invoices: {exc}") from exc
        finally:
            conn.close()

    def approve_invoice(self, invoice_id, approved_by):
        """Approve an agency invoice."""
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE agency_invoices
                   SET status = 'approved', approved_by = ?
                   WHERE id = ?""",
                (approved_by, invoice_id),
            )
            conn.commit()
            logger.info("Approved invoice %s", invoice_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to approve invoice: %s", exc)
            raise CoverAgencyError(f"Failed to approve invoice: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_agency_stats(self, agency_id):
        """Get statistics for an agency: requests, acceptance rate, total spend."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) AS total_requests,
                          COUNT(CASE WHEN agency_response = 'accepted' THEN 1 END) AS accepted,
                          COUNT(CASE WHEN agency_response = 'declined' THEN 1 END) AS declined,
                          CASE WHEN COUNT(*) > 0
                               THEN ROUND(COUNT(CASE WHEN agency_response = 'accepted' THEN 1 END) * 100.0 / COUNT(*), 1)
                               ELSE 0 END AS acceptance_rate
                   FROM agency_cover_requests WHERE agency_id = ?""",
                (agency_id,),
            ).fetchone()
            spend = conn.execute(
                """SELECT COALESCE(SUM(total_amount), 0) AS total_spend
                   FROM agency_invoices WHERE agency_id = ? AND status IN ('approved', 'paid')""",
                (agency_id,),
            ).fetchone()
            result = dict(row)
            result["total_spend"] = spend["total_spend"] if spend else 0
            return result
        except Exception as exc:
            logger.error("Failed to get agency stats: %s", exc)
            raise CoverAgencyError(f"Failed to get agency stats: {exc}") from exc
        finally:
            conn.close()

    def get_cover_spend_report(self, date_from, date_to):
        """Get cover spend report for a date range."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ca.agency_name, ca.id AS agency_id,
                          COUNT(acr.id) AS requests,
                          COALESCE(SUM(ai.total_amount), 0) AS total_spend
                   FROM cover_agencies ca
                   LEFT JOIN agency_cover_requests acr
                       ON acr.agency_id = ca.id
                       AND acr.date_required BETWEEN ? AND ?
                   LEFT JOIN agency_invoices ai
                       ON ai.agency_id = ca.id
                       AND ai.period_start >= ? AND ai.period_end <= ?
                   GROUP BY ca.id
                   ORDER BY total_spend DESC""",
                (date_from, date_to, date_from, date_to),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get spend report: %s", exc)
            raise CoverAgencyError(f"Failed to get spend report: {exc}") from exc
        finally:
            conn.close()
