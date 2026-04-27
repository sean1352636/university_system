CREATE TABLE IF NOT EXISTS scholarship_deadline_reminders (
                        reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        application_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        scholarship_id INTEGER NOT NULL,
                        deadline_date TEXT NOT NULL,
                        reminder_date TEXT NOT NULL,
                        reminder_type TEXT CHECK(reminder_type IN ('one-month', 'two-weeks', 'one-week', 'three-days', 'one-day', 'custom')),
                        days_before_deadline INTEGER,
                        reminder_sent BOOLEAN DEFAULT 0,
                        reminder_sent_date TEXT,
                        notification_method TEXT CHECK(notification_method IN ('email', 'sms', 'push', 'all')),
                        message TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (application_id) REFERENCES student_scholarship_applications(application_id),
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (scholarship_id) REFERENCES scholarship_opportunities(scholarship_id)
                    );
