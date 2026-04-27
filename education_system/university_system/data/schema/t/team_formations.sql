CREATE TABLE IF NOT EXISTS team_formations (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL UNIQUE,
                sport_type TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                team_size INTEGER NOT NULL,
                current_members INTEGER DEFAULT 1,
                skill_level TEXT,
                description TEXT,
                status TEXT DEFAULT 'recruiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES users(username)
            );
