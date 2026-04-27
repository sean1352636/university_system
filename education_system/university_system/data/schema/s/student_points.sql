CREATE TABLE IF NOT EXISTS student_points (
            points_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            points_earned INTEGER,
            points_spent INTEGER DEFAULT 0,
            current_balance INTEGER,
            activity_type TEXT,
            activity_description TEXT,
            earned_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
