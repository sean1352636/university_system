CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value REAL,
                    measurement_date TEXT,
                    category TEXT,
                    subcategory TEXT,
                    metadata TEXT,
                    calculated_at TEXT
                );
