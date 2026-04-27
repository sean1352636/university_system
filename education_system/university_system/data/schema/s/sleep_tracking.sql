CREATE TABLE IF NOT EXISTS sleep_tracking (
                    sleep_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    sleep_date TEXT NOT NULL,
                    bedtime TEXT,
                    wake_time TEXT,
                    hours_slept REAL,
                    sleep_quality INTEGER CHECK(sleep_quality BETWEEN 1 AND 5),
                    interruptions INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
