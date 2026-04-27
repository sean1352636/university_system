CREATE TABLE IF NOT EXISTS performance_trends (
            trend_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_category TEXT NOT NULL,
            time_period TEXT NOT NULL,
            value REAL NOT NULL,
            change_from_previous REAL,
            trend_direction TEXT,
            recorded_date TEXT DEFAULT CURRENT_DATE
        );
