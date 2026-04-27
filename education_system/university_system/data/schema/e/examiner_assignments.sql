CREATE TABLE IF NOT EXISTS examiner_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                examiner_id INTEGER NOT NULL,
                student_id TEXT,
                student_name TEXT,
                course_code TEXT,
                assignment_type TEXT,
                academic_year TEXT,
                report_submitted INTEGER DEFAULT 0,
                report_date TEXT,
                report_path TEXT,
                feedback TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (examiner_id) REFERENCES external_examiners(examiner_id)
            );
