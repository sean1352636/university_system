CREATE TABLE IF NOT EXISTS expense_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    amount REAL NOT NULL,
                    description TEXT,
                    submitted_by TEXT,
                    submitted_date TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    club_id INTEGER,
                    event_id INTEGER
                );
