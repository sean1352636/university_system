CREATE TABLE IF NOT EXISTS faculty_notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accommodation_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    faculty_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    accommodation_summary TEXT NOT NULL,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    acknowledged INTEGER DEFAULT 0,
                    FOREIGN KEY (accommodation_id) REFERENCES accommodations(accommodation_id)
                );
