CREATE TABLE IF NOT EXISTS parking_lots (
            lot_id              TEXT    PRIMARY KEY,
            lot_name            TEXT,
            location            TEXT,
            total_spaces        INTEGER,
            available_spaces    INTEGER,
            zone                TEXT,
            hours_of_operation  TEXT
        , hourly_rate DECIMAL(5,2) DEFAULT 0.00, daily_rate DECIMAL(5,2) DEFAULT 0.00, monthly_rate DECIMAL(5,2) DEFAULT 0.00, is_active BOOLEAN DEFAULT 1, created_at TEXT DEFAULT NULL, updated_at TEXT DEFAULT NULL);
