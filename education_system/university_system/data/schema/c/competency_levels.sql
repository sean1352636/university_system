CREATE TABLE IF NOT EXISTS competency_levels (
            level_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competency_id INTEGER NOT NULL,
            level_name TEXT NOT NULL,
            level_value INTEGER NOT NULL,
            description TEXT,
            FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
        );
