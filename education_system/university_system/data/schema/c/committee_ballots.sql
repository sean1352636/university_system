CREATE TABLE IF NOT EXISTS committee_ballots (
                    ballot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vote_id INTEGER NOT NULL,
                    voter_id TEXT NOT NULL,
                    choice TEXT NOT NULL,
                    cast_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vote_id) REFERENCES committee_votes(vote_id),
                    UNIQUE(vote_id, voter_id)
                );
