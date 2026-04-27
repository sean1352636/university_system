CREATE TABLE IF NOT EXISTS peer_support_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            description TEXT,
            support_type TEXT,
            facilitator_id TEXT,
            max_members INTEGER,
            current_members INTEGER DEFAULT 0,
            meeting_schedule TEXT,
            status TEXT DEFAULT 'active',
            created_date TEXT,
            FOREIGN KEY (facilitator_id) REFERENCES students (student_id)
        );
