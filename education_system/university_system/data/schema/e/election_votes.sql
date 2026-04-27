CREATE TABLE IF NOT EXISTS election_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER,
            voter_id TEXT,
            candidate_id INTEGER,
            vote_time TEXT,
            FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
            FOREIGN KEY (voter_id) REFERENCES students (student_id),
            FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
        );
