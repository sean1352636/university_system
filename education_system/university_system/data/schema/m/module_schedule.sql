CREATE TABLE IF NOT EXISTS module_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT,
                day_of_week TEXT,
                start_time TEXT,
                end_time TEXT,
                room_id INTEGER,
                instructor_id INTEGER,
                session_type TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, semester TEXT DEFAULT 'Fall', year INTEGER DEFAULT 0, status TEXT DEFAULT 'published', recurrence TEXT DEFAULT 'weekly', recurrence_until TEXT, parent_schedule_id INTEGER,
                FOREIGN KEY (module_code) REFERENCES modules (module_code),
                FOREIGN KEY (room_id) REFERENCES rooms (id),
                FOREIGN KEY (instructor_id) REFERENCES instructors (id)
            );
