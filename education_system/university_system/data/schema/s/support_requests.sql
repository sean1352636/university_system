CREATE TABLE IF NOT EXISTS support_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            anonymous_id TEXT,
            group_id INTEGER,
            group_name TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            requested_date TEXT NOT NULL,
            resolved_date TEXT,
            resolved_by TEXT
        );
