CREATE TABLE IF NOT EXISTS ai_activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id TEXT,
                        username TEXT,
                        action TEXT,
                        details TEXT
                    );
