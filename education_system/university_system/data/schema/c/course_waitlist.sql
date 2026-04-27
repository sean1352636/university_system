CREATE TABLE IF NOT EXISTS course_waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            added_at TEXT NOT NULL,
            status TEXT DEFAULT 'Waiting',
            FOREIGN KEY (course_id) REFERENCES courses (id),
            UNIQUE(course_id, student_id)
        );
