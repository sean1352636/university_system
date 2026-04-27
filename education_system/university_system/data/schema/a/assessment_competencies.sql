CREATE TABLE IF NOT EXISTS assessment_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            competency_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
            FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
        );
