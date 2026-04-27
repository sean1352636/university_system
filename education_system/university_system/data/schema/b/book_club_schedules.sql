CREATE TABLE IF NOT EXISTS book_club_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                book_title TEXT,
                schedule_content TEXT,
                created_by TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
            );
