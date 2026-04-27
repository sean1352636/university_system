CREATE TABLE IF NOT EXISTS order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    order_id INTEGER,
    source_order_id TEXT,
    product_id TEXT,
    item_name TEXT,
    artist TEXT,
    quantity REAL DEFAULT 1,
    unit_type TEXT,
    unit_price REAL,
    subtotal REAL,
    special_cut TEXT,
    special_instructions TEXT,
    warranty_id TEXT,
    serial_number TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
