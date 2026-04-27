CREATE TABLE IF NOT EXISTS alumni_forum (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id TEXT,
            title TEXT,
            content TEXT,
            category TEXT,
            post_date TEXT,
            last_updated TEXT,
            reply_count INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            is_pinned BOOLEAN DEFAULT 0,
            FOREIGN KEY (author_id) REFERENCES alumni (alumni_id)
        );
