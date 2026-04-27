CREATE TABLE IF NOT EXISTS hydration_tracking (
                    hydration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    tracking_date TEXT NOT NULL,
                    glasses_consumed INTEGER DEFAULT 0,
                    daily_goal INTEGER DEFAULT 8,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
