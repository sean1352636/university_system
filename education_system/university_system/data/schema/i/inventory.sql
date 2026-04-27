CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT NOT NULL,
                minimum_threshold INTEGER DEFAULT 10,
                supplier TEXT,
                cost_per_unit REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
