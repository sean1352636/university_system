CREATE TABLE IF NOT EXISTS screening_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            screening_type TEXT NOT NULL,
            results TEXT,
            date_performed TEXT NOT NULL,
            next_due_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
