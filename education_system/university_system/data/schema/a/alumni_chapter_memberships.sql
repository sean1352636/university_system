CREATE TABLE IF NOT EXISTS alumni_chapter_memberships (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            alumni_id INTEGER NOT NULL,
            join_date TEXT DEFAULT CURRENT_DATE,
            membership_status TEXT DEFAULT 'active',
            FOREIGN KEY (chapter_id) REFERENCES alumni_chapters (chapter_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni_profiles (alumni_id)
        );
