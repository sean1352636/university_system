CREATE TABLE IF NOT EXISTS "course_events" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    event_sub_type TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                    UNIQUE(event_id, course_id)
                );
