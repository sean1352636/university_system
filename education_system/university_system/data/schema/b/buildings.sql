CREATE TABLE IF NOT EXISTS buildings (
            building_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_name TEXT NOT NULL,
            building_code TEXT UNIQUE NOT NULL,
            address TEXT,
            total_floors INTEGER,
            total_rooms INTEGER,
            building_type TEXT,
            year_built INTEGER,
            last_renovation_year INTEGER,
            accessibility_features TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
