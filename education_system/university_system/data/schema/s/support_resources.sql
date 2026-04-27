CREATE TABLE IF NOT EXISTS support_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            url TEXT,
            file_path TEXT,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            updated_datetime TEXT,
            access_count INTEGER DEFAULT 0,
            tags TEXT,  -- JSON array
            content_type TEXT,
            is_featured BOOLEAN DEFAULT 0,
            requires_auth BOOLEAN DEFAULT 0
        );
