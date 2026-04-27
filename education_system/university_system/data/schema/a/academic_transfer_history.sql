CREATE TABLE IF NOT EXISTS academic_transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            source_system TEXT NOT NULL,
            source_student_id TEXT NOT NULL,
            transfer_date TEXT NOT NULL DEFAULT (datetime('now')),
            data_json TEXT NOT NULL
        );
