CREATE TABLE IF NOT EXISTS cover_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    assignee_id TEXT NOT NULL,
                    assigned_by TEXT,
                    accepted INTEGER DEFAULT 0,
                    accepted_date TEXT,
                    completed INTEGER DEFAULT 0,
                    completed_date TEXT,
                    feedback TEXT,
                    rating INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES cover_requests(request_id)
                );
