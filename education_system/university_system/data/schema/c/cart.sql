CREATE TABLE IF NOT EXISTS cart (
    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    user_id INTEGER,
    product_id TEXT,
    item_id TEXT,
    restaurant_id TEXT,
    quantity INTEGER DEFAULT 1,
    special_instructions TEXT,
    added_at TEXT DEFAULT (datetime('now'))
);
