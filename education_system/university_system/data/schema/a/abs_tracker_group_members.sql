CREATE TABLE IF NOT EXISTS abs_tracker_group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, student_id TEXT, UNIQUE(group_id, student_id)
        );
