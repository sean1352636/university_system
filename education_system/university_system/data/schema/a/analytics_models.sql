CREATE TABLE IF NOT EXISTS analytics_models (
            model_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_type TEXT NOT NULL,
            description TEXT,
            model_version TEXT,
            accuracy_score REAL,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            last_trained_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            parameters TEXT
        );
