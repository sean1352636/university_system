CREATE TABLE IF NOT EXISTS assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_name TEXT NOT NULL,
            assessment_type TEXT NOT NULL,
            module_code TEXT NOT NULL,
            max_points REAL NOT NULL,
            weight REAL NOT NULL,
            due_date TEXT,
            date_created TEXT DEFAULT (datetime('now')),
            description TEXT,
            rubric TEXT, duration_minutes INTEGER DEFAULT 0, status TEXT DEFAULT 'Active', updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
