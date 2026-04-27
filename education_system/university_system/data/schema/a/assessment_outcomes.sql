CREATE TABLE IF NOT EXISTS assessment_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            outcome_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
        );
