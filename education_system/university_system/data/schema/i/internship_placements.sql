CREATE TABLE IF NOT EXISTS internship_placements (
            placement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            internship_id INTEGER,
            start_date TEXT,
            end_date TEXT,
            supervisor_name TEXT,
            supervisor_email TEXT,
            status TEXT DEFAULT 'active',
            feedback_student TEXT,
            feedback_employer TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (internship_id) REFERENCES internships (internship_id)
        );
