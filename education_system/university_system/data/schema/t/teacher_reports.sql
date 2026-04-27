CREATE TABLE IF NOT EXISTS teacher_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            teacher_id INTEGER,
            module_code TEXT,
            report_type TEXT,
            report_content TEXT,
            created_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
