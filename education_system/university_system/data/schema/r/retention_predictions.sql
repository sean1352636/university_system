CREATE TABLE IF NOT EXISTS retention_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            model_id INTEGER NOT NULL,
            retention_probability REAL NOT NULL,
            risk_level TEXT NOT NULL,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            prediction_year INTEGER,
            factors TEXT,
            recommendations TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        );
