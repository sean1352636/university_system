"""Focused components extracted from the legacy integration bus."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.events.in_process import (
    EVENT_CASE_OPENED,
    EVENT_CERT_CHANGED,
    EVENT_CHARGE_RAISED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_EXAM_CHANGED,
    EVENT_INCIDENT_LOGGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED,
    EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_TERM_CHANGED,
    publish,
    subscribe,
)

logger = logging.getLogger(__name__)

def _on_staff_availability_changed(**payload: Any) -> None:
    if payload.get("action") not in ("approved", "cancelled"):
        return
    staff_id = payload.get("staff_id")
    start = payload.get("start_date")
    end = payload.get("end_date")
    if not (staff_id and start and end):
        return

    if payload.get("action") == "approved":
        # CoverManager: open a cover request for each affected day.
        try:
            from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.cover_manager import (
                CoverManager,
            )
            for d in _date_range(start, end):
                try:
                    CoverManager.create_request(
                        requester_id=str(staff_id),
                        cover_date=d,
                        reason=f"{payload.get('source_kind', 'leave')} approved",
                        priority="normal",
                    )
                except Exception as exc:
                    logger.debug("cover create failed for %s: %s", d, exc)
        except Exception as exc:
            logger.debug("cover_manager unavailable: %s", exc)

        # Payroll: tag the affected period(s) so prorate calc picks them up.
        _tag_payroll_leave(str(staff_id), start, end,
                           leave_type=payload.get("leave_type"))

_MERIT_BANDS = (
    (4.5, 0.05),  # outstanding → +5%
    (4.0, 0.03),  # exceeds      → +3%
    (3.5, 0.015), # solid        → +1.5%
)

def _on_appraisal_completed(**payload: Any) -> None:
    if payload.get("action") != "appraisal_completed":
        return
    user_id = payload.get("user_id")
    rating = payload.get("rating")
    cycle_id = payload.get("cycle_id")
    if not user_id or rating is None:
        return

    pct = next((p for thr, p in _MERIT_BANDS if rating >= thr), 0.0)
    if pct <= 0:
        return

    try:
        # Look up current salary, then propose an allowance row.
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(salary_override, salary) FROM staff_contracts "
                "WHERE LOWER(COALESCE(status, 'active')) = 'active' AND (user_id = ? OR user_id = "
                "(SELECT username FROM users WHERE CAST(id AS TEXT) = ?)) "
                "ORDER BY start_date DESC LIMIT 1",
                (str(user_id), str(user_id)),
            ).fetchone()
            salary = float(row[0]) if row and row[0] else 0.0
        if salary <= 0:
            return
        amount = round(salary * pct, 2)
        from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.payroll_manager import (
            PayrollManager,
        )
        PayrollManager.add_allowance(
            user_id=str(user_id),
            allowance_type="merit_proposal",
            amount=amount,
            description=(
                f"Proposed merit (cycle {cycle_id}, rating {rating:.2f}). "
                "Pending HR approval — set is_active=1 to apply."
            ),
            is_active=False,
        )
    except Exception as exc:
        logger.debug("merit-pay proposal failed: %s", exc)

def _is_role_critical(user_id: str | None) -> bool:
    if not user_id:
        return False
    critical_titles = ("compliance", "auditor", "safety", "first aid", "lab manager")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT job_title FROM staff_profiles WHERE user_id = ? OR user_id = "
                "(SELECT username FROM users WHERE CAST(id AS TEXT) = ?) LIMIT 1",
                (str(user_id), str(user_id)),
            ).fetchone()
            if not row or not row[0]:
                return False
            title = row[0].lower()
            return any(k in title for k in critical_titles)
    except Exception:
        return False

def _date_range(start: str, end: str):
    try:
        s = datetime.strptime(start[:10], "%Y-%m-%d").date()
        e = datetime.strptime(end[:10], "%Y-%m-%d").date()
    except Exception:
        return
    cur = s
    while cur <= e:
        yield cur.isoformat()
        cur += timedelta(days=1)

def _tag_payroll_leave(user_id: str, start: str, end: str,
                       *, leave_type: str | None) -> None:
    """Best-effort: stamp open payroll period with a leave note for prorate."""
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='payroll_periods'"
            ).fetchone()
            if not tbl:
                return
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(payroll_periods)").fetchall()}
            if "leave_notes" not in cols:
                conn.execute(
                    "ALTER TABLE payroll_periods ADD COLUMN leave_notes TEXT"
                )
            note = f"{user_id}:{leave_type or 'leave'}:{start}..{end};"
            conn.execute(
                "UPDATE payroll_periods "
                "SET leave_notes = COALESCE(leave_notes, '') || ? "
                "WHERE status = 'open' "
                "  AND start_date <= ? AND end_date >= ?",
                (note, end, start),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("payroll leave tag failed: %s", exc)
