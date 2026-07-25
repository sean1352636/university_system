"""Domain layer for Suppliers & Purchase Orders (Nursery System).

Money going **out**. The rest of Finance covers what parents owe the setting —
invoices, funded-hours claims, vouchers, discounts. This module covers what the
setting owes its suppliers. Three tables:

* ``suppliers`` — who is bought from, with payment terms.
* ``purchase_orders`` — one order, walking
  draft → submitted → approved → ordered → received → invoiced → paid.
  ``rejected`` and ``cancelled`` are the dead ends.
* ``purchase_order_lines`` — what is on it, optionally tied to a
  ``stock_items`` row so receiving the order books the stock in automatically.

Approval is gated on the order total against the approver's spending limit
(``APPROVAL_LIMITS``): a room leader can sign off small consumables, a manager
more, and anything above the manager's limit goes to the owner. ``approve``
refuses politely rather than silently allowing an over-limit sign-off.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``purchasing_cli.py``, Tk GUI in ``purchasing_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Suppliers & Purchase Orders"
CATEGORY = "Finance"

SUPPLIER_PREFIX = "NSP"
PO_PREFIX = "NPO"
LINE_PREFIX = "NPL"
ID_DIGITS = 3

SUPPLIER_STATUSES = ("active", "on-hold", "closed")
SUPPLIER_CATEGORIES = (
    "Nappies & changing", "Formula & bottles", "Food & catering",
    "First aid & medical", "Learning materials", "Cleaning & hygiene",
    "Office & admin", "Maintenance", "Utilities", "Other",
)

# The workflow, in order. ``_NEXT`` is the only place transitions are defined.
PO_STATUSES = ("draft", "submitted", "approved", "rejected", "ordered",
               "received", "invoiced", "paid", "cancelled")

_NEXT: dict[str, tuple[str, ...]] = {
    "draft": ("submitted", "cancelled"),
    "submitted": ("approved", "rejected", "cancelled"),
    "approved": ("ordered", "cancelled"),
    "rejected": ("draft", "cancelled"),
    "ordered": ("received", "cancelled"),
    "received": ("invoiced",),
    "invoiced": ("paid",),
    "paid": (),
    "cancelled": (),
}

# What each role may sign off, in pounds. ``None`` means no limit.
APPROVAL_LIMITS: dict[str, float | None] = {
    "Room Leader": 100.0,
    "Deputy Manager": 500.0,
    "Nursery Manager": 2000.0,
    "Owner": None,
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(ValueError):
    """Raised for invalid supplier / purchase-order input."""


@dataclass
class Supplier:
    supplier_id: str
    name: str
    category: str | None
    contact_name: str | None
    email: str | None
    phone: str | None
    account_number: str | None
    payment_terms_days: int
    status: str
    notes: str | None


@dataclass
class OrderLine:
    line_id: str
    po_id: str
    item_id: str | None
    description: str
    quantity: float
    unit: str
    unit_price: float
    received_quantity: float
    notes: str | None

    @property
    def line_total(self) -> float:
        return round(self.quantity * self.unit_price, 2)

    @property
    def outstanding(self) -> float:
        return max(self.quantity - self.received_quantity, 0)


@dataclass
class PurchaseOrder:
    po_id: str
    supplier_id: str
    order_date: str
    required_by: str | None
    status: str
    raised_by: str | None
    approved_by: str | None
    approved_at: str | None
    approval_note: str | None
    received_at: str | None
    invoice_ref: str | None
    invoice_date: str | None
    invoice_due: str | None
    paid_at: str | None
    notes: str | None
    lines: list[OrderLine] = field(default_factory=list)
    supplier_name: str | None = None
    raised_by_name: str | None = None
    approved_by_name: str | None = None

    @property
    def total(self) -> float:
        return round(sum(line.line_total for line in self.lines), 2)

    @property
    def fully_received(self) -> bool:
        return bool(self.lines) and all(line.outstanding <= 0
                                        for line in self.lines)

    @property
    def is_open(self) -> bool:
        return self.status not in ("paid", "cancelled", "rejected")

    @property
    def overdue(self) -> bool:
        """Invoiced, unpaid and past its due date."""
        if self.status != "invoiced" or not self.invoice_due:
            return False
        return self.invoice_due < _dt.date.today().isoformat()

    def next_statuses(self) -> tuple[str, ...]:
        return _NEXT.get(self.status, ())


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for purchasing")
        raise


# ── Approval policy ──────────────────────────────────────────────────────────

def approval_limit(role: str | None) -> float | None:
    """The spending limit for a role, or 0 for a role with no authority."""
    if not role:
        return 0.0
    if role in APPROVAL_LIMITS:
        return APPROVAL_LIMITS[role]
    return 0.0


def can_approve(role: str | None, total: float) -> bool:
    limit = approval_limit(role)
    return limit is None or total <= limit


def required_role(total: float) -> str:
    """The most junior role that may sign off ``total``."""
    for role, limit in sorted(
            APPROVAL_LIMITS.items(),
            key=lambda kv: (kv[1] is None, kv[1] or 0)):
        if limit is None or total <= limit:
            return role
    return "Owner"


def _staff_role(staff_id: str) -> str | None:
    try:
        with connect() as conn:
            row = conn.execute("SELECT role FROM staff WHERE staff_id = ?",
                               (staff_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("Could not read role for staff %s", staff_id)
        return None
    return row["role"] if row else None


# ── Validation helpers ───────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    v = "" if value is None else str(value).strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


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


# ── Suppliers ────────────────────────────────────────────────────────────────

def _supplier_row(r: sqlite3.Row) -> Supplier:
    return Supplier(
        supplier_id=r["supplier_id"], name=r["name"], category=r["category"],
        contact_name=r["contact_name"], email=r["email"], phone=r["phone"],
        account_number=r["account_number"],
        payment_terms_days=int(r["payment_terms_days"]), status=r["status"],
        notes=r["notes"],
    )


def list_suppliers(*, status: str | None = None,
                   category: str | None = None) -> list[Supplier]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if category:
        clauses.append("category = ?")
        params.append(category)
    sql = "SELECT * FROM suppliers"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_suppliers failed")
        raise
    return [_supplier_row(r) for r in rows]


def get_supplier(supplier_id: str) -> Supplier | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM suppliers WHERE supplier_id = ?",
                (supplier_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_supplier(%s) failed", supplier_id)
        raise
    return _supplier_row(row) if row else None


def _validate_supplier(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _opt(data.get("name"))
    if not name:
        raise ValidationError("Supplier name is required")
    out["name"] = name
    out["category"] = _opt(data.get("category"))
    out["contact_name"] = _opt(data.get("contact_name"))
    email = _opt(data.get("email"))
    if email and not _EMAIL_RE.match(email):
        raise ValidationError("Email is not a valid address")
    out["email"] = email
    out["phone"] = _opt(data.get("phone"))
    out["account_number"] = _opt(data.get("account_number"))
    out["payment_terms_days"] = int(
        _number(data.get("payment_terms_days"), "Payment terms", default=30))
    status = str(data.get("status") or "active").strip().lower()
    if status not in SUPPLIER_STATUSES:
        raise ValidationError("Status must be one of: "
                              + ", ".join(SUPPLIER_STATUSES))
    out["status"] = status
    out["notes"] = _opt(data.get("notes"))
    return out


def create_supplier(data: dict[str, Any]) -> Supplier:
    _ensure_schema()
    payload = _validate_supplier(data)
    sid = _generate_id("suppliers", "supplier_id", SUPPLIER_PREFIX)
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO suppliers (
                    supplier_id, name, category, contact_name, email, phone,
                    account_number, payment_terms_days, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, payload["name"], payload["category"],
                 payload["contact_name"], payload["email"], payload["phone"],
                 payload["account_number"], payload["payment_terms_days"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            f"A supplier called '{payload['name']}' already exists.") from e
    except sqlite3.Error as e:
        logger.exception("INSERT failed for supplier %s", sid)
        raise ValidationError(f"Could not add supplier — {e}") from e
    supplier = get_supplier(sid)
    assert supplier is not None
    logger.info("Added supplier %s (%s)", sid, payload["name"])
    return supplier


def update_supplier(supplier_id: str, data: dict[str, Any]) -> Supplier:
    _ensure_schema()
    if get_supplier(supplier_id) is None:
        raise ValidationError(f"No supplier with id {supplier_id}")
    payload = _validate_supplier(data)
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE suppliers SET
                    name = ?, category = ?, contact_name = ?, email = ?,
                    phone = ?, account_number = ?, payment_terms_days = ?,
                    status = ?, notes = ?
                WHERE supplier_id = ?
                """,
                (payload["name"], payload["category"], payload["contact_name"],
                 payload["email"], payload["phone"], payload["account_number"],
                 payload["payment_terms_days"], payload["status"],
                 payload["notes"], supplier_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            f"A supplier called '{payload['name']}' already exists.") from e
    except sqlite3.Error:
        logger.exception("UPDATE failed for supplier %s", supplier_id)
        raise
    supplier = get_supplier(supplier_id)
    assert supplier is not None
    return supplier


def delete_supplier(supplier_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            orders = conn.execute(
                "SELECT COUNT(*) FROM purchase_orders WHERE supplier_id = ?",
                (supplier_id,)).fetchone()[0]
            if orders:
                raise ValidationError(
                    f"{orders} purchase order(s) reference this supplier — set "
                    "them to 'closed' instead of deleting.")
            cur = conn.execute("DELETE FROM suppliers WHERE supplier_id = ?",
                               (supplier_id,))
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error deleting supplier %s", supplier_id)
        raise


# ── Purchase orders ──────────────────────────────────────────────────────────

_PO_SELECT = """
SELECT o.*, s.name AS supplier_name,
       TRIM(r.first_name || ' ' || r.last_name) AS raised_by_name,
       TRIM(a.first_name || ' ' || a.last_name) AS approved_by_name
FROM purchase_orders o
LEFT JOIN suppliers s ON s.supplier_id = o.supplier_id
LEFT JOIN staff r ON r.staff_id = o.raised_by
LEFT JOIN staff a ON a.staff_id = o.approved_by
"""


def _line_row(r: sqlite3.Row) -> OrderLine:
    return OrderLine(
        line_id=r["line_id"], po_id=r["po_id"], item_id=r["item_id"],
        description=r["description"], quantity=float(r["quantity"]),
        unit=r["unit"], unit_price=float(r["unit_price"]),
        received_quantity=float(r["received_quantity"]), notes=r["notes"],
    )


def _po_row(r: sqlite3.Row, lines: list[OrderLine]) -> PurchaseOrder:
    keys = r.keys()
    return PurchaseOrder(
        po_id=r["po_id"], supplier_id=r["supplier_id"],
        order_date=r["order_date"], required_by=r["required_by"],
        status=r["status"], raised_by=r["raised_by"],
        approved_by=r["approved_by"], approved_at=r["approved_at"],
        approval_note=r["approval_note"], received_at=r["received_at"],
        invoice_ref=r["invoice_ref"], invoice_date=r["invoice_date"],
        invoice_due=r["invoice_due"], paid_at=r["paid_at"], notes=r["notes"],
        lines=lines,
        supplier_name=r["supplier_name"] if "supplier_name" in keys else None,
        raised_by_name=r["raised_by_name"] if "raised_by_name" in keys else None,
        approved_by_name=(
            r["approved_by_name"] if "approved_by_name" in keys else None),
    )


def _lines_for(conn: sqlite3.Connection, po_ids: list[str]
               ) -> dict[str, list[OrderLine]]:
    if not po_ids:
        return {}
    marks = ", ".join("?" * len(po_ids))
    rows = conn.execute(
        f"SELECT * FROM purchase_order_lines WHERE po_id IN ({marks}) "  # noqa: S608
        "ORDER BY line_id", tuple(po_ids)).fetchall()
    out: dict[str, list[OrderLine]] = {}
    for r in rows:
        out.setdefault(r["po_id"], []).append(_line_row(r))
    return out


def list_orders(*, supplier_id: str | None = None, status: str | None = None,
                open_only: bool = False) -> list[PurchaseOrder]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if supplier_id:
        clauses.append("o.supplier_id = ?")
        params.append(supplier_id)
    if status:
        clauses.append("o.status = ?")
        params.append(status)
    if open_only:
        clauses.append("o.status NOT IN ('paid', 'cancelled', 'rejected')")
    sql = _PO_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY o.order_date DESC, o.po_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            lines = _lines_for(conn, [r["po_id"] for r in rows])
    except sqlite3.Error:
        logger.exception("list_orders failed")
        raise
    return [_po_row(r, lines.get(r["po_id"], [])) for r in rows]


def get_order(po_id: str) -> PurchaseOrder | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_PO_SELECT + " WHERE o.po_id = ?",
                               (po_id,)).fetchone()
            if row is None:
                return None
            lines = _lines_for(conn, [po_id])
    except sqlite3.Error:
        logger.exception("get_order(%s) failed", po_id)
        raise
    return _po_row(row, lines.get(po_id, []))


def create_order(data: dict[str, Any]) -> PurchaseOrder:
    """Raise a draft purchase order, optionally with its lines."""
    _ensure_schema()
    supplier_id = _opt(data.get("supplier_id"))
    if not supplier_id:
        raise ValidationError("Supplier is required")
    supplier = get_supplier(supplier_id)
    if supplier is None:
        raise ValidationError(f"No supplier with id {supplier_id}")
    if supplier.status == "closed":
        raise ValidationError(
            f"{supplier.name} is closed — reopen the supplier first.")

    order_date = _check_date(data.get("order_date") or _today(), "Order date")
    required_by = _check_date(data.get("required_by"), "Required by",
                              required=False)
    if required_by and order_date and required_by < order_date:
        raise ValidationError("'Required by' cannot be before the order date")

    po_id = _generate_id("purchase_orders", "po_id", PO_PREFIX)
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO purchase_orders (
                    po_id, supplier_id, order_date, required_by, status,
                    raised_by, notes
                ) VALUES (?, ?, ?, ?, 'draft', ?, ?)
                """,
                (po_id, supplier_id, order_date, required_by,
                 _opt(data.get("raised_by")), _opt(data.get("notes"))),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for purchase order %s", po_id)
        raise ValidationError(f"Could not raise order — {e}") from e

    for line in data.get("lines") or []:
        add_line(po_id, line)

    order = get_order(po_id)
    assert order is not None
    logger.info("Raised purchase order %s for supplier %s", po_id, supplier_id)
    return order


def create_order_from_reorder_list(supplier_id: str, *,
                                   raised_by: str | None = None
                                   ) -> PurchaseOrder:
    """Raise a draft order straight from what stock says needs reordering."""
    from education_system.nursery_system.modules.domain.inventory import (
        inventory as _inventory,
    )
    rows = _inventory.reorder_list(supplier_id=supplier_id)
    if not rows:
        raise ValidationError(
            "Nothing from this supplier is at or below its reorder level.")
    return create_order({
        "supplier_id": supplier_id, "raised_by": raised_by,
        "notes": "Raised from the stock reorder list.",
        "lines": [{"item_id": r["item_id"], "description": r["description"],
                   "quantity": r["quantity"], "unit": r["unit"],
                   "unit_price": r["unit_price"]} for r in rows],
    })


def update_order(po_id: str, data: dict[str, Any]) -> PurchaseOrder:
    """Edit an order's header. Only a draft or rejected order may be edited."""
    _ensure_schema()
    order = get_order(po_id)
    if order is None:
        raise ValidationError(f"No purchase order with id {po_id}")
    if order.status not in ("draft", "rejected"):
        raise ValidationError(
            f"Order {po_id} is {order.status} — only a draft or rejected order "
            "can be edited.")
    order_date = _check_date(data.get("order_date") or order.order_date,
                             "Order date")
    required_by = _check_date(data.get("required_by"), "Required by",
                              required=False)
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE purchase_orders SET order_date = ?, required_by = ?, "
                "raised_by = ?, notes = ? WHERE po_id = ?",
                (order_date, required_by, _opt(data.get("raised_by")),
                 _opt(data.get("notes")), po_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("UPDATE failed for purchase order %s", po_id)
        raise
    out = get_order(po_id)
    assert out is not None
    return out


def delete_order(po_id: str) -> bool:
    _ensure_schema()
    order = get_order(po_id)
    if order is not None and order.status not in ("draft", "cancelled",
                                                  "rejected"):
        raise ValidationError(
            f"Order {po_id} is {order.status} — cancel it rather than deleting "
            "it, so the spend trail survives.")
    try:
        with connect() as conn:
            cur = conn.execute("DELETE FROM purchase_orders WHERE po_id = ?",
                               (po_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting purchase order %s", po_id)
        raise
    if deleted:
        logger.info("Deleted purchase order %s", po_id)
    return deleted


# ── Lines ────────────────────────────────────────────────────────────────────

def add_line(po_id: str, data: dict[str, Any]) -> OrderLine:
    _ensure_schema()
    order = get_order(po_id)
    if order is None:
        raise ValidationError(f"No purchase order with id {po_id}")
    if order.status not in ("draft", "rejected"):
        raise ValidationError(
            f"Order {po_id} is {order.status} — lines can only be changed on a "
            "draft.")

    description = _opt(data.get("description"))
    item_id = _opt(data.get("item_id"))
    if item_id and not description:
        from education_system.nursery_system.modules.domain.inventory import (
            inventory as _inventory,
        )
        item = _inventory.get_item(item_id)
        if item is None:
            raise ValidationError(f"No stock item with id {item_id}")
        description = item.name
    if not description:
        raise ValidationError("A description (or a stock item) is required")

    quantity = _number(data.get("quantity"), "Quantity", default=1)
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero")
    unit_price = _number(data.get("unit_price"), "Unit price")

    line_id = _generate_id("purchase_order_lines", "line_id", LINE_PREFIX)
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO purchase_order_lines (
                    line_id, po_id, item_id, description, quantity, unit,
                    unit_price, received_quantity, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (line_id, po_id, item_id, description, quantity,
                 _opt(data.get("unit")) or "each", unit_price,
                 _opt(data.get("notes"))),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for order line %s", line_id)
        raise ValidationError(f"Could not add line — {e}") from e
    out = get_order(po_id)
    assert out is not None
    line = next(x for x in out.lines if x.line_id == line_id)
    return line


def delete_line(line_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT po_id FROM purchase_order_lines WHERE line_id = ?",
                (line_id,)).fetchone()
            if row is None:
                return False
            order = get_order(row["po_id"])
            if order is not None and order.status not in ("draft", "rejected"):
                raise ValidationError(
                    f"Order {order.po_id} is {order.status} — lines can only be "
                    "changed on a draft.")
            cur = conn.execute(
                "DELETE FROM purchase_order_lines WHERE line_id = ?",
                (line_id,))
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error deleting order line %s", line_id)
        raise


# ── Workflow ─────────────────────────────────────────────────────────────────

def _set_status(po_id: str, status: str, **columns: Any) -> PurchaseOrder:
    order = get_order(po_id)
    if order is None:
        raise ValidationError(f"No purchase order with id {po_id}")
    if status not in order.next_statuses():
        allowed = ", ".join(order.next_statuses()) or "nothing — it is closed"
        raise ValidationError(
            f"Order {po_id} is {order.status}; it can only move to {allowed}.")
    assignments = ", ".join(f"{k} = ?" for k in columns)
    sql = "UPDATE purchase_orders SET status = ?"
    params: list[Any] = [status]
    if assignments:
        sql += f", {assignments}"
        params.extend(columns.values())
    sql += " WHERE po_id = ?"
    params.append(po_id)
    try:
        with connect() as conn:
            conn.execute(sql, tuple(params))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not move purchase order %s to %s", po_id, status)
        raise
    out = get_order(po_id)
    assert out is not None
    logger.info("Purchase order %s: %s -> %s", po_id, order.status, status)
    return out


def submit_order(po_id: str) -> PurchaseOrder:
    """Send a draft for approval."""
    order = get_order(po_id)
    if order is None:
        raise ValidationError(f"No purchase order with id {po_id}")
    if not order.lines:
        raise ValidationError("Add at least one line before submitting")
    return _set_status(po_id, "submitted")


def approve_order(po_id: str, approver_staff_id: str,
                  note: str | None = None, *,
                  approver_role: str | None = None) -> PurchaseOrder:
    """Approve an order, refusing if it is above the approver's limit."""
    order = get_order(po_id)
    if order is None:
        raise ValidationError(f"No purchase order with id {po_id}")
    staff_id = _opt(approver_staff_id)
    if not staff_id:
        raise ValidationError("The approver's staff ID is required")

    role = approver_role or _staff_role(staff_id)
    if not can_approve(role, order.total):
        limit = approval_limit(role)
        raise ValidationError(
            f"£{order.total:.2f} is above the "
            f"{'£%.2f' % limit if limit is not None else 'unlimited'} limit for "
            f"'{role or 'unknown role'}'. This order needs a "
            f"{required_role(order.total)}.")
    return _set_status(po_id, "approved", approved_by=staff_id,
                       approved_at=_now(), approval_note=_opt(note))


def reject_order(po_id: str, approver_staff_id: str,
                 note: str | None = None) -> PurchaseOrder:
    if not _opt(note):
        raise ValidationError("Give a reason for rejecting the order")
    return _set_status(po_id, "rejected", approved_by=_opt(approver_staff_id),
                       approved_at=_now(), approval_note=_opt(note))


def mark_ordered(po_id: str) -> PurchaseOrder:
    """The order has been placed with the supplier."""
    return _set_status(po_id, "ordered")


def receive_order(po_id: str, *, received_date: str | None = None,
                  staff_id: str | None = None,
                  book_into_stock: bool = True) -> PurchaseOrder:
    """Book a delivery in — and, for lines tied to stock, raise the levels.

    Receiving is the point where purchasing and inventory meet: a line with an
    ``item_id`` produces a ``receipt`` movement, so nobody re-keys the delivery
    note into the stock screen.
    """
    order = get_order(po_id)
    if order is None:
        raise ValidationError(f"No purchase order with id {po_id}")
    day = _check_date(received_date or _today(), "Received date")

    if book_into_stock:
        from education_system.nursery_system.modules.domain.inventory import (
            inventory as _inventory,
        )
        for line in order.lines:
            if not line.item_id or line.outstanding <= 0:
                continue
            _inventory.receive(
                line.item_id, line.outstanding, movement_date=day,
                reference=po_id, staff_id=staff_id,
                notes=f"Delivery against {po_id}.")

    try:
        with connect() as conn:
            conn.execute(
                "UPDATE purchase_order_lines SET received_quantity = quantity "
                "WHERE po_id = ?", (po_id,))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not mark lines received on %s", po_id)
        raise
    return _set_status(po_id, "received", received_at=day)


def record_invoice(po_id: str, invoice_ref: str, *,
                   invoice_date: str | None = None,
                   invoice_due: str | None = None) -> PurchaseOrder:
    """Attach the supplier's invoice. The due date follows payment terms."""
    order = get_order(po_id)
    if order is None:
        raise ValidationError(f"No purchase order with id {po_id}")
    ref = _opt(invoice_ref)
    if not ref:
        raise ValidationError("The supplier's invoice reference is required")
    issued = _check_date(invoice_date or _today(), "Invoice date")
    assert issued is not None
    due = _check_date(invoice_due, "Invoice due", required=False)
    if due is None:
        supplier = get_supplier(order.supplier_id)
        terms = supplier.payment_terms_days if supplier else 30
        due = (_dt.date.fromisoformat(issued)
               + _dt.timedelta(days=terms)).isoformat()
    return _set_status(po_id, "invoiced", invoice_ref=ref, invoice_date=issued,
                       invoice_due=due)


def mark_paid(po_id: str, *, paid_date: str | None = None) -> PurchaseOrder:
    return _set_status(po_id, "paid",
                       paid_at=_check_date(paid_date or _today(), "Paid date"))


def cancel_order(po_id: str, note: str | None = None) -> PurchaseOrder:
    return _set_status(po_id, "cancelled",
                       notes=_opt(note) or "Cancelled.")


# ── Pickers / summary ────────────────────────────────────────────────────────

def list_supplier_choices() -> list[tuple[str, str]]:
    return [(s.supplier_id, f"{s.name} ({s.supplier_id})")
            for s in list_suppliers(status="active")]


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"],
             f"{r['first_name']} {r['last_name']} ({r['staff_id']})"
             + (f" — {r['role']}" if r["role"] else ""))
            for r in rows]


def awaiting_approval() -> list[PurchaseOrder]:
    return list_orders(status="submitted")


def summary() -> dict[str, Any]:
    """Headline counts for the purchasing board."""
    orders = list_orders()
    suppliers = list_suppliers()
    open_orders = [o for o in orders if o.is_open]
    year = _today()[:4]
    return {
        "suppliers": len(suppliers),
        "active_suppliers": sum(1 for s in suppliers if s.status == "active"),
        "orders": len(orders),
        "open_orders": len(open_orders),
        "awaiting_approval": sum(1 for o in orders if o.status == "submitted"),
        "awaiting_delivery": sum(1 for o in orders if o.status == "ordered"),
        "unpaid": sum(1 for o in orders if o.status == "invoiced"),
        "overdue": sum(1 for o in orders if o.overdue),
        "committed_spend": round(sum(o.total for o in open_orders), 2),
        "unpaid_value": round(sum(o.total for o in orders
                                  if o.status == "invoiced"), 2),
        "spend_this_year": round(sum(o.total for o in orders
                                     if o.status == "paid"
                                     and (o.paid_at or "").startswith(year)), 2),
    }
