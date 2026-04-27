CREATE TABLE IF NOT EXISTS knowledge_base (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            tags TEXT,
            author_id INTEGER,
            status TEXT DEFAULT 'draft',
            views INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            unhelpful_votes INTEGER DEFAULT 0,
            search_keywords TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (author_id) REFERENCES users (id)
        );
