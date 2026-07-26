"""Domain layer for Occupancy & Income (Nursery System).

A computed finance/occupancy dashboard — it owns no table. It combines:

* room occupancy (``rooms`` capacity vs active ``pupils`` per room),
* fee income (the Invoices and Payments modules), and
* funded income (the Funded Hours Claims module),

into a single at-a-glance picture of how full the setting is and what it is
billing / collecting.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``occupancy_cli.py``, Tk GUI in ``occupancy_views.py``.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Occupancy & Income"
CATEGORY = "Finance"


@dataclass
class RoomOccupancy:
    room_id: str
    name: str
    capacity: int
    occupancy: int
    status: str

    @property
    def places_left(self) -> int:
        return max(self.capacity - self.occupancy, 0)

    @property
    def pct(self) -> float | None:
        if self.capacity <= 0:
            return None
        return round(self.occupancy / self.capacity * 100, 1)


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for occupancy")
        raise


def list_room_occupancy() -> list[RoomOccupancy]:
    _ensure_schema()
    try:
        with connect() as conn:
            rooms = conn.execute(
                "SELECT room_id, name, capacity, status, min_age_months "
                "FROM rooms ORDER BY min_age_months, name").fetchall()
            counts = dict(conn.execute(
                "SELECT room, COUNT(*) FROM pupils WHERE status = 'active' "
                "GROUP BY room").fetchall())
    except sqlite3.Error:
        logger.exception("list_room_occupancy failed")
        raise
    return [
        RoomOccupancy(room_id=r["room_id"], name=r["name"],
                      capacity=int(r["capacity"]),
                      occupancy=int(counts.get(r["name"], 0)),
                      status=r["status"])
        for r in rooms
    ]


def occupancy_totals() -> dict[str, float | None]:
    rooms = list_room_occupancy()
    capacity = sum(r.capacity for r in rooms)
    occupancy = sum(r.occupancy for r in rooms)
    pct = round(occupancy / capacity * 100, 1) if capacity > 0 else None
    return {"rooms": len(rooms), "capacity": capacity, "occupancy": occupancy,
            "places_left": max(capacity - occupancy, 0), "pct": pct}


def income_summary() -> dict[str, float]:
    """Fee + funded income, reusing the finance modules' own aggregates."""
    out = {"invoiced": 0.0, "collected": 0.0, "outstanding": 0.0,
           "payments_received": 0.0, "funding_total": 0.0, "funding_paid": 0.0}
    try:
        from education_system.systems.nursery.domain.finance.invoices import invoices
        inv = invoices.summary()
        out["invoiced"] = inv["billed"]
        out["collected"] = inv["collected"]
        out["outstanding"] = inv["outstanding"]
    except Exception:
        logger.exception("Could not load invoice summary for occupancy")
    try:
        from education_system.systems.nursery.domain.finance.payments import payments
        out["payments_received"] = payments.summary()["received"]
    except Exception:
        logger.exception("Could not load payment summary for occupancy")
    try:
        from education_system.systems.nursery.domain.finance.funding_claims import (
            funding_claims,
        )
        fc = funding_claims.summary()
        out["funding_total"] = fc["total"]
        out["funding_paid"] = fc["paid"]
    except Exception:
        logger.exception("Could not load funding-claim summary for occupancy")
    return {k: round(v, 2) for k, v in out.items()}
