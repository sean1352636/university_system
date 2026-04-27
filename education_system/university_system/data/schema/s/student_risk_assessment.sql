CREATE TABLE IF NOT EXISTS student_risk_assessment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            assessment_date TEXT,
            prediction_model TEXT,
            confidence REAL,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );
