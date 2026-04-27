CREATE TABLE IF NOT EXISTS peer_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            sender_anon_id TEXT NOT NULL,
            message_text TEXT NOT NULL,
            sent_date TEXT NOT NULL,
            FOREIGN KEY (match_id) REFERENCES peer_matches (match_id)
        );
