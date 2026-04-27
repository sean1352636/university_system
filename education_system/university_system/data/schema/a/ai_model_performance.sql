CREATE TABLE IF NOT EXISTS ai_model_performance (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            test_dataset TEXT,
            measured_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
