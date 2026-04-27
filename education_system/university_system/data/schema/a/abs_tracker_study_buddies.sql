CREATE TABLE IF NOT EXISTS abs_tracker_study_buddies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, module_code)
        );
