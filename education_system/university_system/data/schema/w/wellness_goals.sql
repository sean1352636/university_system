CREATE TABLE IF NOT EXISTS wellness_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    goal_description TEXT NOT NULL,
                    target_value REAL,
                    current_value REAL DEFAULT 0,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT DEFAULT 'Active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
