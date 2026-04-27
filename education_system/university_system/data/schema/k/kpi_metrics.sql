CREATE TABLE IF NOT EXISTS kpi_metrics (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT NOT NULL,
            kpi_category TEXT NOT NULL,
            current_value REAL NOT NULL,
            target_value REAL,
            measurement_date TEXT DEFAULT CURRENT_DATE,
            period TEXT,
            trend TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
