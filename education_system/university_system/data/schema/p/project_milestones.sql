CREATE TABLE IF NOT EXISTS project_milestones (
                    id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    milestone_name TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    completion_percentage REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'pending',
                    course_id TEXT,
                    student_id TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL, last_updated TEXT,
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
