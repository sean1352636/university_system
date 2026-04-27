CREATE TABLE IF NOT EXISTS wellbeing_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                mood_rating INTEGER,
                notes TEXT,
                logged_by TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
