CREATE TABLE IF NOT EXISTS shop_discounts (
            discount_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            discount_type TEXT NOT NULL,
            discount_value REAL NOT NULL,
            start_date TEXT,
            end_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            applicable_products TEXT,
            min_purchase_amount REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );
