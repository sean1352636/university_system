CREATE TABLE IF NOT EXISTS comm_hub_replies (
                    reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER NOT NULL,
                    parent_reply_id INTEGER,
                    content TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    is_solution INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (thread_id) REFERENCES comm_hub_threads(thread_id),
                    FOREIGN KEY (parent_reply_id) REFERENCES comm_hub_replies(reply_id)
                );
