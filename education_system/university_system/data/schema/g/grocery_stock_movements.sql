CREATE TABLE IF NOT EXISTS grocery_stock_movements (
            movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            previous_stock INTEGER,
            new_stock INTEGER,
            reference TEXT,
            notes TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES grocery_products (product_id)
        );
