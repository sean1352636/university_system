CREATE TABLE IF NOT EXISTS chapter_memberships (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER,
            alumni_id TEXT,
            join_date TEXT,
            role TEXT DEFAULT 'member',
            FOREIGN KEY (chapter_id) REFERENCES regional_chapters (chapter_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
