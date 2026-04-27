CREATE TABLE IF NOT EXISTS team_members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES team_formations(team_id),
                FOREIGN KEY (user_id) REFERENCES users(username),
                UNIQUE(team_id, user_id)
            );
