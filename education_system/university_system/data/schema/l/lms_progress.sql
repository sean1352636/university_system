CREATE TABLE IF NOT EXISTS lms_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            lesson_id INTEGER NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            FOREIGN KEY (lesson_id) REFERENCES lms_lessons(id),
            UNIQUE (student_id, lesson_id)
        );
