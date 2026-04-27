CREATE TABLE IF NOT EXISTS campus_routes (
                    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_name TEXT NOT NULL,
                    start_location_id INTEGER NOT NULL,
                    end_location_id INTEGER NOT NULL,
                    route_type TEXT DEFAULT 'Walking',
                    is_accessible BOOLEAN DEFAULT 1,
                    distance_meters REAL NOT NULL,
                    estimated_time_minutes INTEGER NOT NULL,
                    waypoints TEXT,
                    description TEXT,
                    elevation_change REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (start_location_id) REFERENCES campus_buildings(building_id),
                    FOREIGN KEY (end_location_id) REFERENCES campus_buildings(building_id)
                );
