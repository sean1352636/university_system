"""Finance adapter — record assignment late penalties as fines.

Wraps ``shared/utils/finance_integration.record_payment_to_finance``
so a late submission produces a pending-fine row in the central
finance ``payments`` table without the assignment GUI needing to
know about its schema.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def calc_late_penalty(
    days_late: int,
    max_marks: int | float,
    penalty_per_day_pct: float,
    *,
    fee_per_percent: float = 1.0,
) -> float:
    """Map % grade-penalty into a monetary fine.

    Mirrors the standard university policy: ``penalty_per_day_pct`` of
    the assignment's max marks is forfeited per day, and we charge
    ``fee_per_percent`` GBP per percentage-point lost. Capped so a
    submission can never owe more than the assignment is worth.
    """
    if days_late <= 0 or penalty_per_day_pct <= 0 or max_marks <= 0:
        return 0.0
    pct_lost = min(days_late * penalty_per_day_pct, 100.0)
    return round(pct_lost * fee_per_percent, 2)


def record_late_penalty(
    *,
    student_id: str,
    submission_id: int,
    assignment_title: str,
    days_late: int,
    amount: float,
    created_by: str | None = None,
) -> int | None:
    """Record a pending late-submission fine in the finance system.

    Returns the finance ``payment_id`` on success, ``None`` on
    failure or when ``amount`` is non-positive.
    """
    if amount <= 0:
        return None
    try:
        from education_system.systems.university.infrastructure.utils.finance_integration import (
            record_payment_to_finance,
        )
    except ImportError as exc:
        logger.debug("finance_integration not available: %s", exc)
        return None

    try:
        return record_payment_to_finance(
            student_id=str(student_id),
            amount=float(amount),
            payment_method="Pending",
            transaction_source="Assignments",
            transaction_ref=f"LATE-{submission_id}",
            status="pending",
            notes=(
                f"Late submission penalty for '{assignment_title}' "
                f"({days_late} day(s) late)"
            ),
            created_by=created_by,
        )
    except Exception as exc:
        logger.warning(
            "record_late_penalty failed for submission=%s: %s",
            submission_id, exc,
        )
        return None
