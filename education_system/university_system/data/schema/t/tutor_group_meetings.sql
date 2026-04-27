CREATE TABLE IF NOT EXISTS tutor_group_meetings (
                    meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    location TEXT,
                    agenda TEXT,
                    attendance_count INTEGER,
                    notes TEXT,
                    status TEXT DEFAULT 'scheduled',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (group_id) REFERENCES tutor_groups (group_id)
                );
