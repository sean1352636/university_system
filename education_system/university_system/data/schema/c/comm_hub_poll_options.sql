CREATE TABLE IF NOT EXISTS comm_hub_poll_options (
                    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poll_id INTEGER NOT NULL,
                    option_text TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    vote_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (poll_id) REFERENCES comm_hub_polls(poll_id)
                );
