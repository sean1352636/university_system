CREATE TABLE IF NOT EXISTS early_alert_indicators (
                    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    indicator_type TEXT NOT NULL,
                    current_value REAL,
                    threshold_value REAL,
                    risk_level TEXT DEFAULT 'Low',
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    follow_up_date TEXT,
                    status TEXT DEFAULT 'Active',
                    notes TEXT
                );
