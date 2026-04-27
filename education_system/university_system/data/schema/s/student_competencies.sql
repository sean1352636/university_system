CREATE TABLE IF NOT EXISTS student_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            competency_id INTEGER NOT NULL,
            level_id INTEGER NOT NULL,
            assessment_date TEXT,
            evidence TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
            FOREIGN KEY (level_id) REFERENCES competency_levels(level_id)
        );
