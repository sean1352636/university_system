CREATE TABLE IF NOT EXISTS rubric_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rubric_id INTEGER NOT NULL,
            criteria_name TEXT NOT NULL,
            description TEXT,
            max_points REAL NOT NULL,
            weight REAL DEFAULT 1.0,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (rubric_id) REFERENCES rubrics (id) ON DELETE CASCADE
        );
