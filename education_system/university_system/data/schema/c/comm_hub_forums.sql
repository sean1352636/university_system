CREATE TABLE IF NOT EXISTS comm_hub_forums (
                    forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    forum_type TEXT DEFAULT 'topic',
                    department TEXT,
                    visibility TEXT DEFAULT 'public',
                    is_archived INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
