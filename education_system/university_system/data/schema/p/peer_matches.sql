CREATE TABLE IF NOT EXISTS peer_matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT NOT NULL,
            matched_id TEXT,
            requester_anon_id TEXT NOT NULL,
            matched_anon_id TEXT,
            topic TEXT,
            match_type TEXT DEFAULT 'One-on-one',
            status TEXT DEFAULT 'pending',
            matched_date TEXT,
            created_date TEXT NOT NULL
        );
