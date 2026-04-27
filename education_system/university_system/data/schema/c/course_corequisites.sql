CREATE TABLE IF NOT EXISTS course_corequisites (
                    corequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    corequisite_course_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id),
                    UNIQUE(course_id, corequisite_course_id)
                );
