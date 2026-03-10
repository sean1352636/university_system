"""Facility Lettings service."""

from education_system.college_system.core.exceptions import LettingsError
from education_system.college_system.infrastructure.database.db import connect

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_NOW = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LettingsService:
    """Facility Lettings service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Bookings ────────────────────────────────────────────────

    def create_booking(self, hirer_name: str, facility: str,
                       booking_date: str, start_time: str,
                       end_time: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            now = _NOW()
            cols = ["hirer_name", "facility", "booking_date",
                    "start_time", "end_time", "created_at", "updated_at"]
            vals = [hirer_name, facility, booking_date,
                    start_time, end_time, now, now]
            allowed = [
                "organisation", "contact_email", "contact_phone",
                "recurrence", "purpose", "attendee_count",
                "dbs_required", "dbs_verified", "insurance_verified",
                "risk_assessment_done", "fee", "payment_status",
                "invoice_number", "status", "notes",
            ]
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    cols.append(k)
                    vals.append(v)
            placeholders = ", ".join("?" for _ in cols)
            col_str = ", ".join(cols)
            conn.execute(
                f"INSERT INTO lettings_bookings ({col_str}) VALUES ({placeholders})",
                vals,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM lettings_bookings WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except LettingsError:
            raise
        except Exception as e:
            conn.rollback()
            raise LettingsError(f"Failed to create booking: {e}") from e
        finally:
            conn.close()

    def list_bookings(self, facility: str = None, status: str = None,
                      payment_status: str = None, search: str = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM lettings_bookings WHERE 1=1"
            params: list = []
            if facility:
                sql += " AND facility = ?"
                params.append(facility)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if payment_status:
                sql += " AND payment_status = ?"
                params.append(payment_status)
            if search:
                sql += (" AND (hirer_name LIKE ? OR organisation LIKE ?"
                        " OR facility LIKE ? OR purpose LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term, term, term])
            sql += " ORDER BY booking_date DESC, start_time DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_booking(self, booking_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM lettings_bookings WHERE id = ?", (booking_id,)
            ).fetchone()
            if not row:
                raise LettingsError(f"Booking {booking_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_booking(self, booking_id: int, **kwargs) -> dict:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise LettingsError("No valid fields to update.")
        updates["updated_at"] = _NOW()
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [booking_id]
            conn.execute(
                f"UPDATE lettings_bookings SET {sets} WHERE id = ?", vals
            )
            conn.commit()
            return self.get_booking(booking_id)
        except LettingsError:
            raise
        except Exception as e:
            conn.rollback()
            raise LettingsError(f"Failed to update booking: {e}") from e
        finally:
            conn.close()

    def delete_booking(self, booking_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM lettings_bookings WHERE id = ?", (booking_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise LettingsError(f"Failed to delete booking: {e}") from e
        finally:
            conn.close()

    def confirm_booking(self, booking_id: int) -> dict:
        return self.update_booking(booking_id, status="confirmed")

    def cancel_booking(self, booking_id: int) -> dict:
        return self.update_booking(booking_id, status="cancelled")

    # ── Contracts ───────────────────────────────────────────────

    def create_contract(self, hirer_name: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            now = _NOW()
            cols = ["hirer_name", "created_at"]
            vals = [hirer_name, now]
            allowed = [
                "organisation", "contract_start", "contract_end",
                "terms", "agreed_fee", "signed_date", "status",
            ]
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    cols.append(k)
                    vals.append(v)
            placeholders = ", ".join("?" for _ in cols)
            col_str = ", ".join(cols)
            conn.execute(
                f"INSERT INTO lettings_contracts ({col_str}) VALUES ({placeholders})",
                vals,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM lettings_contracts WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except LettingsError:
            raise
        except Exception as e:
            conn.rollback()
            raise LettingsError(f"Failed to create contract: {e}") from e
        finally:
            conn.close()

    def list_contracts(self, status: str = None, search: str = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM lettings_contracts WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if search:
                sql += (" AND (hirer_name LIKE ? OR organisation LIKE ?"
                        " OR terms LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term, term])
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_contract(self, contract_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM lettings_contracts WHERE id = ?", (contract_id,)
            ).fetchone()
            if not row:
                raise LettingsError(f"Contract {contract_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_contract(self, contract_id: int, **kwargs) -> dict:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise LettingsError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [contract_id]
            conn.execute(
                f"UPDATE lettings_contracts SET {sets} WHERE id = ?", vals
            )
            conn.commit()
            return self.get_contract(contract_id)
        except LettingsError:
            raise
        except Exception as e:
            conn.rollback()
            raise LettingsError(f"Failed to update contract: {e}") from e
        finally:
            conn.close()

    def delete_contract(self, contract_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM lettings_contracts WHERE id = ?", (contract_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise LettingsError(f"Failed to delete contract: {e}") from e
        finally:
            conn.close()

    def sign_contract(self, contract_id: int, signed_date: str) -> dict:
        return self.update_contract(
            contract_id, signed_date=signed_date, status="signed"
        )

    # ── Statistics ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            stats = {}

            # Booking counts
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM lettings_bookings"
            ).fetchone()
            stats["total_bookings"] = row["total"] if row else 0

            # By status breakdown
            rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM lettings_bookings GROUP BY status"
            ).fetchall()
            stats["by_status"] = {r["status"]: r["cnt"] for r in rows}

            # Total revenue (confirmed bookings)
            row = conn.execute(
                "SELECT COALESCE(SUM(fee), 0) AS rev FROM lettings_bookings "
                "WHERE status = 'confirmed'"
            ).fetchone()
            stats["total_revenue"] = row["rev"] if row else 0.0

            # Pending payments
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM lettings_bookings "
                "WHERE payment_status = 'unpaid' AND status != 'cancelled'"
            ).fetchone()
            stats["pending_payments"] = row["cnt"] if row else 0

            # Contract counts
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM lettings_contracts"
            ).fetchone()
            stats["total_contracts"] = row["total"] if row else 0

            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM lettings_contracts "
                "WHERE status = 'signed'"
            ).fetchone()
            stats["active_contracts"] = row["cnt"] if row else 0

            row = conn.execute(
                "SELECT COALESCE(SUM(agreed_fee), 0) AS val "
                "FROM lettings_contracts"
            ).fetchone()
            stats["total_contract_value"] = row["val"] if row else 0.0

            return stats
        finally:
            conn.close()
