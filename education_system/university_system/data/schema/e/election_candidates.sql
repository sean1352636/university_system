CREATE TABLE IF NOT EXISTS election_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER,
            student_id TEXT,
            manifesto TEXT,
            votes INTEGER DEFAULT 0,
            FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
