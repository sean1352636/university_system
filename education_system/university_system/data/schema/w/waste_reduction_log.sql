CREATE TABLE IF NOT EXISTS waste_reduction_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                waste_generated REAL DEFAULT 0,
                waste_recycled REAL DEFAULT 0,
                waste_composted REAL DEFAULT 0,
                waste_landfill REAL DEFAULT 0,
                recycling_rate REAL DEFAULT 0,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            );
