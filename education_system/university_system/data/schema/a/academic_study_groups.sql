CREATE TABLE IF NOT EXISTS academic_study_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                subject TEXT,
                description TEXT,
                max_members INTEGER DEFAULT 10,
                current_members INTEGER DEFAULT 1,
                meeting_schedule TEXT,
                location TEXT,
                created_by TEXT,
                created_at TEXT,
                status TEXT DEFAULT 'active'
            );
