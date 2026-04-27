CREATE TABLE IF NOT EXISTS points_of_interest (
                    poi_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    building_id INTEGER,
                    poi_name TEXT NOT NULL,
                    poi_type TEXT NOT NULL,
                    floor_number INTEGER,
                    room_number TEXT,
                    description TEXT,
                    latitude REAL,
                    longitude REAL,
                    is_accessible BOOLEAN DEFAULT 1,
                    operating_hours TEXT,
                    contact_info TEXT,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (building_id) REFERENCES campus_buildings(building_id) ON DELETE CASCADE
                );
