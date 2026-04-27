CREATE TABLE IF NOT EXISTS committee_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id INTEGER NOT NULL,
                    committee_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    vote_type TEXT DEFAULT 'simple_majority',
                    is_secret_ballot INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    votes_for INTEGER DEFAULT 0,
                    votes_against INTEGER DEFAULT 0,
                    votes_abstain INTEGER DEFAULT 0,
                    result TEXT,
                    opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT,
                    created_by TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES committee_meetings(meeting_id),
                    FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
                );
