CREATE TABLE IF NOT EXISTS book_clubs (
            book_club_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_name TEXT,
            current_book TEXT,
            book_author TEXT,
            discussion_leader_id TEXT,
            meeting_schedule TEXT,
            max_members INTEGER,
            current_members INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            description TEXT,
            FOREIGN KEY (discussion_leader_id) REFERENCES students (student_id)
        );
