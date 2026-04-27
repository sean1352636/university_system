CREATE TABLE IF NOT EXISTS comm_hub_threads (
                    thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forum_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    author_id TEXT NOT NULL,
                    is_pinned INTEGER DEFAULT 0,
                    is_locked INTEGER DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    reply_count INTEGER DEFAULT 0,
                    last_reply_at TEXT,
                    last_reply_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (forum_id) REFERENCES comm_hub_forums(forum_id)
                );
