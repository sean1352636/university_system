CREATE TABLE IF NOT EXISTS staff_mentoring_programmes (
                    programme_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    programme_type TEXT DEFAULT 'general',
                    department TEXT,
                    max_mentees_per_mentor INTEGER DEFAULT 3,
                    duration_months INTEGER DEFAULT 12,
                    status TEXT DEFAULT 'active',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
