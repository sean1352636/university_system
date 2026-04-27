CREATE TABLE IF NOT EXISTS abs_tracker_intervention_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, student_id TEXT, action TEXT, outcome TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
