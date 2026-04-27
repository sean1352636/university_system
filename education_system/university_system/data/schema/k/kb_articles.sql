CREATE TABLE IF NOT EXISTS kb_articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            category TEXT NOT NULL,
            tags TEXT,  -- JSON array
            author_id TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            updated_datetime TEXT,
            published_datetime TEXT,
            is_published BOOLEAN DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            not_helpful_votes INTEGER DEFAULT 0,
            search_keywords TEXT,  -- Space-separated keywords for search
            related_articles TEXT  -- JSON array of related article IDs
        );
