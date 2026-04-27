CREATE TABLE IF NOT EXISTS book_club_books (
                book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT,
                genre TEXT,
                page_count INTEGER,
                description TEXT,
                discussion_date TEXT,
                proposed_by TEXT,
                proposed_date TEXT,
                status TEXT DEFAULT 'proposed',
                votes INTEGER DEFAULT 0,
                FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
            );
