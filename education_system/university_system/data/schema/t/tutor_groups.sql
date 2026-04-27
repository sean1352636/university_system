CREATE TABLE IF NOT EXISTS tutor_groups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    academic_year TEXT NOT NULL,
                    programme TEXT,
                    lead_tutor_id INTEGER,
                    capacity INTEGER NOT NULL DEFAULT 20,
                    meeting_pattern TEXT DEFAULT 'weekly',
                    notes TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
