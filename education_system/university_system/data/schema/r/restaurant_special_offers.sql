CREATE TABLE IF NOT EXISTS restaurant_special_offers (
            offer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            discount_type TEXT DEFAULT 'percentage',
            discount_value REAL NOT NULL,
            min_order_amount REAL DEFAULT 0,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            applicable_items TEXT,
            max_uses INTEGER DEFAULT -1,
            uses_count INTEGER DEFAULT 0,
            applicable_days TEXT,
            applicable_times TEXT,
            customer_type TEXT DEFAULT 'all',
            status TEXT DEFAULT 'Active'
        );
