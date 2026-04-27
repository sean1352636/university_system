CREATE TABLE IF NOT EXISTS bi_custom_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_category TEXT NOT NULL,
            description TEXT,
            calculation_formula TEXT NOT NULL,
            data_sources TEXT,
            unit_of_measure TEXT,
            target_value REAL,
            created_by TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
