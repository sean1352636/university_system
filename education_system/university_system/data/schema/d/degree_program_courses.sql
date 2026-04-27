CREATE TABLE IF NOT EXISTS degree_program_courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    program_code TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    requirement_type TEXT DEFAULT 'Core',
                    year_level INTEGER DEFAULT 1,
                    semester_offered TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(program_code, course_id)
                );
