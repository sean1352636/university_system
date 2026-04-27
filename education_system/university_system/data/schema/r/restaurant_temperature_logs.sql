CREATE TABLE IF NOT EXISTS restaurant_temperature_logs (
            log_id TEXT PRIMARY KEY,
            equipment_id TEXT NOT NULL,
            temperature REAL NOT NULL,
            recorded_date TEXT NOT NULL,
            recorded_by TEXT,
            location TEXT,
            notes TEXT,
            alert_triggered INTEGER DEFAULT 0
        );
