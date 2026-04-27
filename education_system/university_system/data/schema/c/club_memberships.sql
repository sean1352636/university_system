CREATE TABLE IF NOT EXISTS club_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                student_id TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            );
