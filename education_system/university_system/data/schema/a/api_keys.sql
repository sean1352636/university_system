CREATE TABLE IF NOT EXISTS api_keys (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_name TEXT NOT NULL,
            api_key TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            permissions TEXT, -- JSON array
            rate_limit INTEGER DEFAULT 1000,
            is_active BOOLEAN DEFAULT 1,
            expires_at TEXT,
            last_used_at TEXT,
            created_by TEXT,
            created_at TEXT
        , "id" INTEGER, "user_id" INTEGER);
