CREATE TABLE IF NOT EXISTS currency_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_currency TEXT DEFAULT 'GBP',
            auto_update_rates BOOLEAN DEFAULT 1,
            rate_update_frequency INTEGER DEFAULT 24, -- hours
            last_rate_update TEXT,
            created_at TEXT,
            updated_at TEXT
        );
