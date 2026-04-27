CREATE TABLE IF NOT EXISTS abs_tracker_student_badges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, badge TEXT, awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, badge)
        );
