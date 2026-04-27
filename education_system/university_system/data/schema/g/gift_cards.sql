CREATE TABLE IF NOT EXISTS gift_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            initial_value REAL NOT NULL,
            current_balance REAL NOT NULL,
            purchaser_name TEXT,
            purchaser_email TEXT,
            recipient_name TEXT,
            recipient_email TEXT,
            message TEXT,
            purchase_date TEXT DEFAULT CURRENT_TIMESTAMP,
            expiry_date TEXT,
            status TEXT DEFAULT 'active'
        );
