CREATE TABLE IF NOT EXISTS study_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT,
                    plan_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    total_hours INTEGER DEFAULT 0,
                    difficulty_level TEXT DEFAULT 'Medium',
                    status TEXT DEFAULT 'Active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
