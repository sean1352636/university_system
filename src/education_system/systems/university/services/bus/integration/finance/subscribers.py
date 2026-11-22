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
from education_system.systems.university.services.bus.integration.publishing import log_and_publish

def _lookup_program_fee(course_code: str | None,
                       academic_year: str | None) -> float | None:
    if not course_code:
        return None
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='program_fees'"
            ).fetchone()
            if not tbl:
                return None
            sql = "SELECT amount FROM program_fees WHERE course = ?"
            params: list[Any] = [course_code]
            if academic_year:
                sql += " AND (academic_year = ? OR academic_year IS NULL)"
                params.append(academic_year)
            sql += " ORDER BY academic_year DESC LIMIT 1"
            row = conn.execute(sql, tuple(params)).fetchone()
            return float(row[0]) if row and row[0] is not None else None
    except Exception:
        return None

_REFUND_PREVIEW_SQL = """
CREATE TABLE IF NOT EXISTS refund_previews (
    preview_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    course_code TEXT NOT NULL,
    amount      REAL NOT NULL DEFAULT 0,
    reason      TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

def publish_grant_decision(application_id: int, *, status: str,
                           grant_name: str | None = None,
                           awarded_amount: float = 0.0,
                           pi_id: str | None = None,
                           grant_period_start: str | None = None,
                           grant_period_end: str | None = None) -> None:
    """Publish a grant decision so finance can ledger the award.

    Origin: ``research_grants.accept_award``. The PI
    becomes the budget owner; subscribers ledger the awarded
    amount via ``finance_bus.raise_charge`` with
    ``reference_id='grant:<id>'`` so ``finance_bus.grant_balance``
    can subtract spend from the same ref family.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="research",
        action="grant_decided",
        application_id=int(application_id),
        status=status,
        grant_name=grant_name,
        awarded_amount=float(awarded_amount or 0),
        pi_id=pi_id,
        grant_period_start=grant_period_start,
        grant_period_end=grant_period_end,
    )

def _on_grant_decided(**payload: Any) -> None:
    if payload.get("action") != "grant_decided":
        return
    if (payload.get("status") or "").lower() not in (
            "approved", "awarded", "accepted"):
        return
    amount = float(payload.get("awarded_amount") or 0)
    if amount <= 0:
        return
    pi_id = payload.get("pi_id")
    application_id = payload.get("application_id")
    if not pi_id:
        return
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        # Negative-amount charge represents a *credit* into the
        # grant's tracked balance. We post it against the PI so the
        # row appears in their finance summary, with reference_id
        # tied to the grant so grant_balance() reads it back.
        raise_charge(
            pi_id, -amount,
            source="research_grant",
            description=(
                f"Grant award credit: {payload.get('grant_name') or application_id}"
            ),
            reference_id=f"grant:{application_id}",
        )
    except Exception as exc:
        logger.debug("grant→finance ledger failed: %s", exc)
