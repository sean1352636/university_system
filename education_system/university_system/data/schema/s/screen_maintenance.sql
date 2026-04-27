CREATE TABLE IF NOT EXISTS screen_maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screen_number INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            description TEXT,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT,
            technician TEXT,
            cost REAL,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
