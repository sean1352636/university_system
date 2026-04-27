CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT,
                building TEXT,
                capacity INTEGER,
                room_type TEXT,
                equipment TEXT,
                notes TEXT,
                is_active BOOLEAN DEFAULT 1
            , building_id INTEGER, room_name TEXT, floor_number INTEGER, area_sqft REAL, features TEXT, accessibility_compliant BOOLEAN DEFAULT 1, status TEXT DEFAULT 'available', "room_id" INTEGER);
