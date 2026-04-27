CREATE TABLE IF NOT EXISTS instructor_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (instructor_id) REFERENCES instructors(id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        );
