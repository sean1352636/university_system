CREATE TABLE IF NOT EXISTS exercise_tracking (
                    exercise_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    exercise_date TEXT NOT NULL,
                    exercise_type TEXT NOT NULL,
                    duration_minutes INTEGER,
                    intensity TEXT,
                    calories_burned INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
