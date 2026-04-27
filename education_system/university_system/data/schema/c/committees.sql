CREATE TABLE IF NOT EXISTS committees (
                committee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                committee_type TEXT DEFAULT 'standing',
                department TEXT,
                chair_id TEXT,
                chair_name TEXT,
                secretary_id TEXT,
                secretary_name TEXT,
                meeting_frequency TEXT,
                meeting_location TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
