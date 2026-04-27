CREATE TABLE IF NOT EXISTS carbon_tracking (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                transport_carbon REAL DEFAULT 0,
                energy_carbon REAL DEFAULT 0,
                catering_carbon REAL DEFAULT 0,
                total_carbon REAL DEFAULT 0,
                attendees INTEGER DEFAULT 0,
                carbon_per_person REAL DEFAULT 0,
                sustainability_score REAL DEFAULT 0,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            );
