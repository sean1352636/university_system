CREATE TABLE IF NOT EXISTS search_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    entity_type TEXT,
                    clicked_id TEXT NOT NULL,
                    click_position INTEGER,
                    user_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
