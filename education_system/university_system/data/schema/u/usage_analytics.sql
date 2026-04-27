CREATE TABLE IF NOT EXISTS usage_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            category TEXT,
            additional_data TEXT
        );
