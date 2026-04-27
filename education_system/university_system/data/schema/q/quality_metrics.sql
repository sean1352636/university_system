CREATE TABLE IF NOT EXISTS quality_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_category TEXT,
                    target_value REAL,
                    actual_value REAL,
                    measurement_period TEXT,
                    measured_date TEXT,
                    status TEXT,
                    improvement_needed INTEGER DEFAULT 0,
                    created_at TEXT
                );
