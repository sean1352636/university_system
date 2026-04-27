CREATE TABLE IF NOT EXISTS travel_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    approver_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                );
