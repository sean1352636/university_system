CREATE TABLE IF NOT EXISTS comm_hub_pinned_messages (
                    pin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_type TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    pinned_by TEXT NOT NULL,
                    pinned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    context TEXT DEFAULT 'global'
                );
