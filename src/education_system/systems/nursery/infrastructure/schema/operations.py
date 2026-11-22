"""Consumables stock, suppliers and purchase orders, kitchen menus and ingredients.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ── Consumables inventory ────────────────────────────────────────────────────

# ``stock_items`` = the things a setting runs out of: nappies, wipes, formula,
# food, first-aid supplies, learning materials, cleaning products. ``quantity``
# is the live level, kept in step by ``stock_movements``; a level at or below
# ``reorder_level`` raises a reorder alert.
_STOCK_ITEMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_items (
    item_id          TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT 'Consumables',
    unit             TEXT NOT NULL DEFAULT 'each',
    quantity         REAL NOT NULL DEFAULT 0,
    reorder_level    REAL NOT NULL DEFAULT 0,
    reorder_quantity REAL NOT NULL DEFAULT 0,
    unit_cost        REAL NOT NULL DEFAULT 0,
    supplier_id      TEXT,
    location         TEXT,
    room             TEXT,
    expiry_date      TEXT,
    status           TEXT NOT NULL DEFAULT 'active',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_stock_items_category ON stock_items(category);
CREATE INDEX IF NOT EXISTS idx_stock_items_supplier ON stock_items(supplier_id);
"""

# ``stock_movements`` = the audit trail behind every level change. ``quantity``
# is signed: receipts are positive, usage and waste negative.
_STOCK_MOVEMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id   TEXT PRIMARY KEY,
    item_id       TEXT NOT NULL,
    movement_date TEXT NOT NULL,
    movement_type TEXT NOT NULL,
    quantity      REAL NOT NULL,
    room          TEXT,
    reference     TEXT,
    staff_id      TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (item_id) REFERENCES stock_items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_date ON stock_movements(movement_date);
"""

# ── Suppliers, purchase orders and approvals ─────────────────────────────────

_SUPPLIERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id        TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    category           TEXT,
    contact_name       TEXT,
    email              TEXT,
    phone              TEXT,
    account_number     TEXT,
    payment_terms_days INTEGER NOT NULL DEFAULT 30,
    status             TEXT NOT NULL DEFAULT 'active',
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
"""

# ``purchase_orders`` = money going *out*, as opposed to the parent fees and
# funding claims the rest of Finance covers. A PO walks draft → submitted →
# approved → ordered → received → invoiced → paid, and the approval step is
# gated on the order total against the approver's spending limit.
_PURCHASE_ORDERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id         TEXT PRIMARY KEY,
    supplier_id   TEXT NOT NULL,
    order_date    TEXT NOT NULL,
    required_by   TEXT,
    status        TEXT NOT NULL DEFAULT 'draft',
    raised_by     TEXT,
    approved_by   TEXT,
    approved_at   TEXT,
    approval_note TEXT,
    received_at   TEXT,
    invoice_ref   TEXT,
    invoice_date  TEXT,
    invoice_due   TEXT,
    paid_at       TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    FOREIGN KEY (raised_by) REFERENCES staff(staff_id) ON DELETE SET NULL,
    FOREIGN KEY (approved_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_status   ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(supplier_id);
"""

_PURCHASE_ORDER_LINES_SCHEMA = """
CREATE TABLE IF NOT EXISTS purchase_order_lines (
    line_id           TEXT PRIMARY KEY,
    po_id             TEXT NOT NULL,
    item_id           TEXT,
    description       TEXT NOT NULL,
    quantity          REAL NOT NULL DEFAULT 1,
    unit              TEXT NOT NULL DEFAULT 'each',
    unit_price        REAL NOT NULL DEFAULT 0,
    received_quantity REAL NOT NULL DEFAULT 0,
    notes             TEXT,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES stock_items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_po_lines_po ON purchase_order_lines(po_id);
"""

# ── Kitchen: planned menu and ingredients ────────────────────────────────────

# ``menu_plan`` = what the kitchen intends to cook, per date and meal. The
# existing ``meals`` table records what each child actually ate *afterwards*;
# this is the forward-looking half the kitchen orders and cooks against.
_MENU_PLAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS menu_plan (
    menu_id     TEXT PRIMARY KEY,
    menu_date   TEXT NOT NULL,
    meal_type   TEXT NOT NULL,
    dish        TEXT NOT NULL,
    alternative TEXT,
    allergens   TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_menu_plan_date ON menu_plan(menu_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_plan_unique
    ON menu_plan(menu_date, meal_type);
"""

# ``menu_ingredients`` = per-child quantities for a planned dish, which the
# kitchen multiplies by the booked headcount to get an order total. Linking a
# line to ``stock_items`` lets the order check what is already in the store.
_MENU_INGREDIENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS menu_ingredients (
    ingredient_id      TEXT PRIMARY KEY,
    menu_id            TEXT NOT NULL,
    item_id            TEXT,
    name               TEXT NOT NULL,
    quantity_per_child REAL NOT NULL DEFAULT 0,
    unit               TEXT NOT NULL DEFAULT 'g',
    notes              TEXT,
    FOREIGN KEY (menu_id) REFERENCES menu_plan(menu_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES stock_items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_menu_ingredients_menu ON menu_ingredients(menu_id);
"""
