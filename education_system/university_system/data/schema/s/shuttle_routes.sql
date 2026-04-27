CREATE TABLE IF NOT EXISTS shuttle_routes (
    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_name TEXT NOT NULL,
    description TEXT,
    schedule TEXT,  -- JSON
    stops TEXT,  -- JSON array
    is_active BOOLEAN DEFAULT 1
, "id" INTEGER, "start_time" TEXT, "end_time" TEXT, "frequency_minutes" INTEGER DEFAULT 15, "created_at" TEXT);
