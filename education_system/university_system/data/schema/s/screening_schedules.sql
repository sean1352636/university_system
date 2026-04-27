CREATE TABLE IF NOT EXISTS screening_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    screening_type TEXT,
                    due_date TEXT,
                    completed_date TEXT,
                    status TEXT DEFAULT 'due',
                    provider TEXT,
                    results TEXT,
                    next_due_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
