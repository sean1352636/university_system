CREATE TABLE IF NOT EXISTS faculty_schedule_blocks (
                    block_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    activity_type TEXT NOT NULL DEFAULT 'teaching',
                    title TEXT,
                    description TEXT,
                    location TEXT,
                    course_code TEXT,
                    color TEXT,
                    is_locked INTEGER DEFAULT 0,
                    semester TEXT,
                    academic_year TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
