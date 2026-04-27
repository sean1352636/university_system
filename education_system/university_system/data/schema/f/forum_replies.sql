CREATE TABLE IF NOT EXISTS forum_replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            author_id TEXT,
            content TEXT,
            reply_date TEXT,
            parent_reply_id INTEGER,
            FOREIGN KEY (post_id) REFERENCES alumni_forum (post_id),
            FOREIGN KEY (author_id) REFERENCES alumni (alumni_id)
        );
