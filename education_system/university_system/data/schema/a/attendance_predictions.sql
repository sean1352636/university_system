CREATE TABLE IF NOT EXISTS attendance_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            prediction_date TEXT,
            predicted_attendance_rate REAL,
            risk_level TEXT,
            confidence_score REAL,
            factors TEXT,
            recommendations TEXT,
            model_version TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
