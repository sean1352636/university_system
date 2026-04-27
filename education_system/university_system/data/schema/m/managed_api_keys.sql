CREATE TABLE IF NOT EXISTS managed_api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT UNIQUE NOT NULL,
                    key_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    user_id INTEGER,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    last_used_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    permissions TEXT,
                    metadata TEXT,
                    previous_key_hash TEXT,
                    previous_key_valid_until TEXT
                );
