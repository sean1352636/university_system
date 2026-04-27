CREATE TABLE IF NOT EXISTS system_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            category TEXT NOT NULL,
            recorded_datetime TEXT NOT NULL,
            metadata TEXT  -- JSON data
        );
