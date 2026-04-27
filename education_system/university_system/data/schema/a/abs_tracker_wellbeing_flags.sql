CREATE TABLE IF NOT EXISTS abs_tracker_wellbeing_flags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, attendance_id INTEGER, note TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
