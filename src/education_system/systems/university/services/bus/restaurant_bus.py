"""Cross-domain restaurant / dining service.

Pushes restaurant POS, meal-plan top-ups, and SU/staff discounts
through the existing ``finance_bus`` rather than running a parallel
ledger. Daily menus persist on the academic calendar. Public surface:

* ``top_up_meal_plan(student_id, amount)`` — credit the meal plan;
  posts a negative-amount finance row with ``source='meal_plan_topup'``.
* ``record_pos_transaction(student_id, amount, items)`` — debit a
  POS spend; posts ``source='restaurant_pos'``.
* ``apply_su_discount(student_id, amount)`` → ``(discounted, applied)``;
  reads SU membership via ``student_union_bus.is_member_of`` (any
  active club).
* ``apply_staff_subsidy(staff_id, amount)`` → ``(discounted, applied)``.
* ``meal_plan_balance(student_id)`` — derived from finance txs.
* ``publish_menu_for(date, location, menu_items)`` — calendar event.
* ``menu_for(date)`` — read recent menu rows.
"""

from __future__ import annotations

import logging
import json
import uuid
from datetime import date as _date, datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_SU_DISCOUNT = 0.10           # 10% off for any active SU member
_STAFF_SUBSIDY = 0.20         # 20% off for active staff
_MEAL_PLAN_SOURCES = ("meal_plan_topup", "restaurant_pos")


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.systems.university.interfaces.gui.academics._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("restaurant bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Money flow
# ---------------------------------------------------------------------------

def top_up_meal_plan(student_id: str | int, amount: float,
                     *, processed_by: str | None = None) -> int | None:
    """Credit a student's meal plan. Returns the finance tx_id."""
    if not student_id or not amount or float(amount) <= 0:
        return None
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        # Negative-amount charge represents a credit.
        tx = raise_charge(
            student_id, -float(amount),
            source="meal_plan_topup",
            description=f"Meal-plan top-up of £{float(amount):,.2f}",
            reference_id=f"topup:{uuid.uuid4().hex[:10]}",
            processed_by=processed_by or "restaurant",
        )
    except Exception as exc:
        logger.warning("top_up_meal_plan failed: %s", exc)
        return None
    _publish(
        "restaurant.meal_plan.changed",
        student_id=str(student_id),
        action="top_up", amount=float(amount), tx_id=tx,
    )
    return tx


def record_pos_transaction(student_id: str | int, amount: float,
                           *, items: list | None = None,
                           location: str | None = None,
                           processed_by: str | None = None) -> int | None:
    """Debit a POS spend against the student's finance account."""
    if not student_id or not amount or float(amount) <= 0:
        return None
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        bits = ", ".join((items or [])[:3]) if items else ""
        descr = ("Restaurant POS"
                 + (f" — {bits}" if bits else "")
                 + (f" ({location})" if location else ""))
        tx = raise_charge(
            student_id, float(amount),
            source="restaurant_pos",
            description=descr,
            reference_id=f"pos:{uuid.uuid4().hex[:10]}",
            processed_by=processed_by or "restaurant",
        )
    except Exception as exc:
        logger.warning("record_pos_transaction failed: %s", exc)
        return None
    _publish(
        "restaurant.meal_plan.changed",
        student_id=str(student_id),
        action="pos_spend", amount=float(amount), tx_id=tx,
        items=items, location=location,
    )
    return tx


def meal_plan_balance(student_id: str | int) -> float:
    """Net meal-plan balance: top-ups (negative txs) minus POS spend."""
    if not student_id:
        return 0.0
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(-amount), 0) AS bal "
                "FROM student_finance_transactions "
                "WHERE student_id = ? "
                "  AND transaction_type = 'charge' "
                "  AND COALESCE(reference_id, '') != '' "
                "  AND ( "
                "    description LIKE 'Meal-plan top-up%' "
                "    OR description LIKE 'Restaurant POS%' "
                "  )",
                (str(student_id),),
            ).fetchone()
            return float(row[0] or 0)
    except Exception as exc:
        logger.warning("meal_plan_balance(%s) failed: %s", student_id, exc)
        return 0.0


# ---------------------------------------------------------------------------
# Discounts
# ---------------------------------------------------------------------------

def apply_su_discount(student_id: str | int,
                      amount: float) -> tuple[float, bool]:
    """Return ``(discounted_amount, was_applied)``.

    Counts any active SU club membership as eligibility — calls
    ``student_union_bus.list_clubs_for`` and applies a flat discount
    when the list isn't empty.
    """
    if not student_id or not amount:
        return float(amount or 0), False
    try:
        from education_system.systems.university.services.bus.student_union_bus import (
            list_clubs_for,
        )
        clubs = list_clubs_for(student_id)
        if clubs:
            return round(float(amount) * (1 - _SU_DISCOUNT), 2), True
    except Exception:
        pass
    return float(amount), False


def apply_staff_subsidy(staff_id: str | int,
                        amount: float) -> tuple[float, bool]:
    """Apply staff meal subsidy when the user is on the staff roster."""
    if not staff_id or not amount:
        return float(amount or 0), False
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM staff "
                "WHERE (id = ? OR username = ?) "
                "  AND LOWER(COALESCE(status,'active')) = 'active' "
                "LIMIT 1",
                (staff_id, str(staff_id)),
            ).fetchone()
            if row:
                return round(float(amount) * (1 - _STAFF_SUBSIDY), 2), True
    except Exception:
        pass
    return float(amount), False


# ---------------------------------------------------------------------------
# Menu on the academic calendar
# ---------------------------------------------------------------------------

def publish_menu_for(*, on_date: str,
                     location: str = "Main Hall",
                     menu_items: list | None = None,
                     posted_by: str | None = None) -> str | None:
    """Persist a daily menu as an ``academic_calendar_events`` row.

    Reuses the same pattern hearings, evacuation drills, SU events,
    and trips use. Calendar-aware GUIs see the menu automatically.
    """
    if not on_date or not menu_items:
        return None
    event_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    desc = json.dumps({"location": location, "items": list(menu_items)})
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO academic_calendar_events "
                "(id, name, date, description, event_type, "
                " date_added, last_modified, created_by) "
                "VALUES (?, ?, ?, ?, 'menu', ?, ?, ?)",
                (event_id, f"Menu — {location}",
                 on_date[:10], desc, now, now, posted_by),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("publish_menu_for failed: %s", exc)
        return None

    try:
        from education_system.systems.university.interfaces.gui.academics._event_bus import (
            publish, EVENT_CALENDAR_CHANGED,
        )
        publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                event_type="menu", action="created",
                date=on_date[:10], location=location)
    except Exception:
        pass
    return event_id


def menu_for(on_date: str | None = None,
             *, location: str | None = None) -> list[dict[str, Any]]:
    target = (on_date or _date.today().isoformat())[:10]
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            for r in conn.execute(
                "SELECT id, name, date, description "
                "FROM academic_calendar_events "
                "WHERE event_type = 'menu' AND date = ? "
                "ORDER BY date_added DESC",
                (target,),
            ).fetchall():
                d = dict(r)
                try:
                    d["body"] = json.loads(d["description"] or "{}")
                except Exception:
                    d["body"] = {"items": [], "location": ""}
                if location and (
                    (d["body"].get("location") or "").lower()
                    != location.lower()
                ):
                    continue
                out.append(d)
    except Exception as exc:
        logger.warning("menu_for failed: %s", exc)
    return out


__all__ = [
    "top_up_meal_plan", "record_pos_transaction",
    "apply_su_discount", "apply_staff_subsidy",
    "meal_plan_balance",
    "publish_menu_for", "menu_for",
]
