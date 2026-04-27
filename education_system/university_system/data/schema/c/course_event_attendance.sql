CREATE TABLE IF NOT EXISTS course_event_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    attendance_status TEXT DEFAULT 'present',
                    notes TEXT,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE,
                    UNIQUE(event_id, student_id)
                );
