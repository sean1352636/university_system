CREATE TABLE IF NOT EXISTS shop_products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    category TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tax_rate REAL DEFAULT 0.2,
                    is_active BOOLEAN DEFAULT 1
                );
