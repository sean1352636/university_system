CREATE TABLE IF NOT EXISTS course_credit_registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    user_id TEXT,
                    credits INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'registered',
                    registered_at TEXT
                );
