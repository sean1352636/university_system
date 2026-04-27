CREATE TABLE IF NOT EXISTS instructors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                department TEXT DEFAULT '',
                specialization TEXT DEFAULT '',
                max_courses_per_semester INTEGER DEFAULT 4,
                max_hours_per_week INTEGER DEFAULT 40,
                preferred_days TEXT,
                preferred_times TEXT,
                status TEXT DEFAULT 'Active',
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
