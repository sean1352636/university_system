CREATE TABLE IF NOT EXISTS sc_votes (
        voter_id TEXT PRIMARY KEY,
        candidate_id INTEGER,
        cast_at TEXT,
        FOREIGN KEY (candidate_id) REFERENCES sc_candidates(id)
    );
