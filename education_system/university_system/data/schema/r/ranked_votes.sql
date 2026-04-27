CREATE TABLE IF NOT EXISTS ranked_votes (
            vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER,
            voter_id TEXT,
            candidate_preferences TEXT,  -- JSON string of ranked preferences
            vote_time TEXT,
            FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
            FOREIGN KEY (voter_id) REFERENCES students (student_id)
        );
