CREATE TABLE IF NOT EXISTS shuttle_buses (
    bus_id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    bus_number TEXT UNIQUE,
    capacity INTEGER DEFAULT 40,
    current_location TEXT,  -- lat,lon
    current_stop_id INTEGER,
    in_service BOOLEAN DEFAULT 1,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "id" INTEGER, "current_route_id" INTEGER, "status" TEXT DEFAULT 'active',
    FOREIGN KEY (route_id) REFERENCES shuttle_routes(route_id)
);
