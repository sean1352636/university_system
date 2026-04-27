CREATE TABLE IF NOT EXISTS office_hours (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        instructor_id TEXT NOT NULL,
                        day_of_week TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        location TEXT NOT NULL,
                        capacity INTEGER DEFAULT 5,
                        notes TEXT DEFAULT '',
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
