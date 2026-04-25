"""Service for managing staff absence requests.

Provides CRUD, state transitions (approve/reject/cancel), and reporting
over the ``absence_requests`` table. All database errors are translated to
``AbsenceRequestError``; input errors are raised as ``ValidationError`` so
callers can distinguish user mistakes from infrastructure failures.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timezone
from typing import Iterable

from education_system.college_system.core.exceptions import (
    AbsenceRequestError,
    DatabaseError,
    ValidationError,
)
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
from education_system.college_system.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ABSENCE_TYPES: list[str] = [
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

VALID_STATUSES: list[str] = ["pending", "approved", "rejected", "cancelled"]

# Columns allowed on INSERT. Whitelisted so CodeQL accepts the dynamic SQL
# as non-tainted (py/sql-injection).
_INSERT_COLUMNS: tuple[str, ...] = (
    "staff_id",
    "absence_type",
    "start_date",
    "end_date",
    "reason",
    "status",
    "approved_by",
)

# Columns allowed on UPDATE (superset of insert — includes reason/status/approver).
_UPDATE_COLUMNS: tuple[str, ...] = (
    "absence_type",
    "approved_by",
    "end_date",
    "reason",
    "staff_id",
    "start_date",
    "status",
)

_TERMINAL_STATUSES: frozenset[str] = frozenset({"approved", "rejected", "cancelled"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(value: str, field_name: str) -> date:
    """Parse an ISO ``YYYY-MM-DD`` string or raise ``ValidationError``."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            f"{field_name} must be a valid date in YYYY-MM-DD format."
        ) from exc


def _utcnow_iso() -> str:
    """Return an ISO-8601 timestamp in UTC (tz-aware, replaces utcnow())."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AbsenceRequestService:
    """Absence Requests management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return connect(self._db_path)

    # -- Validation --------------------------------------------------------

    def _validate_request_data(self, data: dict, *, is_update: bool = False) -> None:
        """Validate request fields.

        On create, staff_id / absence_type / start_date / end_date are required.
        On update, only supplied fields are validated.
        """
        if not is_update:
            for field in ("staff_id", "absence_type", "start_date", "end_date"):
                if not data.get(field):
                    raise ValidationError(f"{field} is required.")

        absence_type = data.get("absence_type")
        if absence_type is not None and absence_type not in ABSENCE_TYPES:
            raise ValidationError(
                f"Invalid absence type '{absence_type}'. "
                f"Valid types: {', '.join(ABSENCE_TYPES)}"
            )

        status = data.get("status")
        if status and status not in VALID_STATUSES:
            raise ValidationError(
                f"Invalid status '{status}'. "
                f"Valid statuses: {', '.join(VALID_STATUSES)}"
            )

        start_raw = data.get("start_date")
        end_raw = data.get("end_date")
        start_dt = _parse_date(start_raw, "start_date") if start_raw else None
        end_dt = _parse_date(end_raw, "end_date") if end_raw else None
        if start_dt and end_dt and end_dt < start_dt:
            raise ValidationError("end_date cannot be before start_date.")

    # -- Create ------------------------------------------------------------

    def create_request(self, **kwargs) -> dict:
        """Create a new absence request.

        Required: staff_id, absence_type, start_date, end_date.
        Optional: reason, status (defaults to 'pending'), approved_by.
        """
        self._validate_request_data(kwargs)
        kwargs.setdefault("status", "pending")

        col_names: list[str] = []
        values: list = []
        for col in _INSERT_COLUMNS:
            val = kwargs.get(col)
            if val is not None:
                col_names.append(col)
                values.append(val)

        cols = ", ".join(col_names)
        placeholders = ", ".join("?" for _ in col_names)

        conn = self._conn()
        try:
            conn.execute(
                f"INSERT INTO absence_requests ({cols}) VALUES ({placeholders})",  # nosec B608
                values,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM absence_requests WHERE id = last_insert_rowid()"
            ).fetchone()
            if not row:
                raise AbsenceRequestError("Created row could not be read back.")
            created = dict(row)
            logger.info(
                "Absence request created: id=%s staff_id=%s type=%s %s→%s",
                created["id"], created.get("staff_id"), created.get("absence_type"),
                created.get("start_date"), created.get("end_date"),
            )
            return created
        except (AbsenceRequestError, ValidationError):
            conn.rollback()
            raise
        except (sqlite3.Error, DatabaseError) as e:
            conn.rollback()
            logger.exception("Failed to create absence request")
            raise AbsenceRequestError(f"Failed to create request: {e}") from e
        finally:
            conn.close()

    # -- Read --------------------------------------------------------------

    def get_request(self, pk: int) -> dict | None:
        """Return request by primary key, or ``None`` if not found."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM absence_requests WHERE id = ?", (pk,)
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.exception("get_request failed: pk=%s", pk)
            raise AbsenceRequestError(f"Failed to fetch request {pk}: {e}") from e
        finally:
            conn.close()

    def list_requests(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List requests with optional filters.

        Supported filters: ``staff_id``, ``absence_type``, ``status``,
        ``approved_by``, ``date_from``, ``date_to``. Results are sorted
        newest-first.
        """
        if limit < 0 or offset < 0:
            raise ValidationError("limit and offset must be non-negative.")

        sql = "SELECT * FROM absence_requests WHERE 1=1"
        params: list = []

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
            logger.debug("list_requests → %d row(s) (filters=%s)", len(rows), filters)
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.exception("list_requests failed: filters=%s", filters)
            raise AbsenceRequestError(f"Failed to list requests: {e}") from e
        finally:
            conn.close()

    # -- Update ------------------------------------------------------------

    def update_request(self, pk: int, **kwargs) -> dict:
        """Update a request record. Only whitelisted columns are written."""
        set_parts: list[str] = []
        values: list = []
        validated: dict = {}
        for col in _UPDATE_COLUMNS:
            if col in kwargs and kwargs[col] is not None:
                set_parts.append(f"{col} = ?")
                values.append(kwargs[col])
                validated[col] = kwargs[col]
        if not set_parts:
            raise ValidationError("No valid fields to update.")
        self._validate_request_data(validated, is_update=True)

        set_parts.append("updated_at = ?")
        values.append(_utcnow_iso())
        values.append(pk)
        set_clause = ", ".join(set_parts)

        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM absence_requests WHERE id = ?", (pk,)
            ).fetchone()
            if not existing:
                raise AbsenceRequestError(f"Request {pk} not found.")

            conn.execute(
                f"UPDATE absence_requests SET {set_clause} WHERE id = ?",  # nosec B608
                values,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM absence_requests WHERE id = ?", (pk,)
            ).fetchone()
            logger.info("Absence request updated: pk=%s fields=%s", pk, list(validated))
            return dict(row) if row else {}
        except (AbsenceRequestError, ValidationError):
            conn.rollback()
            raise
        except (sqlite3.Error, DatabaseError) as e:
            conn.rollback()
            logger.exception("update_request failed: pk=%s", pk)
            raise AbsenceRequestError(f"Failed to update request {pk}: {e}") from e
        finally:
            conn.close()

    # -- State transitions ------------------------------------------------

    def _require_pending(self, pk: int, action: str) -> dict:
        """Fetch a request and verify it is in the 'pending' state."""
        request = self.get_request(pk)
        if not request:
            raise AbsenceRequestError("Request not found.")
        if request["status"] != "pending":
            raise AbsenceRequestError(
                f"Cannot {action} request with status "
                f"'{request['status']}'. Only pending requests can be {action}d."
            )
        return request

    def approve_request(self, pk: int, approved_by: int) -> dict:
        """Approve a pending absence request."""
        self._require_pending(pk, "approve")
        logger.info("Approving request pk=%s by staff_id=%s", pk, approved_by)
        return self.update_request(pk, status="approved", approved_by=approved_by)

    def reject_request(
        self, pk: int, approved_by: int, reason: str | None = None
    ) -> dict:
        """Reject a pending absence request. Optional ``reason`` is stored."""
        self._require_pending(pk, "reject")
        logger.info("Rejecting request pk=%s by staff_id=%s", pk, approved_by)
        updates: dict = {"status": "rejected", "approved_by": approved_by}
        if reason:
            updates["reason"] = reason
        return self.update_request(pk, **updates)

    def cancel_request(self, pk: int, staff_id: int) -> dict:
        """Cancel the caller's own pending request."""
        request = self.get_request(pk)
        if not request:
            raise AbsenceRequestError("Request not found.")
        if request["staff_id"] != staff_id:
            raise AbsenceRequestError("You can only cancel your own requests.")
        if request["status"] != "pending":
            raise AbsenceRequestError(
                f"Cannot cancel request with status '{request['status']}'. "
                "Only pending requests can be cancelled."
            )
        logger.info("Cancelling request pk=%s by staff_id=%s", pk, staff_id)
        return self.update_request(pk, status="cancelled")

    def bulk_approve(self, ids: Iterable[int], approved_by: int) -> dict:
        """Approve many pending requests at once.

        Returns a summary ``{"approved": [...], "failed": [{id, error}, ...]}``.
        Failures are collected rather than raised so one bad id does not
        abort the whole batch.
        """
        approved: list[int] = []
        failed: list[dict] = []
        for pk in ids:
            try:
                self.approve_request(pk, approved_by)
                approved.append(pk)
            except AbsenceRequestError as e:
                failed.append({"id": pk, "error": str(e)})
        logger.info(
            "Bulk approve: %d succeeded, %d failed (by staff_id=%s)",
            len(approved), len(failed), approved_by,
        )
        return {"approved": approved, "failed": failed}

    def bulk_reject(
        self, ids: Iterable[int], approved_by: int, reason: str | None = None
    ) -> dict:
        """Reject many pending requests at once. See ``bulk_approve``."""
        rejected: list[int] = []
        failed: list[dict] = []
        for pk in ids:
            try:
                self.reject_request(pk, approved_by, reason=reason)
                rejected.append(pk)
            except AbsenceRequestError as e:
                failed.append({"id": pk, "error": str(e)})
        logger.info(
            "Bulk reject: %d succeeded, %d failed (by staff_id=%s)",
            len(rejected), len(failed), approved_by,
        )
        return {"rejected": rejected, "failed": failed}

    # -- Delete ------------------------------------------------------------

    def delete_request(self, pk: int) -> bool:
        """Delete a request by id. Returns True on success."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM absence_requests WHERE id = ?", (pk,)
            ).fetchone()
            if not existing:
                raise AbsenceRequestError("Request not found.")
            conn.execute("DELETE FROM absence_requests WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Absence request deleted: pk=%s", pk)
            return True
        except AbsenceRequestError:
            conn.rollback()
            raise
        except (sqlite3.Error, DatabaseError) as e:
            conn.rollback()
            logger.exception("delete_request failed: pk=%s", pk)
            raise AbsenceRequestError(f"Failed to delete request {pk}: {e}") from e
        finally:
            conn.close()

    # -- Queries & stats ---------------------------------------------------

    def count_requests(self, **filters) -> int:
        """Count requests matching filters (same filter keys as list_requests)."""
        sql = "SELECT COUNT(*) AS cnt FROM absence_requests WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"] if row else 0
        except sqlite3.Error as e:
            logger.exception("count_requests failed: filters=%s", filters)
            raise AbsenceRequestError(f"Failed to count requests: {e}") from e
        finally:
            conn.close()

    def get_my_requests(
        self, staff_id: int, *, status: str | None = None
    ) -> list[dict]:
        """Get all requests for a specific staff member, optionally filtered."""
        if staff_id is None:
            raise ValidationError("staff_id is required.")
        filters: dict = {"staff_id": staff_id}
        if status:
            filters["status"] = status
        return self.list_requests(**filters)

    def get_pending_requests(self, *, limit: int = 100) -> list[dict]:
        """Convenience: list all pending requests, newest first."""
        return self.list_requests(status="pending", limit=limit)

    def get_requests_in_range(
        self, start_date: str, end_date: str, *, staff_id: int | None = None
    ) -> list[dict]:
        """Return requests whose date span overlaps ``[start_date, end_date]``.

        An existing request overlaps the window when
        ``request.start_date <= end_date`` AND ``request.end_date >= start_date``.
        """
        start_dt = _parse_date(start_date, "start_date")
        end_dt = _parse_date(end_date, "end_date")
        if end_dt < start_dt:
            raise ValidationError("end_date cannot be before start_date.")

        sql = (
            "SELECT * FROM absence_requests "
            "WHERE start_date <= ? AND end_date >= ?"
        )
        params: list = [end_date, start_date]
        if staff_id is not None:
            sql += " AND staff_id = ?"
            params.append(staff_id)
        sql += " ORDER BY start_date ASC"

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.exception(
                "get_requests_in_range failed: %s..%s staff_id=%s",
                start_date, end_date, staff_id,
            )
            raise AbsenceRequestError(
                f"Failed to query requests in range: {e}"
            ) from e
        finally:
            conn.close()

    def has_overlap(
        self,
        staff_id: int,
        start_date: str,
        end_date: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        """Return True if the staff member has a non-terminal request that
        overlaps the given window. Cancelled/rejected rows are ignored so a
        new request can reuse dates that were previously cancelled.
        """
        overlapping = self.get_requests_in_range(
            start_date, end_date, staff_id=staff_id
        )
        for r in overlapping:
            if exclude_id is not None and r["id"] == exclude_id:
                continue
            if r["status"] in {"cancelled", "rejected"}:
                continue
            return True
        return False

    def get_stats(self) -> dict:
        """Return aggregate counts: total, per-status, per-type."""
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM absence_requests"
            ).fetchone()["cnt"]

            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM absence_requests "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in by_status_rows}
            # Ensure every known status appears, even if zero.
            for s in VALID_STATUSES:
                by_status.setdefault(s, 0)

            by_type_rows = conn.execute(
                "SELECT absence_type, COUNT(*) AS cnt FROM absence_requests "
                "GROUP BY absence_type ORDER BY cnt DESC"
            ).fetchall()
            by_type = [dict(r) for r in by_type_rows]

            return {
                "total": total,
                "by_status": by_status,
                "by_type": by_type,
            }
        except sqlite3.Error as e:
            logger.exception("get_stats failed")
            raise AbsenceRequestError(f"Failed to compute stats: {e}") from e
        finally:
            conn.close()
