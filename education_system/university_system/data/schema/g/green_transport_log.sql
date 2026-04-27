CREATE TABLE IF NOT EXISTS green_transport_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transport_method TEXT,
                distance_km REAL DEFAULT 0,
                carbon_saved REAL DEFAULT 0,
                trip_date TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            );
