CREATE TABLE IF NOT EXISTS internship_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            internship_id INTEGER,
            application_date TEXT,
            status TEXT DEFAULT 'pending',
            cv_filename TEXT,
            cover_letter TEXT,
            feedback TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (internship_id) REFERENCES internships (internship_id)
        );
