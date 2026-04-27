CREATE TABLE IF NOT EXISTS roommate_matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id_1 INTEGER NOT NULL,
                    profile_id_2 INTEGER NOT NULL,
                    compatibility_score REAL NOT NULL,
                    match_reasons TEXT,
                    status TEXT DEFAULT 'Suggested',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id_1) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE,
                    FOREIGN KEY (profile_id_2) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE
                );
