"""Domain layer for Consumables & Stock (Nursery System).

The things a setting runs out of on a Tuesday afternoon: nappies, wipes,
formula, food, first-aid supplies, learning materials, cleaning products. Two
tables:

* ``stock_items`` — one row per thing held, with the live ``quantity``, the
  ``reorder_level`` that triggers an alert, a suggested ``reorder_quantity``
  and the supplier it is bought from.
* ``stock_movements`` — the signed ledger behind every level change. Receipts
  are positive; usage, waste and losses are negative. ``quantity`` on the item
  is only ever moved by ``record_movement``, so the level and the ledger can
  never drift apart.

``reorder_alerts`` is the working screen: what is at or below its reorder
level, what has run out entirely, and what is about to expire.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``inventory_cli.py``, Tk GUI in ``inventory_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Consumables & Stock"
CATEGORY = "Finance"

ITEM_PREFIX = "NSI"
MOVEMENT_PREFIX = "NSM"
ID_DIGITS = 3

CATEGORIES = (
    "Nappies & changing",
    "Formula & bottles",
    "Food & kitchen",
    "First aid & medical",
    "Learning materials",
    "Cleaning & hygiene",
    "Office & admin",
    "Consumables",
)

UNITS = ("each", "pack", "box", "bottle", "tub", "roll", "kg", "g", "litre",
         "ml")

# Positive movements add to stock; negative ones take it away. The sign is
# applied by ``record_movement`` so callers always pass a positive quantity.
MOVEMENT_TYPES = ("receipt", "usage", "waste", "adjustment", "return",
                  "stocktake")
_INCOMING = ("receipt", "return")
_ABSOLUTE = ("stocktake", "adjustment")

ITEM_STATUSES = ("active", "discontinued")

# Items expiring within this many days are flagged alongside low stock.
EXPIRY_WARNING_DAYS = 30

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid stock input."""


@dataclass
class StockItem:
    item_id: str
    name: str
    category: str
    unit: str
    quantity: float
    reorder_level: float
    reorder_quantity: float
    unit_cost: float
    supplier_id: str | None
    location: str | None
    room: str | None
    expiry_date: str | None
    status: str
    notes: str | None
    supplier_name: str | None = None

    @property
    def value(self) -> float:
        return round(self.quantity * self.unit_cost, 2)

    @property
    def out_of_stock(self) -> bool:
        return self.quantity <= 0

    @property
    def needs_reorder(self) -> bool:
        return (self.status == "active"
                and self.quantity <= self.reorder_level)

    @property
    def suggested_order(self) -> float:
        """How much to order to get back above the reorder level."""
        if not self.needs_reorder:
            return 0.0
        if self.reorder_quantity > 0:
            return self.reorder_quantity
        return max(self.reorder_level - self.quantity, 1)

    def expires_within(self, days: int, *, on_day: str | None = None) -> bool:
        if not self.expiry_date:
            return False
        day = on_day or _dt.date.today().isoformat()
        try:
            cutoff = (_dt.date.fromisoformat(day)
                      + _dt.timedelta(days=days)).isoformat()
        except ValueError:
            return False
        return self.expiry_date <= cutoff


@dataclass
class StockMovement:
    movement_id: str
    item_id: str
    movement_date: str
    movement_type: str
    quantity: float
    room: str | None
    reference: str | None
    staff_id: str | None
    notes: str | None
    item_name: str | None = None
    staff_name: str | None = None


@dataclass
class StockAlert:
    item: StockItem
    reason: str  # 'out-of-stock' | 'low' | 'expiring' | 'expired'
    detail: str

    @property
    def severity(self) -> str:
        return "urgent" if self.reason in ("out-of-stock", "expired") else "low"


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for inventory")
        raise


# ── Validation helpers ───────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    v = "" if value is None else str(value).strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _check_date(value: Any, label: str, *, required: bool = True) -> str | None:
    v = _opt(value)
    if v is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(v)
    except ValueError as e:
        raise ValidationError(f"{label} is not a real date") from e
    return v


def _number(value: Any, label: str, *, default: float = 0.0,
            minimum: float | None = 0.0) -> float:
    v = _opt(value)
    if v is None:
        return default
    try:
        out = float(v)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if minimum is not None and out < minimum:
        raise ValidationError(f"{label} cannot be less than {minimum:g}")
    return out


def _generate_id(table: str, column: str, prefix: str) -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                f"SELECT {column} FROM {table}").fetchall()}  # noqa: S608
    except sqlite3.Error:
        logger.exception("Could not read existing ids from %s", table)
        raise
    seq = 1
    while f"{prefix}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{prefix}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        candidate = f"{prefix}{n}"
        if candidate not in existing:
            return candidate
    raise RuntimeError(f"Could not allocate a unique id for {table}")


# ── Items ────────────────────────────────────────────────────────────────────

_ITEM_SELECT = """
SELECT i.*, s.name AS supplier_name
FROM stock_items i
LEFT JOIN suppliers s ON s.supplier_id = i.supplier_id
"""


def _item_row(r: sqlite3.Row) -> StockItem:
    keys = r.keys()
    return StockItem(
        item_id=r["item_id"], name=r["name"], category=r["category"],
        unit=r["unit"], quantity=float(r["quantity"]),
        reorder_level=float(r["reorder_level"]),
        reorder_quantity=float(r["reorder_quantity"]),
        unit_cost=float(r["unit_cost"]), supplier_id=r["supplier_id"],
        location=r["location"], room=r["room"], expiry_date=r["expiry_date"],
        status=r["status"], notes=r["notes"],
        supplier_name=r["supplier_name"] if "supplier_name" in keys else None,
    )


def list_items(*, category: str | None = None, supplier_id: str | None = None,
               status: str | None = None,
               needs_reorder: bool = False) -> list[StockItem]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if category:
        clauses.append("i.category = ?")
        params.append(category)
    if supplier_id:
        clauses.append("i.supplier_id = ?")
        params.append(supplier_id)
    if status:
        clauses.append("i.status = ?")
        params.append(status)
    sql = _ITEM_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY i.category, i.name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_items failed")
        raise
    items = [_item_row(r) for r in rows]
    return [i for i in items if i.needs_reorder] if needs_reorder else items


def get_item(item_id: str) -> StockItem | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_ITEM_SELECT + " WHERE i.item_id = ?",
                               (item_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_item(%s) failed", item_id)
        raise
    return _item_row(row) if row else None


def _validate_item(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _opt(data.get("name"))
    if not name:
        raise ValidationError("Item name is required")
    out["name"] = name
    out["category"] = _opt(data.get("category")) or "Consumables"
    out["unit"] = _opt(data.get("unit")) or "each"
    out["quantity"] = _number(data.get("quantity"), "Quantity")
    out["reorder_level"] = _number(data.get("reorder_level"), "Reorder level")
    out["reorder_quantity"] = _number(data.get("reorder_quantity"),
                                      "Reorder quantity")
    out["unit_cost"] = _number(data.get("unit_cost"), "Unit cost")
    out["supplier_id"] = _opt(data.get("supplier_id"))
    out["location"] = _opt(data.get("location"))
    out["room"] = _opt(data.get("room"))
    out["expiry_date"] = _check_date(data.get("expiry_date"), "Expiry date",
                                     required=False)
    status = str(data.get("status") or "active").strip().lower()
    if status not in ITEM_STATUSES:
        raise ValidationError("Status must be one of: "
                              + ", ".join(ITEM_STATUSES))
    out["status"] = status
    out["notes"] = _opt(data.get("notes"))
    return out


def create_item(data: dict[str, Any]) -> StockItem:
    """Add something to the stock list, with its opening quantity."""
    _ensure_schema()
    payload = _validate_item(data)
    iid = _generate_id("stock_items", "item_id", ITEM_PREFIX)
    try:
        with connect() as conn:
            if payload["supplier_id"] and not conn.execute(
                    "SELECT 1 FROM suppliers WHERE supplier_id = ?",
                    (payload["supplier_id"],)).fetchone():
                raise ValidationError(
                    f"No supplier with id {payload['supplier_id']}")
            conn.execute(
                """
                INSERT INTO stock_items (
                    item_id, name, category, unit, quantity, reorder_level,
                    reorder_quantity, unit_cost, supplier_id, location, room,
                    expiry_date, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (iid, payload["name"], payload["category"], payload["unit"],
                 payload["quantity"], payload["reorder_level"],
                 payload["reorder_quantity"], payload["unit_cost"],
                 payload["supplier_id"], payload["location"], payload["room"],
                 payload["expiry_date"], payload["status"], payload["notes"]),
            )
            if payload["quantity"]:
                conn.execute(
                    "INSERT INTO stock_movements (movement_id, item_id, "
                    "movement_date, movement_type, quantity, notes) "
                    "VALUES (?, ?, ?, 'adjustment', ?, 'Opening balance')",
                    (_generate_id("stock_movements", "movement_id",
                                  MOVEMENT_PREFIX),
                     iid, _today(), payload["quantity"]))
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for stock item %s", iid)
        raise ValidationError(f"Could not add item — {e}") from e
    item = get_item(iid)
    assert item is not None
    logger.info("Added stock item %s (%s)", iid, payload["name"])
    return item


def update_item(item_id: str, data: dict[str, Any]) -> StockItem:
    """Edit an item's details. The quantity is left alone — use a movement."""
    _ensure_schema()
    existing = get_item(item_id)
    if existing is None:
        raise ValidationError(f"No stock item with id {item_id}")
    payload = _validate_item({**data, "quantity": existing.quantity})
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE stock_items SET
                    name = ?, category = ?, unit = ?, reorder_level = ?,
                    reorder_quantity = ?, unit_cost = ?, supplier_id = ?,
                    location = ?, room = ?, expiry_date = ?, status = ?,
                    notes = ?
                WHERE item_id = ?
                """,
                (payload["name"], payload["category"], payload["unit"],
                 payload["reorder_level"], payload["reorder_quantity"],
                 payload["unit_cost"], payload["supplier_id"],
                 payload["location"], payload["room"], payload["expiry_date"],
                 payload["status"], payload["notes"], item_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("UPDATE failed for stock item %s", item_id)
        raise
    item = get_item(item_id)
    assert item is not None
    logger.info("Updated stock item %s", item_id)
    return item


def delete_item(item_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute("DELETE FROM stock_items WHERE item_id = ?",
                               (item_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting stock item %s", item_id)
        raise
    if deleted:
        logger.info("Deleted stock item %s", item_id)
    return deleted


# ── Movements (the only thing that changes a level) ──────────────────────────

_MOVEMENT_SELECT = """
SELECT m.*, i.name AS item_name,
       TRIM(st.first_name || ' ' || st.last_name) AS staff_name
FROM stock_movements m
LEFT JOIN stock_items i ON i.item_id = m.item_id
LEFT JOIN staff st ON st.staff_id = m.staff_id
"""


def _movement_row(r: sqlite3.Row) -> StockMovement:
    keys = r.keys()
    return StockMovement(
        movement_id=r["movement_id"], item_id=r["item_id"],
        movement_date=r["movement_date"], movement_type=r["movement_type"],
        quantity=float(r["quantity"]), room=r["room"],
        reference=r["reference"], staff_id=r["staff_id"], notes=r["notes"],
        item_name=r["item_name"] if "item_name" in keys else None,
        staff_name=r["staff_name"] if "staff_name" in keys else None,
    )


def list_movements(*, item_id: str | None = None,
                   movement_type: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> list[StockMovement]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if item_id:
        clauses.append("m.item_id = ?")
        params.append(item_id)
    if movement_type:
        clauses.append("m.movement_type = ?")
        params.append(movement_type)
    if date_from:
        clauses.append("m.movement_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("m.movement_date <= ?")
        params.append(date_to)
    sql = _MOVEMENT_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY m.movement_date DESC, m.movement_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_movements failed")
        raise
    return [_movement_row(r) for r in rows]


def record_movement(data: dict[str, Any]) -> StockMovement:
    """Move stock and update the item's level in the same transaction.

    Pass ``quantity`` as a positive number; the sign follows from
    ``movement_type``. A ``stocktake`` sets the level outright, recording the
    difference as the movement.
    """
    _ensure_schema()
    item_id = _opt(data.get("item_id"))
    if not item_id:
        raise ValidationError("Item is required")
    item = get_item(item_id)
    if item is None:
        raise ValidationError(f"No stock item with id {item_id}")

    movement_type = str(data.get("movement_type") or "usage").strip().lower()
    if movement_type not in MOVEMENT_TYPES:
        raise ValidationError("Movement type must be one of: "
                              + ", ".join(MOVEMENT_TYPES))

    raw = _number(data.get("quantity"), "Quantity", minimum=None)
    if movement_type == "stocktake":
        if raw < 0:
            raise ValidationError("A stocktake count cannot be negative")
        delta = raw - item.quantity
    elif movement_type == "adjustment":
        delta = raw  # a correction may legitimately go either way
    else:
        if raw <= 0:
            raise ValidationError("Quantity must be greater than zero")
        delta = raw if movement_type in _INCOMING else -raw

    new_quantity = round(item.quantity + delta, 3)
    if new_quantity < 0:
        raise ValidationError(
            f"Only {item.quantity:g} {item.unit} of {item.name} in stock — "
            f"cannot take {abs(delta):g} out.")

    mid = _generate_id("stock_movements", "movement_id", MOVEMENT_PREFIX)
    movement_date = _check_date(data.get("movement_date") or _today(), "Date")
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO stock_movements (
                    movement_id, item_id, movement_date, movement_type,
                    quantity, room, reference, staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mid, item_id, movement_date, movement_type, delta,
                 _opt(data.get("room")), _opt(data.get("reference")),
                 _opt(data.get("staff_id")), _opt(data.get("notes"))),
            )
            conn.execute("UPDATE stock_items SET quantity = ? WHERE item_id = ?",
                         (new_quantity, item_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("Could not record stock movement for %s", item_id)
        raise ValidationError(f"Could not record movement — {e}") from e
    rows = list_movements(item_id=item_id)
    out = next((m for m in rows if m.movement_id == mid), None)
    assert out is not None
    logger.info("Stock %s: %s %+g %s (now %g)", item_id, movement_type, delta,
                item.unit, new_quantity)
    return out


def use(item_id: str, quantity: float, **extra: Any) -> StockMovement:
    """Convenience wrapper: take stock out for day-to-day use."""
    return record_movement({"item_id": item_id, "quantity": quantity,
                            "movement_type": "usage", **extra})


def receive(item_id: str, quantity: float, **extra: Any) -> StockMovement:
    """Convenience wrapper: book a delivery in."""
    return record_movement({"item_id": item_id, "quantity": quantity,
                            "movement_type": "receipt", **extra})


def stocktake(item_id: str, counted: float, **extra: Any) -> StockMovement:
    """Convenience wrapper: set the level to what was actually counted."""
    return record_movement({"item_id": item_id, "quantity": counted,
                            "movement_type": "stocktake", **extra})


# ── Alerts ───────────────────────────────────────────────────────────────────

def reorder_alerts(*, on_day: str | None = None) -> list[StockAlert]:
    """What needs ordering or throwing out, worst first."""
    day = _check_date(on_day or _today(), "Date")
    assert day is not None
    alerts: list[StockAlert] = []
    for item in list_items(status="active"):
        if item.out_of_stock:
            alerts.append(StockAlert(
                item, "out-of-stock",
                f"None left. Order {item.suggested_order:g} {item.unit}"
                + (f" from {item.supplier_name}." if item.supplier_name
                   else ".")))
        elif item.needs_reorder:
            alerts.append(StockAlert(
                item, "low",
                f"{item.quantity:g} {item.unit} left, at or below the reorder "
                f"level of {item.reorder_level:g}. Order "
                f"{item.suggested_order:g}"
                + (f" from {item.supplier_name}." if item.supplier_name
                   else ".")))
        if item.expiry_date and item.expiry_date < day:
            alerts.append(StockAlert(
                item, "expired",
                f"Expired on {item.expiry_date} — remove from use."))
        elif item.expires_within(EXPIRY_WARNING_DAYS, on_day=day):
            alerts.append(StockAlert(
                item, "expiring",
                f"Expires {item.expiry_date}, within "
                f"{EXPIRY_WARNING_DAYS} days."))
    alerts.sort(key=lambda a: (0 if a.severity == "urgent" else 1,
                               a.item.category, a.item.name))
    return alerts


def reorder_list(*, supplier_id: str | None = None) -> list[dict[str, Any]]:
    """A ready-to-order list — what to buy, how much, and the likely cost.

    Feeds straight into a purchase order via
    ``purchasing.create_order_from_reorder_list``.
    """
    items = list_items(supplier_id=supplier_id, status="active",
                       needs_reorder=True)
    return [{
        "item_id": i.item_id,
        "description": i.name,
        "quantity": i.suggested_order,
        "unit": i.unit,
        "unit_price": i.unit_cost,
        "line_total": round(i.suggested_order * i.unit_cost, 2),
        "supplier_id": i.supplier_id,
        "supplier_name": i.supplier_name,
    } for i in items]


# ── Pickers / summary ────────────────────────────────────────────────────────

def list_item_choices() -> list[tuple[str, str]]:
    return [(i.item_id, f"{i.name} ({i.item_id}) — {i.quantity:g} {i.unit}")
            for i in list_items(status="active")]


def list_supplier_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT supplier_id, name FROM suppliers "
                "WHERE status = 'active' ORDER BY name").fetchall()
    except sqlite3.Error:
        logger.exception("list_supplier_choices failed")
        raise
    return [(r["supplier_id"], f"{r['name']} ({r['supplier_id']})")
            for r in rows]


def summary(*, on_day: str | None = None) -> dict[str, Any]:
    """Headline counts for the stock board."""
    items = list_items()
    alerts = reorder_alerts(on_day=on_day)
    active = [i for i in items if i.status == "active"]
    return {
        "items": len(items),
        "active_items": len(active),
        "categories": len({i.category for i in active}),
        "stock_value": round(sum(i.value for i in active), 2),
        "out_of_stock": sum(1 for i in active if i.out_of_stock),
        "needs_reorder": sum(1 for i in active if i.needs_reorder),
        "expiring_soon": sum(1 for a in alerts if a.reason == "expiring"),
        "expired": sum(1 for a in alerts if a.reason == "expired"),
        "alerts": len(alerts),
        "reorder_cost": round(sum(r["line_total"] for r in reorder_list()), 2),
    }
