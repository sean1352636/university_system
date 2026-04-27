CREATE TABLE IF NOT EXISTS student_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                activity_id INTEGER,
                enrollment_date TEXT,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (activity_id) REFERENCES extracurricular_activities (id)
            );
