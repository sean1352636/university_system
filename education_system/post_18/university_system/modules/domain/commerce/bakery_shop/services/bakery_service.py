"""
Tkinter-free data/service layer for the Bakery Shop.

The Bakery Shop is otherwise a large GUI-only app: its persistence logic
lives inside the Tkinter tab classes and the ``domain`` mixins (which pull
in ``tkinter`` transitively via ``_common``). This module factors the pure
SQL/data operations for the highest-value *persisted* entities into a small
headless service so the text CLI (``bakery_shop.cli``) can drive them without
importing Tkinter. The GUI is untouched and keeps working.

Everything reads/writes the same central ``student_records.db`` (via
``infrastructure.database.db.get_connection``) and the same ``bakery_*``
tables the GUI uses, so records created here are visible in the GUI and
vice-versa.

Covered persisted entities:
    * Menu / catering trays  (``bakery_catering_trays``)
    * Sales orders / POS      (``bakery_orders``)
    * Pre-orders              (``bakery_preorders``)
    * Inventory: suppliers, reorder rules, purchase orders, batches
    * Production plans        (``bakery_production_plans``)
    * Subscriptions           (``bakery_subscriptions`` / _deliveries)

The bakery's product catalogue itself is an in-memory dict in the GUI
(never persisted), so it is deliberately *not* exposed here as an editable
entity — catering trays are the persisted, product-like menu records.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Connection / schema helpers
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# Subset of the GUI's schema (see domain/data.py) limited to the tables this
# service touches. Column definitions match the GUI exactly so rows created
# here are fully compatible with it. Every statement is CREATE ... IF NOT
# EXISTS, so this is a no-op against an already-initialised database.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS bakery_orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     TEXT,
    timestamp    TEXT NOT NULL,
    username     TEXT,
    user_type    TEXT,
    items_json   TEXT NOT NULL,
    subtotal     REAL,
    discount     REAL,
    total        REAL,
    payment_method   TEXT,
    refunded         INTEGER DEFAULT 0,
    refund_ref       TEXT,
    refund_timestamp TEXT
);
CREATE TABLE IF NOT EXISTS bakery_catering_trays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    items_json TEXT NOT NULL,
    serves INTEGER,
    price REAL NOT NULL,
    active INTEGER DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS bakery_preorders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE,
    user TEXT NOT NULL,
    user_type TEXT,
    items_json TEXT NOT NULL,
    collection_time TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    notes TEXT,
    subtotal REAL,
    discount REAL,
    total REAL,
    payment_method TEXT,
    paid INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS bakery_suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    contact TEXT,
    email TEXT,
    phone TEXT,
    lead_time_days INTEGER DEFAULT 3,
    active INTEGER DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS bakery_reorder_rules (
    item_name TEXT PRIMARY KEY,
    min_stock INTEGER NOT NULL,
    reorder_qty INTEGER NOT NULL,
    supplier_id INTEGER,
    unit_cost REAL,
    auto INTEGER DEFAULT 0,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS bakery_purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT UNIQUE NOT NULL,
    supplier_id INTEGER,
    status TEXT DEFAULT 'draft',
    items_json TEXT NOT NULL,
    created_at TEXT,
    expected_delivery TEXT,
    received_at TEXT,
    total_cost REAL,
    created_by TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS bakery_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    initial_quantity INTEGER,
    expiry_date TEXT NOT NULL,
    received_date TEXT,
    lot_number TEXT,
    supplier_id INTEGER,
    po_id INTEGER,
    status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS bakery_production_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_date TEXT NOT NULL,
    item_name TEXT NOT NULL,
    forecast_qty INTEGER NOT NULL,
    batch_size INTEGER NOT NULL,
    planned_batches INTEGER NOT NULL,
    planned_qty INTEGER NOT NULL,
    created_by TEXT,
    created_at TEXT,
    UNIQUE (plan_date, item_name)
);
CREATE TABLE IF NOT EXISTS bakery_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    items_json TEXT NOT NULL,
    frequency TEXT NOT NULL,
    price_per_delivery REAL,
    next_delivery TEXT,
    active INTEGER DEFAULT 1,
    paused_until TEXT,
    created_at TEXT,
    cancelled_at TEXT
);
CREATE TABLE IF NOT EXISTS bakery_subscription_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL,
    scheduled_for TEXT NOT NULL,
    delivered_at TEXT,
    order_id TEXT,
    status TEXT DEFAULT 'scheduled',
    notes TEXT
);
"""

_schema_ready = False


def _conn():
    """Open a connection to the central DB and lazily ensure our tables."""
    conn = get_connection()
    global _schema_ready
    if not _schema_ready:
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        except Exception:
            logger.exception("Failed to ensure bakery schema")
        _schema_ready = True
    return conn


def _rows(sql: str, params: tuple = ()) -> list[dict]:
    conn = _conn()
    try:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _one(sql: str, params: tuple = ()) -> Optional[dict]:
    conn = _conn()
    try:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r is not None else None
    finally:
        conn.close()


def _write(sql: str, params: tuple = ()) -> int:
    """Execute a single write; return lastrowid."""
    conn = _conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Menu / catering trays  — the persisted, product-like catalogue
# --------------------------------------------------------------------------- #
class MenuManager:
    @staticmethod
    def list_trays(active_only: bool = False) -> list[dict]:
        sql = ("SELECT id, name, serves, items_json, price, active, created_at "
               "FROM bakery_catering_trays")
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY id ASC"
        return _rows(sql)

    @staticmethod
    def add_tray(name: str, price: float, items: dict, *, serves: int = 0,
                 description: str = "") -> int:
        if not name:
            raise ValueError("Tray name is required.")
        if not items:
            raise ValueError("A tray needs at least one item.")
        return _write(
            "INSERT INTO bakery_catering_trays "
            "(name, description, items_json, serves, price, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (name, description, json.dumps(items), int(serves or 0),
             float(price), _now()),
        )

    @staticmethod
    def update_tray(tray_id: int, *, price: Optional[float] = None,
                    serves: Optional[int] = None,
                    active: Optional[bool] = None) -> bool:
        sets: list[str] = []
        vals: list[Any] = []
        if price is not None:
            sets.append("price=?")
            vals.append(float(price))
        if serves is not None:
            sets.append("serves=?")
            vals.append(int(serves))
        if active is not None:
            sets.append("active=?")
            vals.append(1 if active else 0)
        if not sets:
            return False
        vals.append(tray_id)
        conn = _conn()
        try:
            cur = conn.execute(
                f"UPDATE bakery_catering_trays SET {', '.join(sets)} WHERE id=?",
                tuple(vals))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Orders / POS  (bakery_orders)
# --------------------------------------------------------------------------- #
class OrderManager:
    @staticmethod
    def list_orders(limit: int = 30, include_refunded: bool = True) -> list[dict]:
        sql = ("SELECT id, order_id, timestamp, username, user_type, items_json, "
               "subtotal, discount, total, payment_method, refunded "
               "FROM bakery_orders")
        if not include_refunded:
            sql += " WHERE refunded=0"
        sql += " ORDER BY id DESC LIMIT ?"
        return _rows(sql, (int(limit),))

    @staticmethod
    def get_order(pk: int) -> Optional[dict]:
        return _one(
            "SELECT id, order_id, timestamp, username, user_type, items_json, "
            "subtotal, discount, total, payment_method, refunded, refund_ref, "
            "refund_timestamp FROM bakery_orders WHERE id=?", (pk,))

    @staticmethod
    def create_order(username: str, user_type: str, line_items: list[dict], *,
                     discount: float = 0.0, payment_method: str = "cash") -> dict:
        """Persist a POS sale.

        ``line_items`` is a list of ``{"name", "qty", "unit_price"}`` dicts.
        The stored ``items_json`` is ``{name: qty}`` (the shape the GUI's
        ``load_data`` expects). Returns ``{"id", "order_id", "total"}``.
        """
        if not line_items:
            raise ValueError("An order needs at least one line item.")
        items: dict[str, int] = {}
        subtotal = 0.0
        for li in line_items:
            name = li["name"]
            qty = int(li["qty"])
            price = float(li["unit_price"])
            if qty <= 0:
                continue
            items[name] = items.get(name, 0) + qty
            subtotal += qty * price
        if not items:
            raise ValueError("No positive-quantity line items supplied.")
        discount = max(0.0, float(discount))
        total = max(0.0, subtotal - discount)
        # order_id mirrors the GUI's human-friendly counter style.
        count = _one("SELECT COUNT(*) AS c FROM bakery_orders")["c"]
        order_id = f"ORD-{count + 1001}"
        pk = _write(
            "INSERT INTO bakery_orders "
            "(order_id, timestamp, username, user_type, items_json, subtotal, "
            "discount, total, payment_method, refunded) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (order_id, _now(), username, user_type, json.dumps(items),
             round(subtotal, 2), round(discount, 2), round(total, 2),
             payment_method),
        )
        logger.info("Bakery order created %s (id=%s) total=%.2f",
                    order_id, pk, total)
        return {"id": pk, "order_id": order_id, "total": round(total, 2)}

    @staticmethod
    def refund_order(pk: int, refund_ref: Optional[str] = None) -> bool:
        ref = refund_ref or f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        conn = _conn()
        try:
            cur = conn.execute(
                "UPDATE bakery_orders SET refunded=1, refund_ref=?, "
                "refund_timestamp=? WHERE id=? AND refunded=0",
                (ref, _now(), pk))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Pre-orders  (bakery_preorders)
# --------------------------------------------------------------------------- #
_PREORDER_STATUSES = ("pending", "ready", "collected", "cancelled")


class PreorderManager:
    @staticmethod
    def list_preorders(include_completed: bool = False) -> list[dict]:
        sql = ("SELECT id, order_id, user, user_type, items_json, "
               "collection_time, status, total, payment_method, paid, "
               "created_at FROM bakery_preorders")
        if not include_completed:
            sql += " WHERE status IN ('pending','ready')"
        sql += " ORDER BY collection_time ASC"
        return _rows(sql)

    @staticmethod
    def create_preorder(user: str, user_type: str, items: dict,
                        collection_time: str, *, subtotal: float = 0.0,
                        discount: float = 0.0, total: float = 0.0,
                        notes: str = "", payment_method: str = "card") -> str:
        if not user:
            raise ValueError("A pre-order needs a user.")
        if not items:
            raise ValueError("A pre-order needs at least one item.")
        if not collection_time:
            raise ValueError("A collection time is required.")
        count = _one("SELECT COUNT(*) AS c FROM bakery_preorders")["c"]
        order_id = f"PRE-{count + 1001}"
        _write(
            "INSERT INTO bakery_preorders "
            "(order_id, user, user_type, items_json, collection_time, status, "
            "notes, subtotal, discount, total, payment_method, paid, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, 0, ?)",
            (order_id, user, user_type, json.dumps(items), collection_time,
             notes, round(float(subtotal), 2), round(float(discount), 2),
             round(float(total), 2), payment_method, _now()),
        )
        logger.info("Pre-order created %s user=%s pickup=%s", order_id, user,
                    collection_time)
        return order_id

    @staticmethod
    def update_status(preorder_id: int, status: str) -> bool:
        if status not in _PREORDER_STATUSES:
            raise ValueError(
                f"Status must be one of {', '.join(_PREORDER_STATUSES)}.")
        conn = _conn()
        try:
            cur = conn.execute(
                "UPDATE bakery_preorders SET status=? WHERE id=?",
                (status, preorder_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Inventory: suppliers, reorder rules, purchase orders, batches
# --------------------------------------------------------------------------- #
class InventoryManager:
    # ---- suppliers ----
    @staticmethod
    def list_suppliers() -> list[dict]:
        return _rows("SELECT id, name, contact, email, phone, lead_time_days, "
                     "active FROM bakery_suppliers ORDER BY name")

    @staticmethod
    def add_supplier(name: str, *, contact: str = "", email: str = "",
                     phone: str = "", lead_time_days: int = 3) -> int:
        if not name:
            raise ValueError("Supplier name is required.")
        return _write(
            "INSERT INTO bakery_suppliers "
            "(name, contact, email, phone, lead_time_days, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (name, contact, email, phone, int(lead_time_days), _now()),
        )

    # ---- reorder rules ----
    @staticmethod
    def list_reorder_rules() -> list[dict]:
        return _rows("SELECT item_name, min_stock, reorder_qty, supplier_id, "
                     "unit_cost, auto FROM bakery_reorder_rules "
                     "ORDER BY item_name")

    @staticmethod
    def set_reorder_rule(item_name: str, *, min_stock: int, reorder_qty: int,
                         supplier_id: Optional[int] = None,
                         unit_cost: float = 0.0, auto: bool = False) -> bool:
        if not item_name:
            raise ValueError("Item name is required.")
        _write(
            "INSERT OR REPLACE INTO bakery_reorder_rules "
            "(item_name, min_stock, reorder_qty, supplier_id, unit_cost, "
            "auto, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item_name, int(min_stock), int(reorder_qty), supplier_id,
             float(unit_cost), 1 if auto else 0, _now()),
        )
        return True

    # ---- purchase orders ----
    @staticmethod
    def list_purchase_orders(status: Optional[str] = None) -> list[dict]:
        sql = ("SELECT id, po_number, supplier_id, status, items_json, "
               "created_at, expected_delivery, received_at, total_cost "
               "FROM bakery_purchase_orders")
        params: tuple = ()
        if status:
            sql += " WHERE status=?"
            params = (status,)
        sql += " ORDER BY id DESC"
        return _rows(sql, params)

    @staticmethod
    def create_purchase_order(items: list[dict], *,
                              supplier_id: Optional[int] = None,
                              status: str = "draft", notes: str = "",
                              created_by: str = "cli-user") -> str:
        """``items`` is a list of ``{"item", "qty", "unit_cost"}`` dicts."""
        clean = []
        total = 0.0
        for x in items:
            qty = int(x["qty"])
            cost = float(x.get("unit_cost", 0) or 0)
            if qty <= 0:
                continue
            clean.append({"item": x["item"], "qty": qty, "unit_cost": cost})
            total += qty * cost
        if not clean:
            raise ValueError("A purchase order needs at least one line item.")
        po_number = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        lead = 3
        if supplier_id:
            row = _one("SELECT lead_time_days FROM bakery_suppliers WHERE id=?",
                       (supplier_id,))
            if row:
                lead = int(row["lead_time_days"] or 3)
        expected = (datetime.now() + timedelta(days=lead)).strftime("%Y-%m-%d")
        _write(
            "INSERT INTO bakery_purchase_orders "
            "(po_number, supplier_id, status, items_json, created_at, "
            "expected_delivery, total_cost, created_by, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (po_number, supplier_id, status, json.dumps(clean), _now(),
             expected, round(total, 2), created_by, notes),
        )
        logger.info("PO created %s supplier=%s total=%.2f", po_number,
                    supplier_id, total)
        return po_number

    @staticmethod
    def receive_purchase_order(po_id: int, *, shelf_days: int = 7) -> bool:
        """Mark a PO received and create a stock batch per line item.

        (The bakery's per-product stock counter lives only in the GUI's
        in-memory catalogue, so it is not bumped here — but the persisted
        batch records, which the GUI reads back, are created.)
        """
        po = _one("SELECT id, po_number, supplier_id, status, items_json "
                  "FROM bakery_purchase_orders WHERE id=?", (po_id,))
        if not po or po["status"] == "received":
            return False
        try:
            items = json.loads(po["items_json"] or "[]")
        except (TypeError, ValueError):
            items = []
        received_at = _now()
        expiry = (datetime.now() + timedelta(days=shelf_days)).strftime("%Y-%m-%d")
        conn = _conn()
        try:
            for line in items:
                item = line.get("item")
                qty = int(line.get("qty", 0))
                conn.execute(
                    "INSERT INTO bakery_batches "
                    "(item_name, quantity, initial_quantity, expiry_date, "
                    "received_date, lot_number, supplier_id, po_id, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')",
                    (item, qty, qty, expiry, received_at,
                     f"{po['po_number']}-{str(item)[:3].upper()}",
                     po["supplier_id"], po["id"]))
            conn.execute(
                "UPDATE bakery_purchase_orders SET status='received', "
                "received_at=? WHERE id=?", (received_at, po_id))
            conn.commit()
        finally:
            conn.close()
        logger.info("PO received %s items=%d", po["po_number"], len(items))
        return True

    # ---- batches ----
    @staticmethod
    def list_batches(include_depleted: bool = False) -> list[dict]:
        sql = ("SELECT id, item_name, quantity, initial_quantity, expiry_date, "
               "received_date, lot_number, status FROM bakery_batches")
        if not include_depleted:
            sql += " WHERE status='active'"
        sql += " ORDER BY expiry_date ASC, id ASC"
        return _rows(sql)


# --------------------------------------------------------------------------- #
# Production plans  (bakery_production_plans)
# --------------------------------------------------------------------------- #
class ProductionManager:
    @staticmethod
    def list_plans(plan_date: Optional[str] = None) -> list[dict]:
        sql = ("SELECT id, plan_date, item_name, forecast_qty, batch_size, "
               "planned_batches, planned_qty, created_by, created_at "
               "FROM bakery_production_plans")
        params: tuple = ()
        if plan_date:
            sql += " WHERE plan_date=?"
            params = (plan_date,)
        sql += " ORDER BY plan_date DESC, item_name ASC"
        return _rows(sql, params)

    @staticmethod
    def save_plan(plan_date: str, item_name: str, forecast_qty: int,
                  batch_size: int, *, created_by: str = "cli-user") -> dict:
        """Upsert a production plan line, mirroring the GUI's planner.

        ``planned_batches`` is ceil(forecast/batch_size); ``planned_qty`` is
        batches × batch_size. Returns the computed plan figures.
        """
        if not plan_date:
            raise ValueError("A plan date is required.")
        if not item_name:
            raise ValueError("An item name is required.")
        forecast_qty = int(forecast_qty)
        batch_size = int(batch_size)
        if batch_size <= 0:
            raise ValueError("Batch size must be a positive whole number.")
        batches = (forecast_qty + batch_size - 1) // batch_size if forecast_qty > 0 else 0
        planned = batches * batch_size
        _write(
            "INSERT INTO bakery_production_plans "
            "(plan_date, item_name, forecast_qty, batch_size, planned_batches, "
            "planned_qty, created_by, created_at) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(plan_date, item_name) DO UPDATE SET "
            "forecast_qty=excluded.forecast_qty, "
            "batch_size=excluded.batch_size, "
            "planned_batches=excluded.planned_batches, "
            "planned_qty=excluded.planned_qty",
            (plan_date, item_name, forecast_qty, batch_size, batches, planned,
             created_by, _now()),
        )
        logger.info("Production plan saved %s/%s batches=%d qty=%d",
                    plan_date, item_name, batches, planned)
        return {"planned_batches": batches, "planned_qty": planned}


# --------------------------------------------------------------------------- #
# Subscriptions  (bakery_subscriptions)
# --------------------------------------------------------------------------- #
_FREQ_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30}


class SubscriptionManager:
    @staticmethod
    def list_subscriptions(active_only: bool = False) -> list[dict]:
        sql = ("SELECT id, user, plan_name, items_json, frequency, "
               "price_per_delivery, next_delivery, active, created_at "
               "FROM bakery_subscriptions")
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY id DESC"
        return _rows(sql)

    @staticmethod
    def create_subscription(user: str, plan_name: str, items: dict,
                            frequency: str, *, price: float = 0.0) -> int:
        if not user:
            raise ValueError("A subscription needs a user.")
        if not items:
            raise ValueError("A subscription needs at least one item.")
        freq = (frequency or "weekly").lower()
        days = _FREQ_DAYS.get(freq, 7)
        next_d = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        conn = _conn()
        try:
            cur = conn.execute(
                "INSERT INTO bakery_subscriptions "
                "(user, plan_name, items_json, frequency, price_per_delivery, "
                "next_delivery, active, created_at) VALUES (?,?,?,?,?,?,1,?)",
                (user, plan_name, json.dumps(items), freq, float(price),
                 next_d, _now()))
            sid = cur.lastrowid
            conn.execute(
                "INSERT INTO bakery_subscription_deliveries "
                "(subscription_id, scheduled_for, status) "
                "VALUES (?, ?, 'scheduled')", (sid, next_d))
            conn.commit()
            return sid
        finally:
            conn.close()

    @staticmethod
    def cancel_subscription(sub_id: int) -> bool:
        conn = _conn()
        try:
            cur = conn.execute(
                "UPDATE bakery_subscriptions SET active=0, cancelled_at=? "
                "WHERE id=? AND active=1", (_now(), sub_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
