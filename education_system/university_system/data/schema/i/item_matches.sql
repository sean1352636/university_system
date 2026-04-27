CREATE TABLE IF NOT EXISTS item_matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lost_item_id INTEGER NOT NULL,
                    found_item_id INTEGER NOT NULL,
                    match_score REAL NOT NULL,
                    match_reasons TEXT,
                    status TEXT DEFAULT 'Suggested',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lost_item_id) REFERENCES lost_items(item_id) ON DELETE CASCADE,
                    FOREIGN KEY (found_item_id) REFERENCES found_items(item_id) ON DELETE CASCADE
                );
