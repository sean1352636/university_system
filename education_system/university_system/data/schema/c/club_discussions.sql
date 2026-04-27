CREATE TABLE IF NOT EXISTS club_discussions (
            discussion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            author_id TEXT,
            title TEXT,
            content TEXT,
            post_date TEXT,
            last_updated TEXT,
            is_announcement BOOLEAN DEFAULT 0,
            pinned BOOLEAN DEFAULT 0,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (author_id) REFERENCES students (student_id)
        );
