CREATE TABLE IF NOT EXISTS planned_courses (
                    planned_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    course_id TEXT NOT NULL,
                    semester_number INTEGER NOT NULL,
                    semester_name TEXT NOT NULL,
                    is_locked BOOLEAN DEFAULT 0,
                    priority INTEGER DEFAULT 0,
                    notes TEXT,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plan_id) REFERENCES semester_plans(plan_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(code),
                    UNIQUE(plan_id, course_id)
                );
