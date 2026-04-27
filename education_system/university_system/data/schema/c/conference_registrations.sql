CREATE TABLE IF NOT EXISTS conference_registrations (
                    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    travel_request_id INTEGER,
                    conference_name TEXT NOT NULL,
                    conference_url TEXT,
                    location TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    registration_fee REAL DEFAULT 0,
                    presentation_title TEXT,
                    presentation_type TEXT,
                    is_presenting INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'registered',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (travel_request_id) REFERENCES travel_requests(request_id)
                );
