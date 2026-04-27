CREATE TABLE IF NOT EXISTS emergency_pickup_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    pickup_person TEXT NOT NULL,
                    reason TEXT,
                    time_needed TEXT,
                    contact_phone TEXT,
                    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'Pending'
                );
