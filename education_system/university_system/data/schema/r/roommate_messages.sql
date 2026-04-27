CREATE TABLE IF NOT EXISTS roommate_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    sender_profile_id INTEGER NOT NULL,
                    receiver_profile_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES roommate_matches(match_id) ON DELETE CASCADE,
                    FOREIGN KEY (sender_profile_id) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE,
                    FOREIGN KEY (receiver_profile_id) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE
                );
