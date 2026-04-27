CREATE TABLE IF NOT EXISTS transportation_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    service_type TEXT,
                    route_preference TEXT,
                    special_needs TEXT,
                    start_date TEXT,
                    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'Pending'
                );
