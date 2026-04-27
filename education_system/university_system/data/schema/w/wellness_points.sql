CREATE TABLE IF NOT EXISTS wellness_points (
                    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    points_earned INTEGER DEFAULT 0,
                    activity_type TEXT NOT NULL,
                    activity_description TEXT,
                    earned_date TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
