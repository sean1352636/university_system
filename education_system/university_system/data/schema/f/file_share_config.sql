CREATE TABLE IF NOT EXISTS file_share_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
