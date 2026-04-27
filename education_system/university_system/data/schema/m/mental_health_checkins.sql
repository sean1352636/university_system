CREATE TABLE IF NOT EXISTS mental_health_checkins (
            checkin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            mood_rating INTEGER NOT NULL,
            stress_level INTEGER NOT NULL,
            sleep_quality INTEGER,
            notes TEXT,
            follow_up_required INTEGER DEFAULT 0,
            checkin_date TEXT DEFAULT (DATE('now')),
            checkin_time TEXT DEFAULT (TIME('now'))
        );
