CREATE TABLE IF NOT EXISTS staff_expertise (
                    expertise_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    expertise_area TEXT NOT NULL,
                    category TEXT DEFAULT 'academic',
                    proficiency TEXT DEFAULT 'intermediate',
                    keywords TEXT,
                    is_public INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
