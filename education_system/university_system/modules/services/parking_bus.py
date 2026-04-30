"""Cross-domain parking service.

Parking permits + violations route money through finance_bus,
suspensions through finance_bus.place_hold, and repeated violations
through cases_bus.open_case.

Public surface:

* ``issue_permit(holder_id, plate, valid_until, fee)``
* ``suspend_permit(permit_id, reason)``
* ``record_violation(plate, kind, fine_amount, *, holder_id=, location=)``
  → on the third unpaid violation in 12mo, opens a DP case.
* ``list_permits_for(holder_id)``
* ``outstanding_parking_charges(holder_id)``
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_REPEAT_THRESHOLD = 3      # violations before DP escalation
_REPEAT_WINDOW_DAYS = 365


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.university_system.modules.domain.academics.gui._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("parking bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Permits
# ---------------------------------------------------------------------------

def issue_permit(holder_id: str | int,
                 plate: str,
                 *,
                 zone: str = "general",
                 permit_type: str = "annual",
                 valid_from: str | None = None,
                 valid_until: str | None = None,
                 fee: float | None = None,
                 full_name: str | None = None,
                 email: str | None = None,
                 issued_by: str | None = None) -> int | None:
    """Insert a permits row and (optionally) raise the fee charge.

    ``parking_permits.user_id`` is FK→users.id; we resolve from the
    student code when needed. ``vehicle_id`` is FK→vehicles.vehicle_id;
    callers must register the vehicle first or this returns None.
    """
    if not holder_id or not plate:
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    start = (valid_from or today)[:10]
    end = (valid_until
           or (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"))[:10]

    sid = str(holder_id)
    user_int_id: int | None = None
    try:
        user_int_id = int(sid)
    except ValueError:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ? LIMIT 1",
                    (sid,),
                ).fetchone()
                if row:
                    user_int_id = int(row[0])
        except Exception:
            user_int_id = None
    if user_int_id is None:
        logger.warning("issue_permit: cannot resolve user_id for %s",
                       holder_id)
        return None

    pid: int | None = None
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO parking_permits "
                "(user_id, full_name, email, zone, permit_type, "
                " start_date, end_date, active_status, vehicle_id, "
                " issue_date, expiry_date, fee_paid, status, "
                " student_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, "
                "        'active', ?, ?, ?)",
                (user_int_id, full_name, email, zone, permit_type,
                 start, end, plate, today, end,
                 float(fee) if fee else 0.0,
                 sid,
                 today + ' 00:00:00', today + ' 00:00:00'),
            )
            pid = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("issue_permit failed: %s", exc)
        return None

    if fee and fee > 0:
        try:
            from education_system.university_system.modules.services.finance_bus import (
                raise_charge,
            )
            raise_charge(
                holder_id, float(fee),
                source="parking_permit",
                description=(
                    f"Parking permit fee — {permit_type} ({zone}); "
                    f"plate {plate}"
                ),
                reference_id=f"permit:{pid}",
                processed_by=issued_by or "parking_management",
            )
        except Exception:
            pass
    return pid


def suspend_permit(permit_id: int, *,
                   reason: str = "violations",
                   suspended_by: str | None = None) -> bool:
    """Mark a permit suspended and place a finance hold so the campus
    gate (or any subscriber of EVENT_HOLD_CHANGED) refuses access."""
    if not permit_id:
        return False
    holder_id: str | None = None
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM parking_permits WHERE permit_id = ?",
                (int(permit_id),),
            ).fetchone()
            if not row:
                return False
            holder_id = row[0]
            conn.execute(
                "UPDATE parking_permits SET active_status = 0, "
                "       status = 'suspended', "
                "       updated_at = CURRENT_TIMESTAMP "
                "WHERE permit_id = ?",
                (int(permit_id),),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("suspend_permit failed: %s", exc)
        return False

    # Hold doubles as the campus-gate block.
    try:
        from education_system.university_system.modules.services.finance_bus import (
            place_hold,
        )
        place_hold(
            holder_id,
            reason=f"Parking suspension — {reason}",
            source="parking_suspension",
            reference_id=f"permit:{permit_id}",
            placed_by=suspended_by or "parking_management",
        )
    except Exception:
        pass
    return True


def list_permits_for(holder_id: str | int) -> list[dict[str, Any]]:
    if not holder_id:
        return []
    out: list[dict[str, Any]] = []
    sid = str(holder_id)
    try:
        with get_connection() as conn:
            # Same resolution as issue_permit; also accept student_id
            # as a fallback so callers passing the student code still
            # see their permits.
            user_int_id: int | None = None
            try:
                user_int_id = int(sid)
            except ValueError:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ? LIMIT 1",
                    (sid,),
                ).fetchone()
                if row:
                    user_int_id = int(row[0])
            for r in conn.execute(
                "SELECT permit_id, vehicle_id AS plate, zone, permit_type, "
                "       start_date, end_date, fee_paid, status, active_status "
                "FROM parking_permits "
                "WHERE user_id = ? OR student_id = ? "
                "ORDER BY end_date DESC",
                (user_int_id, sid),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_permits_for failed: %s", exc)
    return out


# ---------------------------------------------------------------------------
# Violations
# ---------------------------------------------------------------------------

def record_violation(plate: str,
                     kind: str,
                     fine_amount: float,
                     *,
                     holder_id: str | int | None = None,
                     location: str | None = None,
                     officer_id: int | None = None,
                     issued_by: str | None = None) -> dict[str, Any]:
    """Log a violation, raise the fine in Finance, and on repeat
    offenders open a Disciplinary Portal case.

    Returns ``{ok, violation_id, charge_tx, escalated_case_id}``.
    """
    if not plate or not kind:
        return {"ok": False, "reason": "plate + kind required"}
    today = datetime.now().strftime("%Y-%m-%d")
    out: dict[str, Any] = {"ok": True, "violation_id": None,
                            "charge_tx": None, "escalated_case_id": None}

    # If holder_id wasn't given, look it up by plate.
    resolved_holder: str | None = (
        str(holder_id) if holder_id is not None else None
    )
    try:
        with get_connection() as conn:
            if resolved_holder is None:
                row = conn.execute(
                    "SELECT user_id FROM parking_permits "
                    "WHERE vehicle_id = ? "
                    "ORDER BY end_date DESC LIMIT 1",
                    (plate,),
                ).fetchone()
                if row:
                    resolved_holder = row[0]
            cur = conn.execute(
                "INSERT INTO parking_violations "
                "(license_plate, violation_type, violation_date, "
                " fine_amount, payment_status, location, officer_id, "
                " issued_by, status) "
                "VALUES (?, ?, ?, ?, 'unpaid', ?, ?, ?, 'open')",
                (plate, kind, today, float(fine_amount),
                 location, officer_id, issued_by),
            )
            out["violation_id"] = cur.lastrowid
            conn.commit()
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}

    # Fine to Finance.
    if resolved_holder and fine_amount and fine_amount > 0:
        try:
            from education_system.university_system.modules.services.finance_bus import (
                raise_charge,
            )
            out["charge_tx"] = raise_charge(
                resolved_holder, float(fine_amount),
                source="parking_fine",
                description=f"Parking fine: {kind} ({plate})",
                reference_id=f"violation:{out['violation_id']}",
                processed_by=issued_by or "parking_management",
            )
        except Exception:
            pass

    # Repeat-offender check — count by plate (independent of whether
    # a permit row exists), since unpermitted plates are exactly the
    # offenders we want to escalate.
    if resolved_holder:
        try:
            with get_connection() as conn:
                cnt_row = conn.execute(
                    "SELECT COUNT(*) FROM parking_violations "
                    "WHERE license_plate = ? "
                    "  AND violation_date >= date('now', ?) "
                    "  AND COALESCE(payment_status,'unpaid') != 'paid'",
                    (plate, f"-{_REPEAT_WINDOW_DAYS} days"),
                ).fetchone()
                count = int(cnt_row[0] or 0) if cnt_row else 0
            if count >= _REPEAT_THRESHOLD:
                from education_system.university_system.modules.services.cases_bus import (
                    open_case,
                )
                out["escalated_case_id"] = open_case(
                    kind="disciplinary",
                    subject_id=resolved_holder,
                    offense_type="Parking — repeated violations",
                    severity="Minor",
                    description=(
                        f"{count} unpaid parking violations in last "
                        f"{_REPEAT_WINDOW_DAYS} days; latest: {kind} "
                        f"({plate})."
                    ),
                    opened_by="parking_management",
                )
        except Exception as exc:
            logger.debug("parking repeat escalation failed: %s", exc)

    _publish(
        "parking.violation",
        violation_id=out["violation_id"], plate=plate,
        kind=kind, fine_amount=float(fine_amount),
        holder_id=resolved_holder,
        escalated_case_id=out["escalated_case_id"],
    )
    return out


def outstanding_parking_charges(holder_id: str | int) -> list[dict[str, Any]]:
    if not holder_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            for r in conn.execute(
                "SELECT transaction_id, amount, description, reference_id, "
                "       created_at "
                "FROM student_finance_transactions "
                "WHERE student_id = ? "
                "  AND transaction_type = 'charge' "
                "  AND COALESCE(reference_id,'') LIKE 'violation:%' "
                "  AND created_at >= date('now', '-365 days') "
                "ORDER BY created_at DESC",
                (str(holder_id),),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("outstanding_parking_charges failed: %s", exc)
    return out


__all__ = [
    "issue_permit", "suspend_permit", "list_permits_for",
    "record_violation", "outstanding_parking_charges",
]
