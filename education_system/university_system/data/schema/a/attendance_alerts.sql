CREATE TABLE IF NOT EXISTS attendance_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT UNIQUE,
            student_id TEXT,
            module_code TEXT,
            alert_type TEXT,
            severity TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT,
            acknowledged_at TEXT,
            status TEXT DEFAULT 'pending',
            recipient_email TEXT,
            recipient_phone TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
