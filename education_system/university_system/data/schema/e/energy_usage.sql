CREATE TABLE IF NOT EXISTS energy_usage (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            usage_type TEXT NOT NULL,
            reading_date TEXT NOT NULL,
            meter_reading REAL NOT NULL,
            consumption REAL,
            cost REAL,
            billing_period_start TEXT,
            billing_period_end TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings (building_id)
        );
