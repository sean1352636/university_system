CREATE TABLE IF NOT EXISTS outcome_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            outcome_id INTEGER NOT NULL,
            achievement_level REAL,
            assessment_date TEXT,
            evidence TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
        );
