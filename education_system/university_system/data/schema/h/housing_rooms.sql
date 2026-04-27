CREATE TABLE IF NOT EXISTS housing_rooms (
            room_id TEXT PRIMARY KEY,
            building_id TEXT NOT NULL,
            room_number TEXT NOT NULL,
            floor_number INTEGER NOT NULL,
            room_type TEXT NOT NULL,
            max_occupants INTEGER NOT NULL,
            current_occupants INTEGER DEFAULT 0,
            is_accessible BOOLEAN DEFAULT 0,
            status TEXT NOT NULL,
            monthly_rent REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (building_id) REFERENCES housing_buildings (building_id)
        );
