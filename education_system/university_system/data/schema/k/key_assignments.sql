CREATE TABLE IF NOT EXISTS key_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_number TEXT NOT NULL,
                key_type TEXT,
                room_location TEXT,
                building TEXT,
                assigned_to TEXT,
                assigned_to_name TEXT,
                assigned_date TEXT,
                return_date TEXT,
                status TEXT DEFAULT 'assigned',
                issued_by TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
