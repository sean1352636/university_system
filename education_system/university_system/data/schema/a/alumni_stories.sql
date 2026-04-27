CREATE TABLE IF NOT EXISTS alumni_stories (
            story_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            title TEXT,
            content TEXT,
            story_type TEXT,
            publish_date TEXT,
            is_featured BOOLEAN DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            category TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
