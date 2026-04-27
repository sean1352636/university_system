CREATE TABLE IF NOT EXISTS encryption_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT UNIQUE NOT NULL,
                public_key TEXT,
                private_key_encrypted TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                rotated_at TEXT,
                is_active INTEGER DEFAULT 1
            , algorithm TEXT, status TEXT);
