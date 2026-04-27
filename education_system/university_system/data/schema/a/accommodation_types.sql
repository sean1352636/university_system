CREATE TABLE IF NOT EXISTS accommodation_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    requires_approval BOOLEAN DEFAULT 0,
                    max_duration_days INTEGER,
                    created_at TEXT
                );
