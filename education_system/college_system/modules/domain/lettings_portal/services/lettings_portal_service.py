"""Lettings management portal service with invoicing."""
from education_system.college_system.core.exceptions import LettingsPortalError
from education_system.college_system.infrastructure.database.db import connect
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class LettingsPortalService:
    """Manage lettings hirers, facilities, bookings, and invoicing."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ------------------------------------------------------------------
    # Hirers
    # ------------------------------------------------------------------

    def register_hirer(self, organisation_name, contact_name, contact_email,
                       contact_phone, account_type="occasional"):
        """Register a new external hirer."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO lettings_hirers
                   (organisation_name, contact_name, contact_email, contact_phone,
                    account_type, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
                (organisation_name, contact_name, contact_email, contact_phone,
                 account_type),
            )
            conn.commit()
            logger.info("Registered hirer '%s' (id=%s)", organisation_name, cur.lastrowid)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to register hirer: %s", exc)
            raise LettingsPortalError(f"Failed to register hirer: {exc}") from exc
        finally:
            conn.close()

    def list_hirers(self, account_type=None, active_only=True):
        """List hirers with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM lettings_hirers WHERE 1=1"
            params = []
            if active_only:
                sql += " AND is_active = 1"
            if account_type:
                sql += " AND account_type = ?"
                params.append(account_type)
            sql += " ORDER BY organisation_name"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list hirers: %s", exc)
            raise LettingsPortalError(f"Failed to list hirers: {exc}") from exc
        finally:
            conn.close()

    def update_hirer(self, hirer_id, **updates):
        """Update hirer details."""
        conn = self._conn()
        try:
            allowed = {"organisation_name", "contact_name", "contact_email",
                        "contact_phone", "address", "account_type", "discount_rate",
                        "credit_limit", "dbs_on_file", "insurance_verified",
                        "insurance_expiry", "terms_agreed", "notes", "is_active"}
            fields = {k: v for k, v in updates.items() if k in allowed}
            if not fields:
                return
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [hirer_id]
            conn.execute(
                f"UPDATE lettings_hirers SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update hirer: %s", exc)
            raise LettingsPortalError(f"Failed to update hirer: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Facilities
    # ------------------------------------------------------------------

    def add_facility(self, facility_name, facility_type, capacity, hourly_rate,
                     half_day_rate=0, full_day_rate=0, community_rate=0):
        """Add a lettable facility."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO lettings_facilities
                   (facility_name, facility_type, capacity, hourly_rate,
                    half_day_rate, full_day_rate, community_rate, is_active,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
                (facility_name, facility_type, capacity, hourly_rate,
                 half_day_rate, full_day_rate, community_rate),
            )
            conn.commit()
            logger.info("Added facility '%s' (id=%s)", facility_name, cur.lastrowid)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to add facility: %s", exc)
            raise LettingsPortalError(f"Failed to add facility: {exc}") from exc
        finally:
            conn.close()

    def list_facilities(self, facility_type=None, active_only=True):
        """List lettable facilities."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM lettings_facilities WHERE 1=1"
            params = []
            if active_only:
                sql += " AND is_active = 1"
            if facility_type:
                sql += " AND facility_type = ?"
                params.append(facility_type)
            sql += " ORDER BY facility_name"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list facilities: %s", exc)
            raise LettingsPortalError(f"Failed to list facilities: {exc}") from exc
        finally:
            conn.close()

    def update_facility(self, facility_id, **updates):
        """Update facility details."""
        conn = self._conn()
        try:
            allowed = {"facility_name", "facility_type", "capacity", "hourly_rate",
                        "half_day_rate", "full_day_rate", "community_rate",
                        "available_days", "available_from", "available_until",
                        "weekend_available", "equipment_included", "special_conditions",
                        "is_active"}
            fields = {k: v for k, v in updates.items() if k in allowed}
            if not fields:
                return
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [facility_id]
            conn.execute(
                f"UPDATE lettings_facilities SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to update facility: %s", exc)
            raise LettingsPortalError(f"Failed to update facility: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def check_availability(self, facility_id, date, start_time, end_time):
        """Check if a facility is available for a date/time slot."""
        conn = self._conn()
        try:
            # Check for blocked slots
            blocked = conn.execute(
                """SELECT COUNT(*) AS cnt FROM lettings_availability
                   WHERE facility_id = ? AND date = ? AND is_blocked = 1
                   AND start_time < ? AND end_time > ?""",
                (facility_id, date, end_time, start_time),
            ).fetchone()
            if blocked and blocked["cnt"] > 0:
                return False

            # Check for existing bookings (if lettings_bookings table exists)
            try:
                booked = conn.execute(
                    """SELECT COUNT(*) AS cnt FROM lettings_bookings
                       WHERE facility_id = ? AND booking_date = ?
                       AND start_time < ? AND end_time > ?
                       AND status != 'cancelled'""",
                    (facility_id, date, end_time, start_time),
                ).fetchone()
                if booked and booked["cnt"] > 0:
                    return False
            except Exception:
                pass  # Table may not exist yet

            return True
        except Exception as exc:
            logger.error("Failed to check availability: %s", exc)
            raise LettingsPortalError(f"Failed to check availability: {exc}") from exc
        finally:
            conn.close()

    def block_availability(self, facility_id, date, start_time, end_time, reason):
        """Block a facility time slot."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO lettings_availability
                   (facility_id, date, start_time, end_time, is_blocked,
                    block_reason, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, datetime('now'))""",
                (facility_id, date, start_time, end_time, reason),
            )
            conn.commit()
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to block availability: %s", exc)
            raise LettingsPortalError(f"Failed to block availability: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Bookings & Invoicing
    # ------------------------------------------------------------------

    def calculate_fee(self, facility_id, start_time, end_time, account_type="occasional"):
        """Calculate the fee for a booking based on duration and account type."""
        conn = self._conn()
        try:
            facility = conn.execute(
                "SELECT * FROM lettings_facilities WHERE id = ?", (facility_id,),
            ).fetchone()
            if not facility:
                raise LettingsPortalError(f"Facility {facility_id} not found")

            # Calculate hours
            start_parts = start_time.split(":")
            end_parts = end_time.split(":")
            start_mins = int(start_parts[0]) * 60 + int(start_parts[1])
            end_mins = int(end_parts[0]) * 60 + int(end_parts[1])
            hours = max((end_mins - start_mins) / 60.0, 0)

            if account_type == "community" and facility["community_rate"]:
                rate = facility["community_rate"]
            else:
                rate = facility["hourly_rate"]

            # Use half-day/full-day rates if cheaper
            fee = hours * rate
            if hours >= 7 and facility["full_day_rate"] > 0:
                fee = min(fee, facility["full_day_rate"])
            elif hours >= 3.5 and facility["half_day_rate"] > 0:
                fee = min(fee, facility["half_day_rate"])

            return round(fee, 2)
        except LettingsPortalError:
            raise
        except Exception as exc:
            logger.error("Failed to calculate fee: %s", exc)
            raise LettingsPortalError(f"Failed to calculate fee: {exc}") from exc
        finally:
            conn.close()

    def create_booking_with_invoice(self, hirer_id, facility_id, booking_date,
                                    start_time, end_time, purpose,
                                    attendee_count=0):
        """Create a booking and generate an invoice."""
        conn = self._conn()
        try:
            # Check availability
            if not self.check_availability(facility_id, booking_date, start_time, end_time):
                raise LettingsPortalError("Facility is not available for the requested slot")

            # Get hirer for account type
            hirer = conn.execute(
                "SELECT * FROM lettings_hirers WHERE id = ?", (hirer_id,),
            ).fetchone()
            if not hirer:
                raise LettingsPortalError(f"Hirer {hirer_id} not found")

            account_type = hirer["account_type"] if hirer else "occasional"
            fee = self.calculate_fee(facility_id, start_time, end_time, account_type)

            # Create booking (if lettings_bookings table exists, use it; otherwise skip)
            booking_id = None
            try:
                cur = conn.execute(
                    """INSERT INTO lettings_bookings
                       (hirer_id, facility_id, booking_date, start_time, end_time,
                        purpose, attendee_count, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed',
                               datetime('now'), datetime('now'))""",
                    (hirer_id, facility_id, booking_date, start_time, end_time,
                     purpose, attendee_count),
                )
                booking_id = cur.lastrowid
            except Exception:
                pass  # Table may not exist

            # Apply discount
            discount = hirer.get("discount_rate", 0) or 0
            discount_amount = round(fee * discount / 100.0, 2)
            subtotal = fee
            vat_amount = round((subtotal - discount_amount) * 0.2, 2)  # 20% VAT
            total = round(subtotal - discount_amount + vat_amount, 2)

            # Generate invoice number
            now = datetime.now()
            inv_number = f"LET-{now.strftime('%Y%m%d')}-{hirer_id}-{booking_id or 0}"

            inv_cur = conn.execute(
                """INSERT INTO lettings_invoices
                   (booking_id, hirer_id, invoice_number, invoice_date,
                    subtotal, vat_amount, discount_amount, total_amount,
                    due_date, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now', '+30 days'),
                           'draft', datetime('now'), datetime('now'))""",
                (booking_id, hirer_id, inv_number, now.strftime("%Y-%m-%d"),
                 subtotal, vat_amount, discount_amount, total),
            )
            conn.commit()
            logger.info("Created booking %s with invoice %s", booking_id, inv_cur.lastrowid)
            return {
                "booking_id": booking_id,
                "invoice_id": inv_cur.lastrowid,
                "invoice_number": inv_number,
                "subtotal": subtotal,
                "discount_amount": discount_amount,
                "vat_amount": vat_amount,
                "total_amount": total,
            }
        except LettingsPortalError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create booking: %s", exc)
            raise LettingsPortalError(f"Failed to create booking: {exc}") from exc
        finally:
            conn.close()

    def generate_invoice(self, booking_id, hirer_id):
        """Generate an invoice for an existing booking."""
        conn = self._conn()
        try:
            now = datetime.now()
            inv_number = f"LET-{now.strftime('%Y%m%d')}-{hirer_id}-{booking_id}"
            cur = conn.execute(
                """INSERT INTO lettings_invoices
                   (booking_id, hirer_id, invoice_number, invoice_date,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'draft', datetime('now'), datetime('now'))""",
                (booking_id, hirer_id, inv_number, now.strftime("%Y-%m-%d")),
            )
            conn.commit()
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to generate invoice: %s", exc)
            raise LettingsPortalError(f"Failed to generate invoice: {exc}") from exc
        finally:
            conn.close()

    def list_invoices(self, hirer_id=None, status=None):
        """List lettings invoices."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM lettings_invoices WHERE 1=1"
            params = []
            if hirer_id is not None:
                sql += " AND hirer_id = ?"
                params.append(hirer_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY invoice_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list invoices: %s", exc)
            raise LettingsPortalError(f"Failed to list invoices: {exc}") from exc
        finally:
            conn.close()

    def record_payment(self, invoice_id, amount, payment_date=None):
        """Record a payment against an invoice."""
        conn = self._conn()
        try:
            pay_date = payment_date or datetime.now().strftime("%Y-%m-%d")
            conn.execute(
                """UPDATE lettings_invoices
                   SET paid_amount = COALESCE(paid_amount, 0) + ?,
                       paid_date = ?, status = 'paid',
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (amount, pay_date, invoice_id),
            )
            conn.commit()
            logger.info("Recorded payment of %.2f for invoice %s", amount, invoice_id)
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to record payment: %s", exc)
            raise LettingsPortalError(f"Failed to record payment: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_revenue_report(self, date_from, date_to):
        """Get revenue report for a date range."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT lh.organisation_name, lh.id AS hirer_id,
                          COUNT(li.id) AS num_invoices,
                          COALESCE(SUM(li.total_amount), 0) AS total_invoiced,
                          COALESCE(SUM(li.paid_amount), 0) AS total_paid,
                          COALESCE(SUM(li.total_amount), 0) - COALESCE(SUM(li.paid_amount), 0) AS outstanding
                   FROM lettings_hirers lh
                   LEFT JOIN lettings_invoices li
                       ON li.hirer_id = lh.id
                       AND li.invoice_date BETWEEN ? AND ?
                   GROUP BY lh.id
                   HAVING num_invoices > 0
                   ORDER BY total_invoiced DESC""",
                (date_from, date_to),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get revenue report: %s", exc)
            raise LettingsPortalError(f"Failed to get revenue report: {exc}") from exc
        finally:
            conn.close()

    def get_utilisation_report(self, date_from, date_to):
        """Get facility utilisation report."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT lf.facility_name, lf.id AS facility_id,
                          lf.facility_type,
                          COUNT(lb.id) AS num_bookings,
                          COALESCE(SUM(
                              (CAST(SUBSTR(lb.end_time, 1, 2) AS INTEGER) * 60 +
                               CAST(SUBSTR(lb.end_time, 4, 2) AS INTEGER) -
                               CAST(SUBSTR(lb.start_time, 1, 2) AS INTEGER) * 60 -
                               CAST(SUBSTR(lb.start_time, 4, 2) AS INTEGER)) / 60.0
                          ), 0) AS total_hours
                   FROM lettings_facilities lf
                   LEFT JOIN lettings_bookings lb
                       ON lb.facility_id = lf.id
                       AND lb.booking_date BETWEEN ? AND ?
                       AND lb.status != 'cancelled'
                   GROUP BY lf.id
                   ORDER BY total_hours DESC""",
                (date_from, date_to),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get utilisation report: %s", exc)
            raise LettingsPortalError(f"Failed to get utilisation report: {exc}") from exc
        finally:
            conn.close()

    def get_hirer_statement(self, hirer_id):
        """Get a statement for a hirer showing all invoices and payments."""
        conn = self._conn()
        try:
            hirer = conn.execute(
                "SELECT * FROM lettings_hirers WHERE id = ?", (hirer_id,),
            ).fetchone()
            if not hirer:
                raise LettingsPortalError(f"Hirer {hirer_id} not found")

            invoices = conn.execute(
                """SELECT * FROM lettings_invoices
                   WHERE hirer_id = ?
                   ORDER BY invoice_date""",
                (hirer_id,),
            ).fetchall()

            total_invoiced = sum(r["total_amount"] or 0 for r in invoices)
            total_paid = sum(r["paid_amount"] or 0 for r in invoices)

            return {
                "hirer": dict(hirer),
                "invoices": [dict(r) for r in invoices],
                "total_invoiced": round(total_invoiced, 2),
                "total_paid": round(total_paid, 2),
                "balance": round(total_invoiced - total_paid, 2),
            }
        except LettingsPortalError:
            raise
        except Exception as exc:
            logger.error("Failed to get hirer statement: %s", exc)
            raise LettingsPortalError(f"Failed to get hirer statement: {exc}") from exc
        finally:
            conn.close()
