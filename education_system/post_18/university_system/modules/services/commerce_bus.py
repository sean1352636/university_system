"""Cross-domain commerce helpers.

Single small surface used by Cinema, Gym, Restaurant and Shop so that
every commerce transaction:

  * posts to ``finance_bus`` (one ledger across the institution),
  * earns points via ``loyalty_bus`` (one tier across all venues),
  * gets a consistent SU-member / loyalty-tier discount applied at the
    point of sale via ``price_for``.

This module deliberately doesn't own any tables — it composes
``finance_bus`` + ``loyalty_bus`` + ``student_union_bus`` and exposes
``post_sale`` / ``price_for`` / ``customer_tier`` / ``apply_perk``.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
)
from education_system.post_18.university_system.modules.services import finance_bus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

_SU_MEMBER_DISCOUNT = 0.10  # 10% off for any active SU club member
_TIER_DISCOUNT = {
    "Bronze":   0.00,
    "Silver":   0.05,
    "Gold":     0.10,
    "Platinum": 0.15,
}


def _su_member(student_id: str | int) -> bool:
    try:
        from education_system.post_18.university_system.modules.services import (
            student_union_bus,
        )
        return bool(student_union_bus.list_clubs_for(student_id))
    except Exception:
        return False


def customer_tier(student_id: str | int) -> str:
    """Return the student's loyalty tier across the institution.

    Reads from ``loyalty_bus.tier`` if present, otherwise falls back to
    ``restaurant_customers.loyalty_tier`` so the existing tier column
    isn't ignored.
    """
    if not student_id:
        return "Bronze"
    try:
        from education_system.post_18.university_system.modules.services import (
            loyalty_bus,
        )
        return loyalty_bus.tier(student_id)
    except Exception:
        pass
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT loyalty_tier FROM restaurant_customers "
                "WHERE customer_id = ? OR student_id = ? LIMIT 1",
                (str(student_id), str(student_id)),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return "Bronze"


def price_for(student_id: str | int | None,
              base: float,
              *,
              source: str | None = None) -> tuple[float, dict[str, Any]]:
    """Apply institution-wide discounts to ``base``.

    Returns ``(final_price, breakdown)`` where ``breakdown`` lists each
    discount component. Always safe — falls back to ``base`` on any
    error. ``source`` is informational only (e.g. ``"cinema"``).
    """
    base_amt = float(base or 0)
    if base_amt <= 0 or not student_id:
        return base_amt, {"base": base_amt, "discounts": [], "final": base_amt}

    discounts: list[dict[str, Any]] = []
    pct = 0.0
    if _su_member(student_id):
        discounts.append({"kind": "su_member", "pct": _SU_MEMBER_DISCOUNT})
        pct += _SU_MEMBER_DISCOUNT
    tier = customer_tier(student_id)
    tier_pct = _TIER_DISCOUNT.get(tier, 0.0)
    if tier_pct:
        discounts.append({"kind": "tier", "tier": tier, "pct": tier_pct})
        pct += tier_pct

    pct = min(pct, 0.30)  # cap stacked discounts at 30%
    final = round(base_amt * (1 - pct), 2)
    return final, {
        "base": base_amt, "discounts": discounts,
        "pct": pct, "final": final, "source": source,
    }


# ---------------------------------------------------------------------------
# Sale posting
# ---------------------------------------------------------------------------

def post_sale(
    student_id: str | int | None,
    *,
    source: str,
    amount: float,
    description: str,
    reference_id: str | None = None,
    earn_points: bool = True,
    invoice: bool = False,
    processed_by: str | None = None,
) -> dict[str, Any]:
    """Single entry-point used by every commerce module.

    Writes a finance row + earns loyalty points. Returns
    ``{"tx_id", "points_earned", "kind"}``.

    Two semantic modes:

    * ``invoice=False`` (default) — already paid at the till. Calls
      :func:`finance_bus.record_paid_sale` which writes a
      ``transaction_type='sale'`` row that does *not* mutate the
      running balance. Use for cinema bookings, restaurant orders,
      shop purchases, gym membership signup.
    * ``invoice=True`` — genuinely deferred obligation. Calls
      :func:`finance_bus.raise_charge` which lowers the balance.
      Use for things like a monthly subscription that will be
      billed later. Housing rent has its own helper
      (``housing_finance.post_rent_charge``); don't double up.

    Walk-ins (no ``student_id``) return the no-op shape with no
    finance/loyalty side-effects.
    """
    out: dict[str, Any] = {
        "tx_id": None, "points_earned": 0,
        "kind": "invoice" if invoice else "sale",
    }
    amt = float(amount or 0)
    if not student_id or amt <= 0:
        return out

    if invoice:
        out["tx_id"] = finance_bus.raise_charge(
            student_id, amt,
            source=source,
            description=description,
            reference_id=reference_id,
            processed_by=processed_by or source,
        )
    else:
        out["tx_id"] = finance_bus.record_paid_sale(
            student_id, amt,
            source=source,
            description=description,
            reference_id=reference_id,
            processed_by=processed_by or source,
        )

    if earn_points:
        try:
            from education_system.post_18.university_system.modules.services import (
                loyalty_bus,
            )
            pts = int(amt)
            loyalty_bus.add_points(
                student_id, source=source, points=pts,
                reference_id=reference_id,
                description=description,
            )
            out["points_earned"] = pts
        except Exception as exc:
            logger.debug("post_sale loyalty add failed: %s", exc)

    return out


def resolve_student(*, email: str | None = None,
                    customer_id: str | None = None,
                    user_id: str | int | None = None) -> str | None:
    """Best-effort lookup of a student_id from any of the identifiers
    a commerce module is likely to have. Returns ``None`` if no
    match — caller skips the loyalty/finance side-effects.

    Order: explicit ``student_id`` field on a customer-row table,
    then ``students.email``, then ``users.id`` → ``users.student_id``.
    """
    try:
        with get_connection() as conn:
            if customer_id:
                # restaurant_customers may carry an explicit student_id
                # link (added by the restaurant migration); prefer it.
                try:
                    row = conn.execute(
                        "SELECT student_id FROM restaurant_customers "
                        "WHERE customer_id = ? AND student_id IS NOT NULL "
                        "LIMIT 1",
                        (str(customer_id),),
                    ).fetchone()
                    if row and row[0]:
                        return str(row[0])
                except Exception:
                    pass
            if email:
                row = conn.execute(
                    "SELECT student_id FROM students WHERE email = ? "
                    "LIMIT 1",
                    (email,),
                ).fetchone()
                if row and row[0]:
                    return str(row[0])
            if user_id is not None:
                row = conn.execute(
                    "SELECT student_id FROM users WHERE id = ? LIMIT 1",
                    (user_id,),
                ).fetchone()
                if row and row[0]:
                    return str(row[0])
    except Exception as exc:
        logger.debug("resolve_student failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Tier-based perks (read-only helpers consumed by venue GUIs)
# ---------------------------------------------------------------------------

def apply_perk(student_id: str | int | None,
               perk: str) -> tuple[bool, str | None]:
    """Return ``(granted, reason)`` for cross-venue perks.

    Known perks (advisory; venue code decides what to do):

    * ``"cinema_seat_upgrade"``    — Gold+ tier
    * ``"shop_free_delivery"``     — Silver+ tier
    * ``"gym_guest_pass"``         — Platinum tier (one per month)
    * ``"restaurant_priority"``    — Gold+ tier
    """
    if not student_id:
        return False, "no student"
    tier = customer_tier(student_id)
    rank = {"Bronze": 0, "Silver": 1, "Gold": 2, "Platinum": 3}.get(tier, 0)
    rules = {
        "cinema_seat_upgrade": (2, "Gold tier or higher"),
        "shop_free_delivery":  (1, "Silver tier or higher"),
        "gym_guest_pass":      (3, "Platinum tier"),
        "restaurant_priority": (2, "Gold tier or higher"),
    }
    if perk not in rules:
        return False, f"unknown perk {perk!r}"
    threshold, label = rules[perk]
    if rank >= threshold:
        return True, f"{tier} tier qualifies ({label})"
    return False, f"requires {label}; current tier {tier}"


__all__ = [
    "post_sale", "price_for", "customer_tier", "apply_perk",
    "resolve_student",
]
