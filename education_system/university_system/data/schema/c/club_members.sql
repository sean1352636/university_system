CREATE TABLE IF NOT EXISTS club_members (
                    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_id INTEGER,
                    student_id TEXT,
                    role TEXT DEFAULT 'member',
                    join_date TEXT, "id" INTEGER,
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
