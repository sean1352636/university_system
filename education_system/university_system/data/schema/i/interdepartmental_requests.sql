CREATE TABLE IF NOT EXISTS interdepartmental_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_type TEXT NOT NULL,
                from_department TEXT,
                to_department TEXT,
                requested_by TEXT NOT NULL,
                requested_by_name TEXT,
                request_title TEXT NOT NULL,
                request_description TEXT,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                assigned_to TEXT,
                assigned_to_name TEXT,
                due_date TEXT,
                completed_date TEXT,
                response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
