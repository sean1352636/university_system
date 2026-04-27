CREATE TABLE IF NOT EXISTS instructor_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (instructor_id) REFERENCES instructors(id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code),
            UNIQUE(instructor_id, module_code)
        );
