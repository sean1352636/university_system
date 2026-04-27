CREATE TABLE IF NOT EXISTS exchange_rates (
            rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            exchange_rate DECIMAL(10,6) NOT NULL,
            rate_date TEXT NOT NULL,
            source TEXT, -- 'manual', 'api', 'bank'
            created_at TEXT
        );
