CREATE TABLE IF NOT EXISTS shuttle_stops (
    stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stop_name TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    arrival_time TIME,
    amenities TEXT  -- JSON
, "estimated_time_from_start" INTEGER, "id" INTEGER, "route_id" INTEGER, "stop_order" INTEGER);
