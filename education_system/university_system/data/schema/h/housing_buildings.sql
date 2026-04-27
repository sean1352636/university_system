CREATE TABLE IF NOT EXISTS housing_buildings (
            building_id TEXT PRIMARY KEY,
            building_name TEXT NOT NULL,
            address TEXT NOT NULL,
            campus_location TEXT NOT NULL,
            total_rooms INTEGER NOT NULL,
            available_rooms INTEGER NOT NULL,
            has_elevator BOOLEAN DEFAULT 0,
            has_accessible_rooms BOOLEAN DEFAULT 0,
            has_kitchen BOOLEAN DEFAULT 0,
            has_laundry BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
