CREATE TABLE IF NOT EXISTS "shop_inventory" (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                last_restock_date TEXT,
                restock_threshold INTEGER DEFAULT 5
            );
