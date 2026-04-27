CREATE TABLE IF NOT EXISTS student_requirement_progress (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    requirement_id TEXT NOT NULL,
                    credits_completed REAL DEFAULT 0.0,
                    completion_percentage REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'in_progress',
                    completion_date TEXT,
                    notes TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (requirement_id) REFERENCES graduation_requirements (id),
                    UNIQUE(student_id, requirement_id)
                );
