CREATE TABLE IF NOT EXISTS course_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        semester TEXT NOT NULL,
        year INTEGER NOT NULL,
        start_time TEXT,
        end_time TEXT,
        days_of_week TEXT,
        classroom TEXT,
        instructor_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(course_id) REFERENCES courses(id),
        FOREIGN KEY(instructor_id) REFERENCES instructors(id),
        UNIQUE(course_id, semester, year)
    );
