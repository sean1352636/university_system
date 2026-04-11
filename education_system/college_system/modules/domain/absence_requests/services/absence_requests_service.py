"""Service for managing absence requests."""

from datetime import datetime, date
from education_system.college_system.core.exceptions import AbsenceRequestError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)

ABSENCE_TYPES = [
    "sick",
    "medical_appointment",
    "family_emergency",
    "bereavement",
    "annual_leave",
    "study_leave",
    "maternity",
    "paternity",
    "unpaid_leave",
    "jury_duty",
    "religious_observance",
    "other",
]

VALID_STATUSES = ["pending", "approved", "rejected", "cancelled"]


def _parse_date(value: str, field_name: str) -> date:
    """Parse and validate a date string (YYYY-MM-DD)."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid date in YYYY-MM-DD format.")


class AbsenceRequestService:
    """Absence Requests management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _validate_request_data(self, data: dict, *, is_update: bool = False):
        """Validate request fields."""
        if not is_update:
            for field in ("staff_id", "absence_type", "start_date", "end_date"):
                if not data.get(field):
                    raise ValidationError(f"{field} is required.")

        if "absence_type" in data and data["absence_type"] not in ABSENCE_TYPES:
            raise ValidationError(
                f"Invalid absence type '{data['absence_type']}'. "
                f"Valid types: {', '.join(ABSENCE_TYPES)}"
            )

        if "status" in data and data["status"] and data["status"] not in VALID_STATUSES:
            raise ValidationError(
                f"Invalid status '{data['status']}'. Valid statuses: {', '.join(VALID_STATUSES)}"
            )

        start = data.get("start_date")
        end = data.get("end_date")
        if start:
            start_date = _parse_date(start, "start_date")
        if end:
            end_date = _parse_date(end, "end_date")
        if start and end:
            if end_date < start_date:
                raise ValidationError("end_date cannot be before start_date.")

    def create_request(self, **kwargs) -> dict:
        """Create a new absence request."""
        self._validate_request_data(kwargs)
        # Default status to pending
        if not kwargs.get("status"):
            kwargs["status"] = "pending"
        conn = self._conn()
        try:
            # Iterate over a literal column tuple so CodeQL recognises
            # the column names as untainted (py/sql-injection).
            col_names: list[str] = []
            values: list = []
            for col in ('staff_id', 'absence_type', 'start_date', 'end_date',
                        'reason', 'status', 'approved_by'):
                val = kwargs.get(col)
                if val is not None:
                    col_names.append(col)
                    values.append(val)
            cols = ", ".join(col_names)
            placeholders = ", ".join("?" for _ in col_names)
            conn.execute(
                f"INSERT INTO absence_requests ({cols}) VALUES ({placeholders})",  # nosec B608
                values,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM absence_requests WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Request created: id=%d", row["id"])
            return dict(row)
        except (AbsenceRequestError, ValidationError):
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AbsenceRequestError(f"Failed to create request: {e}") from e
        finally:
            conn.close()

    def get_request(self, pk: int) -> dict | None:
        """Get request by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM absence_requests WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_requests(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List requests with optional filters.

        Supports filters: staff_id, absence_type, status, date_from, date_to.
        """
        sql = "SELECT * FROM absence_requests WHERE 1=1"
        params: list = []

        # Handle date range filters separately
        date_from = filters.pop("date_from", None)
        date_to = filters.pop("date_to", None)
        if date_from:
            _parse_date(date_from, "date_from")
            sql += " AND start_date >= ?"
            params.append(date_from)
        if date_to:
            _parse_date(date_to, "date_to")
            sql += " AND end_date <= ?"
            params.append(date_to)

        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_request(self, pk: int, **kwargs) -> dict:
        """Update request record."""
        allowed = {"staff_id", "absence_type", "start_date", "end_date", "reason", "status", "approved_by"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        self._validate_request_data(updates, is_update=True)
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE absence_requests SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Request updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM absence_requests WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def approve_request(self, pk: int, approved_by: int) -> dict:
        """Approve a pending absence request."""
        request = self.get_request(pk)
        if not request:
            raise AbsenceRequestError("Request not found.")
        if request["status"] != "pending":
            raise AbsenceRequestError(
                f"Cannot approve request with status '{request['status']}'. Only pending requests can be approved."
            )
        return self.update_request(pk, status="approved", approved_by=approved_by)

    def reject_request(self, pk: int, approved_by: int) -> dict:
        """Reject a pending absence request."""
        request = self.get_request(pk)
        if not request:
            raise AbsenceRequestError("Request not found.")
        if request["status"] != "pending":
            raise AbsenceRequestError(
                f"Cannot reject request with status '{request['status']}'. Only pending requests can be rejected."
            )
        return self.update_request(pk, status="rejected", approved_by=approved_by)

    def cancel_request(self, pk: int, staff_id: int) -> dict:
        """Cancel own pending request."""
        request = self.get_request(pk)
        if not request:
            raise AbsenceRequestError("Request not found.")
        if request["staff_id"] != staff_id:
            raise AbsenceRequestError("You can only cancel your own requests.")
        if request["status"] != "pending":
            raise AbsenceRequestError(
                f"Cannot cancel request with status '{request['status']}'. Only pending requests can be cancelled."
            )
        return self.update_request(pk, status="cancelled")

    def delete_request(self, pk: int) -> bool:
        """Delete request."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM absence_requests WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AbsenceRequestError("Request not found.")
            conn.execute("DELETE FROM absence_requests WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Request deleted: pk=%d", pk)
            return True
        except AbsenceRequestError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AbsenceRequestError(f"Failed to delete request: {e}") from e
        finally:
            conn.close()

    def count_requests(self, **filters) -> int:
        """Count requests."""
        sql = "SELECT COUNT(*) as cnt FROM absence_requests WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def get_my_requests(self, staff_id: int, *, status: str | None = None) -> list[dict]:
        """Get all requests for a specific staff member."""
        filters = {"staff_id": staff_id}
        if status:
            filters["status"] = status
        return self.list_requests(**filters)
