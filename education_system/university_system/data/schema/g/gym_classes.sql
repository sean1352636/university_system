CREATE TABLE IF NOT EXISTS gym_classes (
                    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_name TEXT NOT NULL,
                    class_type TEXT NOT NULL,
                    instructor_id TEXT,
                    instructor_name TEXT NOT NULL,
                    schedule_day TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    location TEXT NOT NULL,
                    max_capacity INTEGER DEFAULT 20,
                    current_enrolled INTEGER DEFAULT 0,
                    description TEXT,
                    difficulty_level TEXT DEFAULT 'all_levels',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
