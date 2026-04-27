CREATE TABLE IF NOT EXISTS early_warning_indicators (
            indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            indicator_type TEXT NOT NULL,
            indicator_value TEXT NOT NULL,
            severity TEXT NOT NULL,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_resolved BOOLEAN DEFAULT 0,
            resolved_at TEXT,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
