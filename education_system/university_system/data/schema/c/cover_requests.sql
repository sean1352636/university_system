CREATE TABLE IF NOT EXISTS cover_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requester_id TEXT NOT NULL,
                    request_type TEXT DEFAULT 'teaching',
                    course_code TEXT,
                    course_name TEXT,
                    cover_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    location TEXT,
                    reason TEXT,
                    urgency TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'open',
                    department TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
