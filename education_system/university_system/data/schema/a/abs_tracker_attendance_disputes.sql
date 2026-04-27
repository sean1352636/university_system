CREATE TABLE IF NOT EXISTS abs_tracker_attendance_disputes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    TEXT, attendance_id INTEGER, reason TEXT,
            status        TEXT DEFAULT 'open',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at   TEXT, outcome TEXT
        );
