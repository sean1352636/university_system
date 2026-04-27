CREATE TABLE IF NOT EXISTS takeaway_restaurants (
            restaurant_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cuisine_type TEXT,
            description TEXT,
            delivery_fee REAL DEFAULT 2.00,
            min_order_amount REAL DEFAULT 10.00,
            estimated_delivery_time INTEGER DEFAULT 30,
            is_open BOOLEAN DEFAULT 1,
            opening_hours TEXT,
            rating REAL DEFAULT 0.0,
            total_orders INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
