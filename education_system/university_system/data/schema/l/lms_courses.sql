CREATE TABLE IF NOT EXISTS lms_courses (
                lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                instructor_id TEXT NOT NULL,
                course_description TEXT,
                syllabus_url TEXT,
                start_date TEXT,
                end_date TEXT,
                enrollment_limit INTEGER DEFAULT 0,
                is_published INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
