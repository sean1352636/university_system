CREATE TABLE IF NOT EXISTS abs_tracker_student_prefs (
            student_id TEXT, key TEXT, value TEXT,
            PRIMARY KEY(student_id, key)
        );
