CREATE TABLE IF NOT EXISTS alumni_chapters (
            chapter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_name TEXT NOT NULL,
            region TEXT NOT NULL,
            chapter_leader_id INTEGER,
            contact_email TEXT,
            description TEXT,
            meeting_frequency TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chapter_leader_id) REFERENCES alumni_profiles (alumni_id)
        );
