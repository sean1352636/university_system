CREATE TABLE IF NOT EXISTS "shop_transaction_items" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_per_item REAL NOT NULL,
                subtotal REAL NOT NULL
            );
