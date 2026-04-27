CREATE TABLE IF NOT EXISTS mental_health_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            content_type TEXT NOT NULL,
            content_url TEXT,
            tags TEXT,
            view_count INTEGER DEFAULT 0,
            is_published INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        , "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP);
