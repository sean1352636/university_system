CREATE TABLE IF NOT EXISTS abs_tracker_student_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT, target_pct REAL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, module_code)
        );
