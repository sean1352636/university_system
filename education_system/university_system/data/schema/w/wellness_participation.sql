CREATE TABLE IF NOT EXISTS wellness_participation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    program_name TEXT,
                    enrollment_date TEXT,
                    completion_date TEXT,
                    status TEXT DEFAULT 'enrolled',
                    progress_score INTEGER DEFAULT 0,
                    goals_met INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
