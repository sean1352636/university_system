CREATE TABLE IF NOT EXISTS system_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                recorded_date DATETIME DEFAULT CURRENT_TIMESTAMP
            );
