CREATE TABLE IF NOT EXISTS attendees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone_number TEXT,
                    student_id TEXT,
                    created_at TEXT NOT NULL
                );
