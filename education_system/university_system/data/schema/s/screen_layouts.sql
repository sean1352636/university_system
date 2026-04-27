CREATE TABLE IF NOT EXISTS screen_layouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screen_number INTEGER UNIQUE NOT NULL,
            name TEXT,
            rows INTEGER NOT NULL DEFAULT 8,
            seats_per_row INTEGER NOT NULL DEFAULT 12,
            vip_rows TEXT,
            wheelchair_positions TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
