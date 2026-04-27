CREATE TABLE IF NOT EXISTS requirement_completion (
                completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                requirement_id INTEGER NOT NULL,
                is_completed INTEGER DEFAULT 0,
                credits_earned INTEGER DEFAULT 0,
                completed_date TEXT, "credits_completed" REAL DEFAULT 0,
                FOREIGN KEY (requirement_id) REFERENCES degree_requirements(requirement_id) ON DELETE CASCADE
            );
