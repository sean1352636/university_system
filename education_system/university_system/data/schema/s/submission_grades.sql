CREATE TABLE IF NOT EXISTS submission_grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                marks INTEGER,
                feedback TEXT,
                graded_by TEXT,
                graded_at TEXT DEFAULT (datetime('now'))
            );
