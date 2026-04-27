CREATE TABLE IF NOT EXISTS student_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            badge_id INTEGER,
            earned_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (badge_id) REFERENCES achievement_badges (badge_id)
        );
