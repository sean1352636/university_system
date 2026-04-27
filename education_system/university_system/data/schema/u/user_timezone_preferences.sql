CREATE TABLE IF NOT EXISTS user_timezone_preferences (
                    user_id TEXT PRIMARY KEY,
                    timezone_name TEXT NOT NULL,
                    auto_dst BOOLEAN DEFAULT TRUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
