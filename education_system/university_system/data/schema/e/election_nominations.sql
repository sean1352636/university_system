CREATE TABLE IF NOT EXISTS election_nominations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                election_id INTEGER,
                student_id TEXT,
                position TEXT,
                nomination_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
