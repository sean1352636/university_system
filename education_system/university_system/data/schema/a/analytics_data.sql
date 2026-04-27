CREATE TABLE IF NOT EXISTS analytics_data (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_value REAL,
            metric_date TEXT,
            category TEXT,
            additional_data TEXT
        );
