CREATE TABLE IF NOT EXISTS abs_tracker_student_drafts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT, date TEXT, reason TEXT,
            saved_at    TEXT DEFAULT CURRENT_TIMESTAMP
        );
