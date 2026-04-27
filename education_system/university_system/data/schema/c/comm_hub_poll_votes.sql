CREATE TABLE IF NOT EXISTS comm_hub_poll_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poll_id INTEGER NOT NULL,
                    option_id INTEGER NOT NULL,
                    voter_id TEXT NOT NULL,
                    comment TEXT,
                    voted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (poll_id) REFERENCES comm_hub_polls(poll_id),
                    FOREIGN KEY (option_id) REFERENCES comm_hub_poll_options(option_id),
                    UNIQUE(poll_id, option_id, voter_id)
                );
