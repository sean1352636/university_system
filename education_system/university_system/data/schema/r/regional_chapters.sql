CREATE TABLE IF NOT EXISTS regional_chapters (
            chapter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_name TEXT,
            location TEXT,
            coordinator_id TEXT,
            description TEXT,
            created_date TEXT,
            member_count INTEGER DEFAULT 0,
            FOREIGN KEY (coordinator_id) REFERENCES alumni (alumni_id)
        );
