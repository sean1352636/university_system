CREATE TABLE IF NOT EXISTS grade_predictions (
                    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    current_grade REAL,
                    predicted_final_grade TEXT,
                    confidence_level REAL DEFAULT 0.0,
                    prediction_factors_json TEXT,
                    improvement_suggestions_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
