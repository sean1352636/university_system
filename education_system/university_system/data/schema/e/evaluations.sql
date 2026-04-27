CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                teaching_quality INTEGER NOT NULL,
                course_content INTEGER NOT NULL,
                workload INTEGER NOT NULL,
                communication INTEGER NOT NULL,
                overall INTEGER NOT NULL,
                comments TEXT,
                submitted_at TEXT NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id)
            );
