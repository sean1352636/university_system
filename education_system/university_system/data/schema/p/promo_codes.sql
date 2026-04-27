CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_type TEXT NOT NULL,
            discount_value REAL NOT NULL,
            min_purchase REAL DEFAULT 0,
            max_uses INTEGER DEFAULT NULL,
            times_used INTEGER DEFAULT 0,
            valid_from TEXT,
            valid_until TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
