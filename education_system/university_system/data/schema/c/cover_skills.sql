CREATE TABLE IF NOT EXISTS cover_skills (
                    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    proficiency TEXT DEFAULT 'intermediate',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
