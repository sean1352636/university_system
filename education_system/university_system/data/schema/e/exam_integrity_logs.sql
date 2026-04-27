CREATE TABLE IF NOT EXISTS exam_integrity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data_json TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
