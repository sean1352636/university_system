CREATE TABLE IF NOT EXISTS teacher_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                day_of_week TEXT,
                start_time TEXT,
                end_time TEXT,
                meeting_type TEXT,
                location TEXT,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (teacher_id) REFERENCES users (id)
            );
