CREATE TABLE IF NOT EXISTS student_absences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                absence_date TEXT,
                return_date TEXT,
                reason TEXT,
                reported_by TEXT,
                reported_date TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
