CREATE TABLE IF NOT EXISTS search_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    filters TEXT NOT NULL,
                    date_added TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                );
