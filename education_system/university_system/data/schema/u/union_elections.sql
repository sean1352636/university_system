CREATE TABLE IF NOT EXISTS union_elections (
            election_id INTEGER PRIMARY KEY AUTOINCREMENT,
            position TEXT,
            department TEXT,
            nomination_start TEXT,
            nomination_end TEXT,
            voting_start TEXT,
            voting_end TEXT,
            status TEXT DEFAULT 'upcoming'
        );
