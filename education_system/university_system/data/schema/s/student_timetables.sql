CREATE TABLE IF NOT EXISTS student_timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT,
            instructor_id INTEGER,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code),
            FOREIGN KEY (instructor_id) REFERENCES instructors(id)
        );
