CREATE TABLE IF NOT EXISTS mood_tracking (
                    mood_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    mood_date TEXT NOT NULL,
                    mood_type TEXT NOT NULL,
                    intensity INTEGER CHECK(intensity BETWEEN 1 AND 5),
                    triggers TEXT,
                    activities TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
