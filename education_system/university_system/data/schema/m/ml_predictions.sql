CREATE TABLE IF NOT EXISTS ml_predictions (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                prediction_type TEXT NOT NULL,
                risk_score REAL,
                prediction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                actual_outcome TEXT,
                model_version TEXT
            );
