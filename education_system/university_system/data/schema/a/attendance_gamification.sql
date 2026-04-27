CREATE TABLE IF NOT EXISTS attendance_gamification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            badges TEXT,
            achievements TEXT,
            streak_days INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_attendance_date TEXT,
            total_rewards INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
