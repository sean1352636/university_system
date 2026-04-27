CREATE TABLE IF NOT EXISTS comm_hub_polls (
                    poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forum_id INTEGER,
                    thread_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    poll_type TEXT DEFAULT 'single_choice',
                    is_anonymous INTEGER DEFAULT 0,
                    allow_comments INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'open',
                    closes_at TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (forum_id) REFERENCES comm_hub_forums(forum_id),
                    FOREIGN KEY (thread_id) REFERENCES comm_hub_threads(thread_id)
                );
