"""Cross-domain helpers that route housing money through finance_bus.

Mirrors the ``student_union_bus`` pattern. Lets housing GUIs post rent,
deposit and damage charges, and place / release arrears holds, without
having to touch the finance schema directly. All writes go through
``finance_bus`` so the same ``finance.charge.raised`` /
``finance.hold.changed`` events fire that the Finance GUI already
subscribes to.

Public surface:

* ``post_rent_charge(student_id, assignment_id, amount, ...)``
* ``post_deposit_charge(student_id, assignment_id, amount)``
* ``post_damage_charge(student_id, assignment_id, amount, description)``
* ``place_arrears_hold(student_id, assignment_id, amount)``
* ``release_arrears_holds_for(student_id, assignment_id=None)``
* ``check_overdue_assignments(days_overdue=14)``
* ``can_assign_room(student_id)`` → ``(bool, reason)``
* ``list_housing_charges(student_id)``
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.services import finance_bus

logger = logging.getLogger(__name__)


_RENT_SOURCE = "housing_rent"
_DEPOSIT_SOURCE = "housing_deposit"
_DAMAGE_SOURCE = "housing_damage"
_ARREARS_SOURCE = "housing_arrears"


def _ref(assignment_id: str | int) -> str:
    return f"asg:{assignment_id}"


# ---------------------------------------------------------------------------
# Charges
# ---------------------------------------------------------------------------

def post_rent_charge(
    student_id: str | int,
    assignment_id: str | int,
    amount: float,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
    processed_by: str | None = None,
) -> int | None:
    """Post a rent debit through finance_bus."""
    if not amount or amount <= 0:
        return None
    desc = "Housing rent"
    if period_start and period_end:
        desc = f"Housing rent {period_start} → {period_end}"
    return finance_bus.raise_charge(
        student_id, float(amount),
        source=_RENT_SOURCE,
        description=desc,
        reference_id=_ref(assignment_id),
        processed_by=processed_by or "housing",
    )


def post_deposit_charge(
    student_id: str | int,
    assignment_id: str | int,
    amount: float,
    *,
    processed_by: str | None = None,
) -> int | None:
    if not amount or amount <= 0:
        return None
    return finance_bus.raise_charge(
        student_id, float(amount),
        source=_DEPOSIT_SOURCE,
        description="Housing deposit",
        reference_id=_ref(assignment_id),
        processed_by=processed_by or "housing",
    )


def post_damage_charge(
    student_id: str | int,
    assignment_id: str | int,
    amount: float,
    description: str,
    *,
    processed_by: str | None = None,
) -> int | None:
    if not amount or amount <= 0:
        return None
    return finance_bus.raise_charge(
        student_id, float(amount),
        source=_DAMAGE_SOURCE,
        description=description or "Housing damage charge",
        reference_id=_ref(assignment_id),
        processed_by=processed_by or "housing",
    )


# ---------------------------------------------------------------------------
# Arrears holds
# ---------------------------------------------------------------------------

def place_arrears_hold(
    student_id: str | int,
    assignment_id: str | int,
    amount: float,
    *,
    placed_by: str | None = None,
) -> int | None:
    """Place an arrears hold. Idempotent: if an active hold already
    exists for this assignment, return its id."""
    sid = str(student_id)
    ref = _ref(assignment_id)
    for h in finance_bus.list_active_holds(sid):
        if h.get("source") == _ARREARS_SOURCE and h.get("reference_id") == ref:
            return int(h["hold_id"])
    return finance_bus.place_hold(
        sid,
        reason=f"Rent arrears on assignment {assignment_id}",
        source=_ARREARS_SOURCE,
        amount=float(amount or 0),
        reference_id=ref,
        placed_by=placed_by or "housing",
    )


def release_arrears_holds_for(
    student_id: str | int,
    assignment_id: str | int | None = None,
    *,
    released_by: str | None = None,
) -> int:
    """Release active housing-arrears holds for the student.

    If ``assignment_id`` is given, only holds matching that reference
    are released. Returns the number of holds released.
    """
    sid = str(student_id)
    target_ref = _ref(assignment_id) if assignment_id is not None else None
    released = 0
    for h in finance_bus.list_active_holds(sid):
        if h.get("source") != _ARREARS_SOURCE:
            continue
        if target_ref and h.get("reference_id") != target_ref:
            continue
        if finance_bus.release_hold(int(h["hold_id"]),
                                    released_by=released_by or "housing"):
            released += 1
    return released


# ---------------------------------------------------------------------------
# Overdue scan
# ---------------------------------------------------------------------------

def check_overdue_assignments(days_overdue: int = 14) -> list[dict[str, Any]]:
    """Return active assignments whose most recent rent payment is
    older than ``days_overdue`` days (or has none).

    This is a read-only scan — the caller decides whether to call
    ``place_arrears_hold`` on each row. Best-effort: returns ``[]`` on
    any DB error.
    """
    out: list[dict[str, Any]] = []
    sql = """
    SELECT a.assignment_id, a.student_id, a.monthly_rent,
           MAX(p.payment_date) AS last_payment
      FROM housing_assignments a
      LEFT JOIN payments p
        ON p.reference_id = a.assignment_id
       AND p.source_type = 'housing'
       AND p.status = 'Completed'
     WHERE a.status = 'Active'
     GROUP BY a.assignment_id
    HAVING last_payment IS NULL
        OR julianday('now') - julianday(last_payment) > ?
    """
    try:
        with get_connection() as conn:
            for r in conn.execute(sql, (int(days_overdue),)).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("check_overdue_assignments failed: %s", exc)
    return out


# ---------------------------------------------------------------------------
# Hold-aware gating
# ---------------------------------------------------------------------------

def can_assign_room(student_id: str | int) -> tuple[bool, str | None]:
    """Return ``(allowed, reason)``. Blocks assignment when the student
    has an active arrears or other finance hold."""
    if not student_id:
        return True, None
    holds = finance_bus.list_active_holds(student_id)
    if not holds:
        return True, None
    sources = sorted({h.get("source", "?") for h in holds})
    return False, f"Active finance hold(s): {', '.join(sources)}"


# ---------------------------------------------------------------------------
# Read helpers (for unified GUI views)
# ---------------------------------------------------------------------------

def list_housing_charges(student_id: str | int,
                         *, days: int = 365) -> list[dict[str, Any]]:
    """Return housing-source charges within the last ``days`` days."""
    if not student_id:
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
                "  AND COALESCE(reference_id, '') LIKE 'asg:%' "
                "  AND created_at >= date('now', ?) "
                "ORDER BY created_at DESC",
                (str(student_id), f"-{int(days)} days"),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_housing_charges(%s) failed: %s", student_id, exc)
    return out


__all__ = [
    "post_rent_charge",
    "post_deposit_charge",
    "post_damage_charge",
    "place_arrears_hold",
    "release_arrears_holds_for",
    "check_overdue_assignments",
    "can_assign_room",
    "list_housing_charges",
]
