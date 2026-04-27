CREATE TABLE IF NOT EXISTS comm_hub_forum_members (
                    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forum_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT DEFAULT 'member',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (forum_id) REFERENCES comm_hub_forums(forum_id),
                    UNIQUE(forum_id, user_id)
                );
